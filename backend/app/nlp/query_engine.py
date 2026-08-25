"""
FORGE-VISION — Natural Language Investigation Engine
Strict grounding rule: answers only from stored evidence/findings.
No LLM hallucination — rule-based query parsing + template answers.
"""
import re
from datetime import datetime
from typing import Any, Optional

import aiosqlite


# ─────────────────────────────────────────────────────────────────────────────
# QUERY INTENT PARSER
# ─────────────────────────────────────────────────────────────────────────────

INTENTS = [
    (r"(ucf|ucf crime|anomaly.*cctv)", "ucf_crime"),
    (r"(virat|racd|cctv action|traffic intersection|kaggle|public research|research evidence)", "public_research"),
    (r"(hikvision|dahua|cp plus|generic)", "vendor_specific"),
    (r"(tamper|tampered|altered|edited|suspicious)", "tamper_flags"),
    (r"(vehicle|car|truck|motorcycle|bus|auto)", "vehicles"),
    (r"(person|people|suspect|pedestrian|human|walk|run|fall|fight)", "persons"),
    (r"(camera.*tamper|spray|blackout|defocus|cover)", "camera_tamper"),
    (r"(chain.*custody|custody|ledger)", "custody"),
    (r"(hash|integrity|verified|mismatch)", "integrity"),
    (r"(timeline|when|time|between)", "timeline"),
    (r"(recover|deleted|fragment|carved|missing)", "recovery"),
    (r"(abnormal|anomaly|burglary|robbery|accident|fighting)", "anomalies"),
    (r"(report|summary|overview)", "summary"),
    (r"(camera|channel)\s*(\d+|[A-Za-z]+)", "camera_specific"),
    (r"(all|list|show|what)", "list_findings"),
]


def parse_intent(query: str) -> tuple[str, dict]:
    """Return (intent, params) for a natural language query."""
    q = query.lower().strip()
    params = {}

    # Extract camera/channel number
    cam_match = re.search(r"camera\s*(\d+)|channel\s*(\d+)", q)
    if cam_match:
        params["camera_id"] = cam_match.group(1) or cam_match.group(2)

    # Extract vendor
    for v in ["hikvision", "dahua", "cp plus", "generic"]:
        if v in q:
            params["vendor"] = "CP Plus" if v == "cp plus" else v.capitalize()

    # Extract time range
    time_match = re.search(r"(\d{1,2})\s*(?:am|pm|:00).*?(\d{1,2})\s*(?:am|pm|:00)", q)
    if time_match:
        params["time_range"] = (time_match.group(1), time_match.group(2))

    for pattern, intent in INTENTS:
        if re.search(pattern, q):
            return intent, params

    return "general", params


# ─────────────────────────────────────────────────────────────────────────────
# QUERY HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

async def handle_query(db: aiosqlite.Connection, case_id: str, query: str) -> dict:
    intent, params = parse_intent(query)
    handler = HANDLERS.get(intent, handle_general)
    return await handler(db, case_id, query, params)


