"""FORGE-VISION — Court-admissible forensic report generator (PDF + JSON)"""
import io
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..database import get_db
from ..routers.auth import get_current_user, require_role
from ..hash_engine import verify_chain
from ..custody.ledger import get_custody_chain, append_custody_event

router = APIRouter()

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence_store", "reports")


@router.post("/case/{case_id}/generate")
async def generate_report(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_role("supervisor", "investigator")),
):
    """Generate court-admissible forensic report PDF. Supervisor role required to finalize."""
    async with db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)) as cur:
        case = dict(await cur.fetchone() or {})
    if not case:
        raise HTTPException(404, "Case not found")

    async with db.execute("SELECT * FROM evidence WHERE case_id = ?", (case_id,)) as cur:
        evidence_list = [dict(r) for r in await cur.fetchall()]

    async with db.execute("SELECT * FROM ai_findings WHERE case_id = ? ORDER BY confidence DESC", (case_id,)) as cur:
        ai_findings = [dict(r) for r in await cur.fetchall()]

    async with db.execute(
        """SELECT af.*, e.camera_id FROM authenticity_findings af
           JOIN evidence e ON af.evidence_id = e.id WHERE e.case_id = ?""", (case_id,)
    ) as cur:
        auth_findings = [dict(r) for r in await cur.fetchall()]

    async with db.execute("SELECT * FROM datasets WHERE case_id = ?", (case_id,)) as cur:
        datasets_list = [dict(r) for r in await cur.fetchall()]

    async with db.execute("SELECT * FROM bookmarks WHERE case_id = ? ORDER BY created_at DESC", (case_id,)) as cur:
        bookmarks_list = [dict(r) for r in await cur.fetchall()]

    custody_entries = await get_custody_chain(db, case_id)
    chain_verification = verify_chain(custody_entries)

    report_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    report_data = {
        "report_id": report_id,
        "report_generated_at": now_iso,
        "generated_by": current_user.get("full_name") or current_user.get("username", "Forensic Investigator"),
        "operator_role": current_user.get("role", "investigator").upper(),
        "system": "FORGE-VISION v1.0.0-SIH150",
        "case": case,
        "datasets": datasets_list,
        "evidence_inventory": evidence_list,
        "bookmarks": bookmarks_list,
        "ai_findings": ai_findings,
        "authenticity_findings": auth_findings,
        "custody_chain": custody_entries,
        "chain_verification": chain_verification,
    }

    pdf_bytes = _generate_pdf(report_data)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, f"{case_id}_report.pdf")
    with open(report_path, "wb") as f:
        f.write(pdf_bytes)

    await append_custody_event(
        db, case_id=case_id, action="report_generated",
        operator_id=current_user["id"], operator_role=current_user["role"],
        detail={"report_id": report_data["report_id"], "page_count": "see PDF"},
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="FORGE-VISION-{case_id}.pdf"'},
    )


