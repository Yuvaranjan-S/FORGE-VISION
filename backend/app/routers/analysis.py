"""FORGE-VISION — Analysis router (authenticity, AI detection, motion, camera tamper)"""
import json
import os
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..routers.auth import get_current_user
from ..custody.ledger import append_custody_event
from ..validation.authenticity import run_full_authenticity_analysis
from ..ai_engine.analysis import (
    simulate_object_detection,
    detect_camera_tampering,
    generate_motion_heatmap,
    simulate_reid_hops,
)

router = APIRouter()

THUMB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence_store", "thumbnails")


@router.post("/{evidence_id}/authenticity")
async def run_authenticity(
    evidence_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)) as cur:
        ev = dict(await cur.fetchone() or {})
    if not ev:
        raise HTTPException(404, "Evidence not found")

    os.makedirs(THUMB_DIR, exist_ok=True)
    results = run_full_authenticity_analysis(
        file_path=ev["file_path"],
        evidence_id=evidence_id,
        thumbnail_dir=THUMB_DIR,
    )

    # Store authenticity findings
    for finding in results.get("findings", []):
        fid = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO authenticity_findings
               (id, evidence_id, check_type, frame_number, severity, confidence, detail, is_simulated, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fid, evidence_id,
             finding.get("check_type", "unknown"),
             finding.get("frame_number"),
             finding.get("severity", "low"),
             finding.get("confidence", 0.0),
             finding.get("detail", ""),
             1 if finding.get("is_simulated") else 0,
             datetime.now(timezone.utc).isoformat())
        )

    # Update evidence authenticity status
    await db.execute(
        "UPDATE evidence SET authenticity_status = ? WHERE id = ?",
        (results["authenticity_status"], evidence_id)
    )
    await db.commit()

    await append_custody_event(
        db, case_id=ev["case_id"], action="authenticity_analysis",
        operator_id=current_user["id"], operator_role=current_user["role"],
        evidence_id=evidence_id,
        detail={"status": results["authenticity_status"], "finding_count": results["finding_count"]},
    )
    return results


@router.post("/{evidence_id}/ai-detection")
async def run_ai_detection(
    evidence_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)) as cur:
        ev = dict(await cur.fetchone() or {})
    if not ev:
        raise HTTPException(404, "Evidence not found")

    frame_count = ev.get("frame_count") or 750
    fps = ev.get("fps") or 25.0
    findings = simulate_object_detection(evidence_id, frame_count, fps)

    case_id = ev["case_id"]
    for f in findings:
        await db.execute(
            """INSERT INTO ai_findings
               (id, evidence_id, case_id, finding_type, frame_number, timestamp_in_video,
                confidence, bounding_box, label, description, is_simulated, requires_review,
                linked_evidence_ids, generated_at, generator)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f["id"], evidence_id, case_id, f["finding_type"], f["frame_number"],
             f["timestamp_in_video"], f["confidence"],
             json.dumps(f.get("bounding_box", [])),
             f["label"], f["description"],
             1 if f["is_simulated"] else 0,
             1 if f["requires_review"] else 0,
             None, f["generated_at"], f["generator"])
        )
    await db.commit()

    await append_custody_event(
        db, case_id=case_id, action="ai_detection",
        operator_id=current_user["id"], operator_role=current_user["role"],
        evidence_id=evidence_id,
        detail={"findings_count": len(findings), "is_simulated": True},
    )
    return {"evidence_id": evidence_id, "findings_generated": len(findings), "findings": findings}


@router.post("/{evidence_id}/motion-heatmap")
async def run_motion_heatmap(
    evidence_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)) as cur:
        ev = dict(await cur.fetchone() or {})
    if not ev:
        raise HTTPException(404, "Evidence not found")

    os.makedirs(THUMB_DIR, exist_ok=True)
    output_path = os.path.join(THUMB_DIR, f"{evidence_id}_heatmap.jpg")
    result = generate_motion_heatmap(ev["file_path"], output_path)

    await append_custody_event(
        db, case_id=ev["case_id"], action="motion_heatmap",
        operator_id=current_user["id"], operator_role=current_user["role"],
        evidence_id=evidence_id,
        detail={"frames_analyzed": result.get("frames_analyzed", 0)},
    )
    return result


@router.post("/{evidence_id}/camera-tamper")
async def run_camera_tamper(
    evidence_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)) as cur:
        ev = dict(await cur.fetchone() or {})
    if not ev:
        raise HTTPException(404, "Evidence not found")

    result = detect_camera_tampering(ev["file_path"], evidence_id)
    case_id = ev["case_id"]

    for finding in result.get("camera_tamper_findings", []):
        fid = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO ai_findings
               (id, evidence_id, case_id, finding_type, confidence, label, description,
                is_simulated, requires_review, generated_at, generator)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, evidence_id, case_id, "camera_tamper",
             finding.get("confidence", 0.5),
             finding.get("tamper_type", "unknown"),
             finding.get("detail", ""),
             1 if finding.get("is_simulated") else 0,
             1, datetime.now(timezone.utc).isoformat(),
             "CameraTamperDetector")
        )
    await db.commit()

    await append_custody_event(
        db, case_id=case_id, action="camera_tamper_analysis",
        operator_id=current_user["id"], operator_role=current_user["role"],
        evidence_id=evidence_id,
        detail={"tamper_detected": result.get("tamper_detected"), "findings": result.get("total_findings")},
    )
    return result


@router.post("/case/{case_id}/cross-camera-reid")
async def run_cross_camera_reid(
    case_id: str,
    subject_label: str = "Suspect A",
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        "SELECT id as evidence_id, camera_id, timestamp_start FROM evidence WHERE case_id = ?", (case_id,)
    ) as cur:
        items = [dict(r) for r in await cur.fetchall()]

    if len(items) < 2:
        return {"message": "Cross-camera ReID requires at least 2 evidence items in the case.", "hops": []}

    hops = simulate_reid_hops(case_id, items, subject_label)

    for hop in hops:
        await db.execute(
            """INSERT INTO correlation_hops
               (id, case_id, subject_label, from_evidence_id, from_frame, from_timestamp,
                to_evidence_id, to_frame, to_timestamp, similarity_score, match_basis,
                is_simulated, disclaimer, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (hop["id"], case_id, hop["subject_label"],
             hop["from_evidence_id"], hop["from_frame"], hop["from_timestamp"],
             hop["to_evidence_id"], hop["to_frame"], hop["to_timestamp"],
             hop["similarity_score"], hop["match_basis"],
             1 if hop["is_simulated"] else 0,
             hop["disclaimer"], hop["created_at"])
        )
    await db.commit()

    await append_custody_event(
        db, case_id=case_id, action="cross_camera_reid",
        operator_id=current_user["id"], operator_role=current_user["role"],
        detail={"subject_label": subject_label, "hops_generated": len(hops), "is_simulated": True},
    )
    return {"subject_label": subject_label, "hops": hops, "hop_count": len(hops)}