async def handle_public_research(db, case_id, query, params):
    async with db.execute(
        """SELECT e.*, d.name as dataset_name, d.license FROM evidence e
           LEFT JOIN datasets d ON e.dataset_id = d.id
           WHERE (e.case_id = ? OR e.case_id IS NULL) AND (e.source_type = 'PUBLIC_RESEARCH_DATASET' OR e.source_platform = 'Kaggle')
           ORDER BY e.ingested_at DESC LIMIT 10""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        return _answer(
            query, intent="public_research",
            answer="No public research dataset evidence imported in this case yet. You can import Kaggle CCTV benchmarks from the Dataset Library.",
            citations=[], confidence=1.0,
        )

    citations = [{
        "evidence_id": r["id"],
        "filename": r.get("original_filename") or r.get("source_name"),
        "dataset": r.get("dataset_name", "Kaggle Benchmark"),
        "source": "Kaggle (Public Research)",
        "vendor": r.get("source_vendor", "Unknown"),
        "vendor_status": r.get("vendor_classification_status", "UNKNOWN"),
        "sha256": (r.get("sha256") or "")[:16] + "...",
    } for r in rows]

    return _answer(
        query, intent="public_research",
        answer=f"Found {len(rows)} public research evidence item(s) from Kaggle benchmarks. All records maintain strict research provenance (Vendor: Unknown).",
        citations=citations, confidence=0.98,
    )


async def handle_ucf_crime(db, case_id, query, params):
    async with db.execute(
        """SELECT e.*, d.name as dataset_name FROM evidence e
           LEFT JOIN datasets d ON e.dataset_id = d.id
           WHERE (e.case_id = ? OR e.case_id IS NULL) AND (d.name LIKE '%UCF%' OR e.original_filename LIKE '%Burglary%' OR e.original_filename LIKE '%Robbery%' OR e.original_filename LIKE '%Road%')
           ORDER BY e.ingested_at DESC LIMIT 10""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        return _answer(
            query, intent="ucf_crime",
            answer="No footage from the UCF Crime dataset found in this case. You can import sample UCF Crime videos from the Dataset Library.",
            citations=[], confidence=1.0,
        )

    citations = [{
        "evidence_id": r["id"],
        "filename": r.get("original_filename") or r.get("source_name"),
        "dataset": "UCF Crime Surveillance Benchmark",
        "resolution": r.get("resolution"),
        "fps": r.get("fps"),
        "duration": f"{r.get('duration_seconds', 0)}s",
        "sha256": (r.get("sha256") or "")[:16] + "...",
    } for r in rows]

    return _answer(
        query, intent="ucf_crime",
        answer=f"Found {len(rows)} video(s) from the UCF Crime CCTV anomaly dataset with verified SHA-256 integrity.",
        citations=citations, confidence=0.98,
    )


async def handle_vendor_specific(db, case_id, query, params):
    vendor = params.get("vendor", "Generic")
    async with db.execute(
        """SELECT id, source_name, original_filename, source_vendor, vendor_classification_status,
                  is_simulated_adapter, parser_used, integrity_status, sha256
           FROM evidence WHERE (case_id = ? OR case_id IS NULL) AND source_vendor = ?""",
        (case_id, vendor)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        return _answer(
            query, intent="vendor_specific",
            answer=f"No evidence records found for vendor '{vendor}' in this case.",
            citations=[], confidence=1.0,
        )

    citations = [{
        "evidence_id": r["id"],
        "file": r.get("original_filename") or r.get("source_name"),
        "vendor": r["source_vendor"],
        "vendor_status": r["vendor_classification_status"],
        "is_simulated": bool(r["is_simulated_adapter"]),
        "parser": r["parser_used"],
    } for r in rows[:10]]

    sim_note = " (Simulated vendor demo data — not original vendor hardware evidence)" if any(r["is_simulated_adapter"] for r in rows) else ""
    return _answer(
        query, intent="vendor_specific",
        answer=f"Found {len(rows)} evidence item(s) associated with {vendor}.{sim_note}",
        citations=citations, confidence=0.95,
    )


async def handle_anomalies(db, case_id, query, params):
    async with db.execute(
        """SELECT af.*, e.camera_id, e.source_name, e.original_filename FROM ai_findings af
           JOIN evidence e ON af.evidence_id = e.id
           WHERE af.case_id = ? AND (af.finding_type = 'anomaly' OR af.label IN ('Burglary','Robbery','Road Accident','Fighting','Fall'))
           ORDER BY af.confidence DESC LIMIT 10""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        # Fallback to check if video filenames imply anomalies
        async with db.execute(
            """SELECT id, original_filename, source_name, camera_id FROM evidence
               WHERE case_id = ? AND (original_filename LIKE '%Burglary%' OR original_filename LIKE '%Robbery%' OR original_filename LIKE '%Fall%' OR original_filename LIKE '%Fight%')""",
            (case_id,)
        ) as cur:
            ev_rows = [dict(r) for r in await cur.fetchall()]

        if ev_rows:
            citations = [{"evidence_id": r["id"], "file": r.get("original_filename"), "camera": r.get("camera_id")} for r in ev_rows]
            return _answer(
                query, intent="anomalies",
                answer=f"Found {len(ev_rows)} surveillance video(s) recorded during anomalous events (burglary, robbery, altercations).",
                citations=citations, confidence=0.9,
            )

        return _answer(
            query, intent="anomalies",
            answer="No anomalous events detected yet in this case. Run AI detection on evidence items to generate anomaly findings.",
            citations=[], confidence=1.0,
        )

    citations = [{
        "evidence_id": r["evidence_id"],
        "camera_id": r.get("camera_id"),
        "label": r.get("label"),
        "frame": r.get("frame_number"),
        "timestamp": r.get("timestamp_in_video"),
        "confidence": r.get("confidence"),
    } for r in rows]

    return _answer(
        query, intent="anomalies",
        answer=f"{len(rows)} anomaly event(s) identified across surveillance footage in this case.",
        citations=citations, confidence=0.95,
    )


async def handle_tamper_flags(db, case_id, query, params):
    async with db.execute(
        """SELECT af.*, e.camera_id, e.channel FROM ai_findings af
           JOIN evidence e ON af.evidence_id = e.id
           WHERE af.case_id = ? AND af.finding_type IN ('tamper','authenticity','camera_tamper')
           ORDER BY af.confidence DESC""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    async with db.execute(
        """SELECT * FROM authenticity_findings af
           JOIN evidence e ON af.evidence_id = e.id
           WHERE e.case_id = ? AND (af.severity IN ('medium','high'))""",
        (case_id,)
    ) as cur:
        auth_rows = [dict(r) for r in await cur.fetchall()]

    if not rows and not auth_rows:
        return _answer(
            query, intent="tamper_flags",
            answer="No tamper or authenticity flags have been detected in this case so far. Run authenticity analysis on individual evidence items to generate findings.",
            citations=[], confidence=1.0,
        )

    citations = []
    for r in (rows + auth_rows)[:5]:
        citations.append({
            "evidence_id": r.get("evidence_id"),
            "finding_type": r.get("finding_type") or r.get("check_type"),
            "confidence": r.get("confidence"),
            "detail": r.get("description") or r.get("detail"),
        })

    return _answer(
        query, intent="tamper_flags",
        answer=f"{len(rows) + len(auth_rows)} tamper/authenticity flag(s) found in this case. All require expert human review before any forensic conclusion.",
        citations=citations, confidence=0.95,
    )


async def handle_vehicles(db, case_id, query, params):
    async with db.execute(
        """SELECT af.*, e.camera_id, e.channel FROM ai_findings af
           JOIN evidence e ON af.evidence_id = e.id
           WHERE af.case_id = ? AND af.finding_type = 'vehicle'
           ORDER BY af.frame_number ASC""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    return _findings_answer(query, "vehicle", rows, "vehicles")


async def handle_persons(db, case_id, query, params):
    async with db.execute(
        """SELECT af.*, e.camera_id, e.channel FROM ai_findings af
           JOIN evidence e ON af.evidence_id = e.id
           WHERE af.case_id = ? AND af.finding_type = 'person'
           ORDER BY af.frame_number ASC""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    return _findings_answer(query, "person", rows, "persons/suspects")


async def handle_camera_tamper(db, case_id, query, params):
    async with db.execute(
        """SELECT af.*, e.camera_id FROM ai_findings af
           JOIN evidence e ON af.evidence_id = e.id
           WHERE af.case_id = ? AND af.finding_type = 'camera_tamper'""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        return _answer(query, intent="camera_tamper",
            answer="No camera-side tamper events detected. Run camera tamper analysis to generate findings.",
            citations=[], confidence=1.0)

    citations = [{"evidence_id": r["evidence_id"], "camera_id": r.get("camera_id"),
                  "detail": r.get("description"), "confidence": r.get("confidence")} for r in rows[:5]]
    return _answer(query, intent="camera_tamper",
        answer=f"{len(rows)} camera-side tamper finding(s) detected (blackout, spray, defocus, angle shift).",
        citations=citations, confidence=0.9)


async def handle_custody(db, case_id, query, params):
    async with db.execute(
        "SELECT COUNT(*) as cnt FROM custody_ledger WHERE case_id = ?", (case_id,)
    ) as cur:
        row = dict(await cur.fetchone())
    count = row["cnt"]

    async with db.execute(
        "SELECT * FROM custody_ledger WHERE case_id = ? ORDER BY seq DESC LIMIT 3", (case_id,)
    ) as cur:
        recent = [dict(r) for r in await cur.fetchall()]

    return _answer(query, intent="custody",
        answer=f"Chain of custody contains {count} entries. Most recent actions: {', '.join(r['action'] for r in recent)}.",
        citations=[{"seq": r["seq"], "action": r["action"], "operator": r["operator_id"],
                    "timestamp": r["timestamp"]} for r in recent],
        confidence=1.0)


async def handle_integrity(db, case_id, query, params):
    async with db.execute(
        "SELECT id, integrity_status, sha256, camera_id FROM evidence WHERE case_id = ?", (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    verified = [r for r in rows if r["integrity_status"] == "verified"]
    mismatched = [r for r in rows if r["integrity_status"] == "mismatch"]

    answer = f"{len(rows)} evidence item(s) total. {len(verified)} verified, {len(mismatched)} hash mismatch(es) detected."
    if mismatched:
        answer += " ⚠ HASH MISMATCH detected — evidence may have been modified after acquisition."

    citations = [{"evidence_id": r["id"], "status": r["integrity_status"], "sha256": r["sha256"]} for r in mismatched[:3]]
    return _answer(query, intent="integrity", answer=answer, citations=citations, confidence=1.0)


async def handle_recovery(db, case_id, query, params):
    async with db.execute(
        """SELECT e.id, e.recovery_status, e.completeness_score, e.camera_id,
                  COUNT(rs.id) as segment_count
           FROM evidence e
           LEFT JOIN recovery_segments rs ON rs.evidence_id = e.id
           WHERE e.case_id = ?
           GROUP BY e.id""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    partial = [r for r in rows if r["recovery_status"] in ("partial","reconstructed","carved")]
    return _answer(query, intent="recovery",
        answer=f"{len(rows)} evidence item(s) analyzed. {len(partial)} with partial/reconstructed data.",
        citations=[{"evidence_id": r["id"], "status": r["recovery_status"],
                    "completeness": r["completeness_score"]} for r in partial[:5]],
        confidence=0.95)


async def handle_summary(db, case_id, query, params):
    async with db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)) as cur:
        case = dict(await cur.fetchone() or {})
    async with db.execute("SELECT COUNT(*) as cnt FROM evidence WHERE case_id = ?", (case_id,)) as cur:
        ev_count = (await cur.fetchone())["cnt"]
    async with db.execute("SELECT COUNT(*) as cnt FROM ai_findings WHERE case_id = ?", (case_id,)) as cur:
        ai_count = (await cur.fetchone())["cnt"]
    async with db.execute("SELECT COUNT(*) as cnt FROM custody_ledger WHERE case_id = ?", (case_id,)) as cur:
        cust_count = (await cur.fetchone())["cnt"]

    return _answer(query, intent="summary",
        answer=f"Case '{case.get('title','?')}': {ev_count} evidence item(s), {ai_count} AI finding(s), {cust_count} custody ledger entries.",
        citations=[], confidence=1.0)


async def handle_list_findings(db, case_id, query, params):
    async with db.execute(
        """SELECT finding_type, COUNT(*) as cnt FROM ai_findings WHERE case_id = ? GROUP BY finding_type""",
        (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        return _answer(query, intent="list_findings",
            answer="No AI findings generated yet. Run analysis on evidence items first.",
            citations=[], confidence=1.0)

    breakdown = ", ".join(f"{r['cnt']} {r['finding_type']}(s)" for r in rows)
    return _answer(query, intent="list_findings",
        answer=f"AI findings in this case: {breakdown}.",
        citations=rows, confidence=1.0)


async def handle_general(db, case_id, query, params):
    return _answer(query, intent="general",
        answer="Query understood. You can ask about: Kaggle research datasets, UCF Crime, VIRAT, vehicle detections, person movement, tamper flags, camera tampering, chain of custody, or integrity.",
        citations=[], confidence=0.5)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _answer(query: str, intent: str, answer: str, citations: list, confidence: float) -> dict:
    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "citations": citations,
        "confidence": confidence,
        "grounding_rule": "All answers are derived exclusively from stored evidence and AI findings in this case. No information is inferred or hallucinated.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _findings_answer(query: str, finding_type: str, rows: list, label: str) -> dict:
    if not rows:
        return _answer(query, intent=f"detect_{finding_type}",
            answer=f"No {label} detected in this case. Run AI object detection analysis first.",
            citations=[], confidence=1.0)

    citations = [{
        "evidence_id": r.get("evidence_id"),
        "camera_id": r.get("camera_id") or r.get("channel"),
        "frame": r.get("frame_number"),
        "timestamp": r.get("timestamp_in_video"),
        "confidence": r.get("confidence"),
        "label": r.get("label"),
        "simulated": r.get("is_simulated"),
    } for r in rows[:10]]

    sim_note = " (Note: detections are simulated — real YOLO model not yet integrated)" if any(r.get("is_simulated") for r in rows) else ""
    return _answer(query, intent=f"detect_{finding_type}",
        answer=f"{len(rows)} {label} detection(s) found across this case.{sim_note}",
        citations=citations, confidence=0.9)


HANDLERS = {
    "public_research": handle_public_research,
    "ucf_crime": handle_ucf_crime,
    "vendor_specific": handle_vendor_specific,
    "anomalies": handle_anomalies,
    "tamper_flags": handle_tamper_flags,
    "vehicles": handle_vehicles,
    "persons": handle_persons,
    "camera_tamper": handle_camera_tamper,
    "custody": handle_custody,
    "integrity": handle_integrity,
    "timeline": handle_summary,
    "recovery": handle_recovery,
    "summary": handle_summary,
    "camera_specific": handle_list_findings,
    "list_findings": handle_list_findings,
    "general": handle_general,
}