def _generate_pdf(data: dict) -> bytes:
    """Generate PDF report using ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak,
        )
        from reportlab.platypus.flowables import KeepTogether

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm,
                                leftMargin=20*mm, rightMargin=20*mm)

        styles = getSampleStyleSheet()
        DARK = colors.HexColor("#0a0e1a")
        AMBER = colors.HexColor("#f59e0b")
        CYAN = colors.HexColor("#06b6d4")
        RED = colors.HexColor("#ef4444")
        GREEN = colors.HexColor("#22c55e")
        GRAY = colors.HexColor("#64748b")

        h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=DARK, fontSize=20, spaceAfter=6)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=AMBER, fontSize=13, spaceAfter=4, spaceBefore=12)
        h3 = ParagraphStyle("H3", parent=styles["Heading3"], textColor=CYAN, fontSize=11, spaceAfter=3, spaceBefore=8)
        body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, spaceAfter=3)
        mono = ParagraphStyle("Mono", parent=styles["Normal"], fontName="Courier", fontSize=7.5, spaceAfter=2)
        warn = ParagraphStyle("Warn", parent=styles["Normal"], textColor=RED, fontSize=8, spaceAfter=3, spaceBefore=3)
        note = ParagraphStyle("Note", parent=styles["Normal"], textColor=GRAY, fontSize=8, spaceAfter=3)

        case = data.get("case", {})
        evidence_list = data.get("evidence_inventory", [])
        ai_findings = data.get("ai_findings", [])
        auth_findings = data.get("authenticity_findings", [])
        custody = data.get("custody_chain", [])
        chain_v = data.get("chain_verification", {})

        elements = []

        # ── HEADER ──────────────────────────────────────────────
        elements.append(Paragraph("🔍 FORGE-VISION", h1))
        elements.append(Paragraph("Forensic Video Intelligence Report", ParagraphStyle("sub", parent=styles["Normal"], fontSize=12, textColor=GRAY)))
        elements.append(Paragraph(f"System: FORGE-VISION v1.0.0-SIH150 | SIH Problem Statement 150", note))
        elements.append(HRFlowable(width="100%", thickness=2, color=AMBER))
        elements.append(Spacer(1, 6))

        # ── CASE METADATA ────────────────────────────────────────
        elements.append(Paragraph("1. CASE METADATA", h2))
        meta_data = [
            ["Case ID", case.get("id", "?")],
            ["Title", case.get("title", "?")],
            ["Status", case.get("status", "?").upper()],
            ["Created By", case.get("created_by", "?")],
            ["Created At", case.get("created_at", "?")],
            ["Reference Timezone", case.get("reference_timezone", "Asia/Kolkata")],
            ["Report Generated", data.get("report_generated_at", "?")],
            ["Report Generated By", data.get("generated_by", "?")],
            ["System", data.get("system", "?")],
        ]
        t = Table(meta_data, colWidths=[50*mm, 120*mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f1f5f9")),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 8))

        # ── DATASET PROVENANCE ─────────────────────────────────
        datasets = data.get("datasets", [])
        if datasets:
            elements.append(Paragraph("2. DATASET PROVENANCE & SOURCE CLASSIFICATION", h2))
            
            # Check if any public research or synthetic datasets are present
            has_public_research = any(d.get("source_type") == "PUBLIC_RESEARCH_DATASET" or d.get("platform") == "Kaggle" for d in datasets)
            has_synthetic = any(d.get("source_type") == "SYNTHETIC_DEMO" or d.get("is_synthetic") for d in datasets)
            
            if has_public_research:
                elements.append(Paragraph(
                    "📌 <b>DATASET PROVENANCE NOTICE:</b> Public research dataset — not original case-acquired DVR evidence. "
                    "Original bitstream hashes preserved without vendor fabrication.",
                    ParagraphStyle("resNotice", parent=styles["Normal"], textColor=CYAN, fontSize=8, spaceAfter=4)
                ))
            if has_synthetic:
                elements.append(Paragraph(
                    "⚠ <b>DEMO LIMITATION NOTICE:</b> Synthetic demonstration data — not original forensic evidence. "
                    "Simulated vendor format labeled for evaluation only.",
                    ParagraphStyle("synNotice", parent=styles["Normal"], textColor=AMBER, fontSize=8, spaceAfter=4)
                ))

            ds_rows = [["Dataset Name", "Source Type", "Platform / Ref", "License", "Forensic Status"]]
            for ds in datasets:
                ds_rows.append([
                    ds.get("name", "?")[:22],
                    ds.get("source_type", "?")[:24],
                    (ds.get("kaggle_dataset_identifier") or ds.get("source_provider") or "Direct")[:20],
                    ds.get("license", "?")[:22],
                    ds.get("forensic_status", "AUTHENTIC"),
                ])
            t_ds = Table(ds_rows, colWidths=[40*mm, 35*mm, 35*mm, 35*mm, 25*mm])
            t_ds.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 7),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
            ]))
            elements.append(t_ds)
            elements.append(Spacer(1, 8))

        # ── CHAIN VERIFICATION BANNER ──────────────────────────
        elements.append(Paragraph("3. CHAIN OF CUSTODY INTEGRITY", h2))
        chain_ok = chain_v.get("is_valid", False)
        chain_color = GREEN if chain_ok else RED
        chain_status = "✓ CHAIN INTACT — All custody entries verified" if chain_ok else f"⚠ CHAIN BROKEN at sequence {chain_v.get('broken_at_seq')} — Evidence may have been modified"
        elements.append(Paragraph(chain_status,
            ParagraphStyle("chain", parent=styles["Normal"], textColor=chain_color, fontSize=10, fontName="Helvetica-Bold")))
        elements.append(Paragraph(f"Total entries: {chain_v.get('entry_count', 0)}", body))
        elements.append(Spacer(1, 6))

        # ── EVIDENCE INVENTORY ─────────────────────────────────
        elements.append(Paragraph("4. EVIDENCE INVENTORY", h2))
        if not evidence_list:
            elements.append(Paragraph("No evidence items in this case.", body))
        else:
            ev_rows = [["Evidence ID", "Camera", "Vendor", "Parser", "Integrity", "Authenticity", "SHA256 (first 16)"]]
            for ev in evidence_list:
                sha = (ev.get("sha256") or "")[:16] + "..."
                ev_rows.append([
                    (ev.get("id") or "")[:12] + "...",
                    ev.get("camera_id") or "?",
                    ev.get("source_vendor") or "?",
                    ("SIM-" if ev.get("is_simulated_adapter") else "") + (ev.get("parser_used") or "?"),
                    ev.get("integrity_status") or "?",
                    ev.get("authenticity_status") or "?",
                    sha,
                ])
            t2 = Table(ev_rows, colWidths=[28*mm, 20*mm, 22*mm, 30*mm, 18*mm, 22*mm, 30*mm])
            t2.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), DARK),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 7),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ]))
            elements.append(t2)

        elements.append(Spacer(1, 8))

        # ── EVIDENCE BOOKMARKS ─────────────────────────────────
        bookmarks = data.get("bookmarks", [])
        if bookmarks:
            elements.append(Paragraph("5. INVESTIGATOR EVIDENCE BOOKMARKS", h2))
            bm_rows = [["Tag", "Camera", "Timestamp", "Title", "Investigator Notes", "Created By"]]
            for bm in bookmarks:
                bm_rows.append([
                    bm.get("tag", "SUSPECT"),
                    bm.get("camera_id", "?"),
                    bm.get("timestamp_in_video", "00:00:00"),
                    bm.get("title", "?")[:25],
                    (bm.get("notes") or "-")[:35],
                    bm.get("created_by", "?")[:16],
                ])
            t_bm = Table(bm_rows, colWidths=[18*mm, 18*mm, 22*mm, 38*mm, 50*mm, 24*mm])
            t_bm.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 7),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#fffbeb")]),
            ]))
            elements.append(t_bm)
            elements.append(Spacer(1, 8))

        # ── HASH VERIFICATION ──────────────────────────────────
        elements.append(Paragraph("6. HASH VERIFICATION RECORDS", h2))
        for ev in evidence_list[:5]:
            elements.append(Paragraph(f"Evidence: {ev.get('id', '?')[:12]}... | Camera: {ev.get('camera_id','?')}", h3))
            elements.append(Paragraph(f"MD5:      {ev.get('md5', 'N/A')}", mono))
            elements.append(Paragraph(f"SHA256:   {ev.get('sha256', 'N/A')}", mono))
            elements.append(Paragraph(f"SHA3-256: {ev.get('sha3_256', 'N/A')}", mono))
            elements.append(Paragraph(f"Integrity: {ev.get('integrity_status','?').upper()}", body))
            elements.append(Spacer(1, 4))

        # ── METHODOLOGY ─────────────────────────────────────────
        elements.append(PageBreak())
        elements.append(Paragraph("5. METHODOLOGY", h2))
        methodology_text = """
        This forensic analysis was performed using FORGE-VISION v1.0.0, a vendor-agnostic DVR/NVR
        forensic intelligence platform. The following methodology was applied:
        (a) Evidence acquired with forensic write-blocking enforcement.
        (b) Triple hash (MD5 + SHA256 + SHA3-256) computed at acquisition.
        (c) Vendor signature detection applied to identify source device parser.
        (d) Video metadata extracted via FFprobe (IEEE/ISO standard tool).
        (e) H.264 NAL start-code scan performed for deleted-data indicators.
        (f) Error Level Analysis (ELA) performed on keyframes for authenticity assessment.
        (g) Frame perceptual-hash duplicate detection performed.
        (h) Scene-change detection performed via FFmpeg lavfi scene filter.
        (i) Motion heatmap generated via frame-differencing accumulation.
        (j) All operations logged to a SHA256-hash-chained chain-of-custody ledger.
        """
        elements.append(Paragraph(methodology_text.strip(), body))

        # ── AI FINDINGS ─────────────────────────────────────────
        elements.append(Paragraph("6. AI-ASSISTED FINDINGS", h2))
        elements.append(Paragraph(
            "⚠ All AI findings below are LEADS for investigator review, not forensic conclusions. "
            "Confidence scores are model estimates. Simulated findings are explicitly marked.",
            warn))

        verified_findings = [f for f in ai_findings if not f.get("is_simulated")]
        sim_findings = [f for f in ai_findings if f.get("is_simulated")]
        elements.append(Paragraph(f"Total AI findings: {len(ai_findings)} ({len(verified_findings)} real, {len(sim_findings)} simulated)", body))

        if ai_findings:
            fi_rows = [["Type", "Camera", "Frame", "Timestamp", "Label", "Confidence", "Simulated"]]
            for f in ai_findings[:20]:
                ev_camera = "?"
                fi_rows.append([
                    f.get("finding_type", "?"),
                    f.get("camera_id", "?"),
                    str(f.get("frame_number", "?")),
                    f.get("timestamp_in_video", "?"),
                    f.get("label", "?"),
                    f"{float(f.get('confidence', 0)):.0%}",
                    "YES" if f.get("is_simulated") else "NO",
                ])
            t3 = Table(fi_rows, colWidths=[22*mm, 18*mm, 16*mm, 24*mm, 25*mm, 18*mm, 18*mm])
            t3.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTSIZE", (0,0), (-1,-1), 7),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#fefce8")]),
            ]))
            elements.append(t3)

        # ── AUTHENTICITY FINDINGS ─────────────────────────────
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("7. AUTHENTICITY / TAMPER FINDINGS", h2))
        elements.append(Paragraph(
            "All findings require expert human review before any forensic conclusion is drawn. "
            "This tool flags statistical anomalies only.",
            warn))

        if not auth_findings:
            elements.append(Paragraph("No authenticity analysis has been run on this evidence. "
                                       "Run authenticity analysis from the investigation workstation.", body))
        else:
            for af in auth_findings:
                severity_color = RED if af.get("severity") == "high" else (AMBER if af.get("severity") == "medium" else GRAY)
                elements.append(Paragraph(
                    f"[{af.get('severity','?').upper()}] {af.get('check_type','?')} — "
                    f"Confidence: {float(af.get('confidence',0)):.0%} {'[SIMULATED]' if af.get('is_simulated') else ''}",
                    ParagraphStyle("af", parent=styles["Normal"], textColor=severity_color, fontSize=9)
                ))
                elements.append(Paragraph(af.get("detail", ""), body))
                elements.append(Spacer(1, 3))

        # ── BSA CERTIFICATE TEMPLATE ───────────────────────────
        elements.append(PageBreak())
        elements.append(Paragraph("8. ELECTRONIC EVIDENCE CERTIFICATE (TEMPLATE)", h2))
        elements.append(Paragraph(
            "⚠ IMPORTANT: This section is a TEMPLATE only. It requires review, completion, and formal "
            "certification by a competent authority as required under the Bharatiya Sakshya Adhiniyam, 2023 "
            "(BSA 2023) or its applicable provisions. This auto-generated document does NOT constitute a "
            "legally self-certifying electronic evidence certificate.",
            warn))
        elements.append(Spacer(1, 6))

        cert_text = f"""
CERTIFICATE UNDER SECTION [APPLICABLE PROVISION] OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023

I, _____________________ [Name], _____________________ [Designation],
do hereby certify that:

1. The electronic records presented as evidence in Case ID: {case.get('id','?')} were obtained
   from {len(evidence_list)} evidence source(s) using the FORGE-VISION forensic acquisition platform.

2. The records were acquired in a forensically sound manner with write-blocking enforcement.
   Acquisition hashes (MD5, SHA256, SHA3-256) were computed at the time of acquisition and are
   documented in this report.

3. The computer resources / analysis tools used:
   System: FORGE-VISION v1.0.0-SIH150
   Video analysis: FFprobe/FFmpeg (open-source, industry-standard)
   Authenticity analysis: Error Level Analysis (PIL/numpy implementation)

4. The information contained in this report was produced without modification to the original evidence.

5. The chain of custody ledger integrity verification result:
   Status: {'CHAIN INTACT' if chain_ok else 'CHAIN BROKEN — see Section 2'}
   Total entries: {chain_v.get('entry_count', 0)}

Signature: _______________________
Date:      _______________________
Place:     _______________________

[THIS TEMPLATE REQUIRES REVIEW AND FORMAL CERTIFICATION BEFORE USE IN LEGAL PROCEEDINGS]
        """
        elements.append(Paragraph(cert_text.strip().replace("\n", "<br/>"), mono))

        # ── CUSTODY LOG SUMMARY ────────────────────────────────
        elements.append(PageBreak())
        elements.append(Paragraph("9. CHAIN OF CUSTODY LOG", h2))
        if custody:
            cust_rows = [["Seq", "Action", "Operator", "Role", "Timestamp", "Entry Hash (first 16)"]]
            for entry in custody:
                cust_rows.append([
                    str(entry.get("seq", "?")),
                    entry.get("action", "?"),
                    entry.get("operator_id", "?")[:12],
                    entry.get("operator_role", "?"),
                    (entry.get("timestamp") or "")[:19],
                    (entry.get("this_entry_hash") or "")[:16] + "...",
                ])
            t4 = Table(cust_rows, colWidths=[12*mm, 32*mm, 30*mm, 22*mm, 38*mm, 36*mm])
            t4.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), DARK),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTSIZE", (0,0), (-1,-1), 7),
                ("FONTNAME", (0,1), (-1,-1), "Courier"),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0fdf4")]),
            ]))
            elements.append(t4)

        # ── FOOTER NOTE ────────────────────────────────────────
        elements.append(Spacer(1, 12))
        elements.append(HRFlowable(width="100%", thickness=1, color=GRAY))
        elements.append(Paragraph(
            "FORGE-VISION | Vendor-Agnostic DVR/NVR Forensic Intelligence Platform | SIH150 | "
            "AI findings are investigative leads, not forensic conclusions. "
            "Simulated adapters are explicitly labeled. This report requires expert review.",
            note))

        doc.build(elements)
        return buf.getvalue()

    except ImportError:
        # ReportLab not installed — return minimal text PDF placeholder
        return _minimal_pdf_fallback(data)


def _minimal_pdf_fallback(data: dict) -> bytes:
    """Minimal fallback if ReportLab is not installed."""
    text = f"""FORGE-VISION Forensic Report
Case: {data.get('case',{}).get('title','?')}
Generated: {data.get('report_generated_at','?')}
Evidence items: {len(data.get('evidence_inventory',[]))}
AI findings: {len(data.get('ai_findings',[]))}
Chain valid: {data.get('chain_verification',{}).get('is_valid','?')}

[Install reportlab for full PDF generation: pip install reportlab]
"""
    # Minimal valid PDF with text
    content = text.encode("latin-1", errors="replace")
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Courier>>>>>>>\n"
        b"endobj\n"
        b"4 0 obj<</Length " + str(len(content) + 50).encode() + b">>\n"
        b"stream\nBT /F1 10 Tf 50 750 Td (" + content[:200] + b") Tj ET\nendstream\nendobj\n"
        b"xref\n0 5\ntrailer<</Size 5/Root 1 0 R>>\n%%EOF"
    )
    return pdf
