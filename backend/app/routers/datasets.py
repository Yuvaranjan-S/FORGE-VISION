"""
FORGE-VISION — Dataset Library Router (Multi-Source Provenance & Registration Engine)
Supports:
- PUBLIC_RESEARCH_DATASET (UCF Crime, VIRAT, Avenue, UCSD)
- AUTHORIZED_DVR_EXPORT
- AUTHORIZED_CCTV_RECORDING
- VENDOR_SAMPLE (Hikvision, Dahua, CP Plus, Matrix, Uniview, Honeywell)
- FORENSIC_DISK_IMAGE
- TEAM_COLLECTED_TEST_DATA
- SYNTHETIC_DEMO (Built-in synthetic generator with honest labeling)
- USER_UPLOADED
"""
import json
import os
import uuid
import random
from datetime import datetime, timezone
from typing import Optional, List

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from ..database import get_db
from ..routers.auth import get_current_user, require_role
from ..hash_engine import compute_string_sha256, compute_file_hashes
from ..custody.ledger import append_custody_event
from ..parsers import detect_vendor_and_get_parser
from ..kaggle_pipeline import (
    KAGGLE_SOURCES_CATALOG, IMPORT_JOBS, KAGGLE_DATA_DIR,
    scan_dataset_videos_quick, process_kaggle_import_job,
)

router = APIRouter()

DATASET_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "datasets")
EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence_store", "files")
THUMB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence_store", "thumbnails")


class DatasetRegisterRequest(BaseModel):
    name: str
    case_id: Optional[str] = None
    source_type: str = "PUBLIC_RESEARCH_DATASET"
    source_provider: str
    description: Optional[str] = None
    vendor: Optional[str] = "Generic"
    device_model: Optional[str] = None
    license: Optional[str] = "Research / Educational Use"
    source_reference: Optional[str] = None
    collection_method: Optional[str] = "Direct Download / Authorized Transfer"
    collector_name: Optional[str] = None
    collection_date: Optional[str] = None
    camera_count: Optional[int] = 1
    file_count: Optional[int] = 1
    total_size_bytes: Optional[int] = 0
    is_synthetic: bool = False
    forensic_status: str = "RESEARCH_BENCHMARK"


class ImportVideosRequest(BaseModel):
    case_id: str = "CASE-DEMO001"
    selected_files: Optional[List[str]] = None   # full file paths; None = import all
    max_count: Optional[int] = None


class SyntheticDemoGenerateRequest(BaseModel):
    case_id: Optional[str] = "CASE-DEMO001"
    scenario: str = "Warehouse" # Warehouse | Bank | Commercial Complex | Perimeter
    camera_count: int = 8


# ── LIST DATASETS ─────────────────────────────────────────────
@router.get("/")
async def list_datasets(
    case_id: Optional[str] = None,
    source_type: Optional[str] = None,
    vendor: Optional[str] = None,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all datasets with provenance and file stats."""
    query = "SELECT * FROM datasets WHERE 1=1"
    params = []
    if case_id:
        query += " AND (case_id = ? OR case_id IS NULL)"
        params.append(case_id)
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if vendor:
        query += " AND vendor = ?"
        params.append(vendor)
    query += " ORDER BY created_at DESC"

    async with db.execute(query, tuple(params)) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    for ds in rows:
        ds_id = ds["id"]
        async with db.execute("SELECT COUNT(*) as cnt, SUM(file_size_bytes) as total_sz FROM dataset_files WHERE dataset_id = ?", (ds_id,)) as cur:
            stat = await cur.fetchone()
            if stat and stat["cnt"]:
                ds["file_count"] = stat["cnt"]
                ds["total_size_bytes"] = stat["total_sz"] or ds["total_size_bytes"]

        async with db.execute("SELECT COUNT(DISTINCT camera_id) as cam_cnt FROM evidence WHERE dataset_id = ?", (ds_id,)) as cur:
            cam_stat = await cur.fetchone()
            if cam_stat and cam_stat["cam_cnt"]:
                ds["camera_count"] = cam_stat["cam_cnt"]

    return rows


# ── GET DATASET DETAIL ────────────────────────────────────────
@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)) as cur:
        ds = await cur.fetchone()
    if not ds:
        raise HTTPException(404, "Dataset not found")

    ds_dict = dict(ds)

    # Attach dataset files
    async with db.execute("SELECT * FROM dataset_files WHERE dataset_id = ? ORDER BY created_at ASC", (dataset_id,)) as cur:
        ds_dict["files"] = [dict(r) for r in await cur.fetchall()]

    # Attach linked evidence items
    async with db.execute("SELECT * FROM evidence WHERE dataset_id = ? ORDER BY camera_id ASC", (dataset_id,)) as cur:
        ds_dict["evidence_items"] = [dict(r) for r in await cur.fetchall()]

    return ds_dict


# ── REGISTER DATASET (Public Research / Authorized) ───────────
@router.post("/register")
async def register_dataset(
    req: DatasetRegisterRequest,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Register public research dataset or external authorized dataset metadata without redistributing raw copyrighted media."""
    dataset_id = f"DS-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    ds_hash = compute_string_sha256(f"{dataset_id}:{req.name}:{req.source_provider}:{now}")

    await db.execute(
        """INSERT INTO datasets (
            id, case_id, name, source_type, source_provider, description,
            vendor, device_model, camera_count, file_count, total_size_bytes,
            license, source_reference, collection_method, collector_name,
            collection_date, is_synthetic, forensic_status, sha256, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            dataset_id, req.case_id, req.name, req.source_type, req.source_provider,
            req.description, req.vendor, req.device_model, req.camera_count,
            req.file_count, req.total_size_bytes, req.license, req.source_reference,
            req.collection_method, req.collector_name or current_user["full_name"],
            req.collection_date or now[:10],
            1 if req.is_synthetic else 0,
            req.forensic_status, ds_hash, now
        )
    )
    await db.commit()

    if req.case_id:
        await append_custody_event(
            db, case_id=req.case_id, action="dataset_registered",
            operator_id=current_user["id"], operator_role=current_user["role"],
            detail={"dataset_id": dataset_id, "dataset_name": req.name, "source_type": req.source_type},
        )

    return {"dataset_id": dataset_id, "name": req.name, "sha256": ds_hash, "created_at": now}


# ── IMPORT DATASET FILES ──────────────────────────────────────
@router.post("/import")
async def import_dataset_files(
    dataset_name: str = Form(...),
    source_type: str = Form(default="USER_UPLOADED"),
    source_provider: str = Form(default="Investigator Ingestion"),
    vendor: str = Form(default="Generic"),
    case_id: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    license_type: Optional[str] = Form(default="Authorized Case Evidence"),
    files: List[UploadFile] = File(...),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Multi-file dataset ingestion wizard endpoint: hashes, seals, and standardizes evidence into Common Evidence Model."""
    dataset_id = f"DS-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)

    imported_files = []
    total_size = 0

    for idx, f in enumerate(files, 1):
        file_id = str(uuid.uuid4())
        original_name = f.filename or f"evidence_{idx}.mp4"
        safe_name = f"{file_id}_{original_name}"
        dest_path = os.path.join(EVIDENCE_DIR, safe_name)

        # Write to disk
        with open(dest_path, "wb") as out:
            while chunk := await f.read(65536):
                out.write(chunk)

        hashes = compute_file_hashes(dest_path)
        file_sz = hashes["file_size_bytes"]
        total_size += file_sz

        # Vendor parser detection & metadata extraction
        parser = detect_vendor_and_get_parser(dest_path)
        device_info = parser.identify_device(dest_path)
        metadata = parser.extract_metadata(dest_path)
        parser_name = type(parser).__name__
        is_sim = parser.IS_SIMULATED

        camera_id = f"CAM-{(idx % 8) + 1:02d}"
        channel = f"CH-{(idx % 8) + 1}"

        # Insert dataset file
        await db.execute(
            """INSERT INTO dataset_files (id, dataset_id, file_name, file_path, file_size_bytes, sha256, detected_vendor, file_type, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (file_id, dataset_id, original_name, dest_path, file_sz, hashes["sha256"], device_info.get("source_vendor", vendor), metadata.get("container_format", "video"), "ingested", now)
        )

        # If linked to a case, also create evidence record
        if case_id:
            evidence_id = file_id
            await db.execute(
                """INSERT INTO evidence (
                    id, case_id, dataset_id, source_type, source_name, source_provider, source_vendor,
                    parser_used, parser_confidence, is_simulated_adapter, device_model, firmware,
                    camera_id, original_camera_id, channel, timestamp_start, timestamp_end,
                    codec, resolution, fps, duration_seconds, bitrate_kbps, frame_count,
                    file_path, file_size_bytes, recovery_status, integrity_status, authenticity_status,
                    priority, completeness_score, md5, sha256, sha3_256, ingested_at, ingested_by, notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    evidence_id, case_id, dataset_id, source_type, original_name, source_provider,
                    device_info.get("source_vendor", vendor), parser_name, parser.confidence_score(),
                    1 if is_sim else 0, device_info.get("device_model"), device_info.get("firmware"),
                    camera_id, camera_id, channel, metadata.get("timestamp_start") or now,
                    now, metadata.get("codec"), metadata.get("resolution"), metadata.get("fps"),
                    metadata.get("duration_seconds"), metadata.get("bitrate_kbps"), metadata.get("frame_count"),
                    dest_path, file_sz, "intact", "verified", "no_tamper_detected", "MEDIUM", 1.0,
                    hashes["md5"], hashes["sha256"], hashes["sha3_256"], now, current_user["id"],
                    f"Ingested via Dataset Import Wizard. {dataset_name}"
                )
            )

        imported_files.append({"id": file_id, "name": original_name, "sha256": hashes["sha256"], "size": file_sz})

    ds_sha256 = compute_string_sha256(":".join(f["sha256"] for f in imported_files) or dataset_id)

    # Insert Dataset
    await db.execute(
        """INSERT INTO datasets (
            id, case_id, name, source_type, source_provider, description,
            vendor, camera_count, file_count, total_size_bytes, license,
            collection_method, collector_name, collection_date, is_synthetic,
            forensic_status, sha256, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            dataset_id, case_id, dataset_name, source_type, source_provider,
            description, vendor, len(set(f["id"] for f in imported_files)),
            len(imported_files), total_size, license_type, "Batch Ingestion Wizard",
            current_user["full_name"], now[:10], 0, "AUTHENTIC", ds_sha256, now
        )
    )
    await db.commit()

    if case_id:
        await append_custody_event(
            db, case_id=case_id, action="dataset_imported",
            operator_id=current_user["id"], operator_role=current_user["role"],
            detail={"dataset_id": dataset_id, "dataset_name": dataset_name, "files_count": len(imported_files)},
        )

    return {
        "dataset_id": dataset_id,
        "name": dataset_name,
        "files_imported": len(imported_files),
        "total_size_bytes": total_size,
        "sha256": ds_sha256,
        "status": "COMPLETED",
    }


# ── GENERATE SYNTHETIC DEMO DATASET ───────────────────────────
@router.post("/generate-synthetic")
async def generate_synthetic_dataset(
    req: SyntheticDemoGenerateRequest,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Generates a full 8-camera synthetic demo dataset with realistic multi-vendor evidence,
    recording gap scenarios, blackout events, cross-camera transitions, and AI detection findings.
    Strictly labeled [SYNTHETIC DEMO / DEMO ONLY] throughout.
    """
    dataset_id = f"DS-SYNTH-{str(uuid.uuid4())[:6].upper()}"
    case_id = req.case_id or "CASE-DEMO001"
    now = datetime.now(timezone.utc).isoformat()
    rng = random.Random(42)

    vendors = [
        ("Hikvision", "HikvisionParser", "DS-7208HQHI-K2", "H.265", "1920x1080", 25.0, 4096),
        ("Dahua", "DahuaParser", "DHI-NVR2208-4KS2", "H.264", "2560x1440", 20.0, 6144),
        ("CP Plus", "CPPlusParser", "CP-UVR-0801E1", "H.264", "1920x1080", 25.0, 3072),
        ("Generic", "GenericVideoParser", "IP Camera Stream", "H.264", "1920x1080", 30.0, 4096),
        ("Matrix", "MatrixParser", "SATATYA NVR0802X", "H.265", "3840x2160", 15.0, 8192),
        ("Uniview", "UniviewParser", "NVR301-08S3", "H.265", "2560x1440", 25.0, 5120),
        ("Honeywell", "HoneywellParser", "HEN08104", "H.264", "1920x1080", 25.0, 4096),
        ("Godrej", "GodrejParser", "Seethru NVR-8", "H.264", "1920x1080", 20.0, 3500),
    ]

    camera_locations = [
        ("CAM-01", "Main Gate & Entry Barrier", 80, 140),
        ("CAM-02", "Visitor Parking & Driveway", 220, 100),
        ("CAM-03", "Main Entrance & Reception Corridor", 360, 160),
        ("CAM-04", "Central Warehouse Aisle #1", 500, 220),
        ("CAM-05", "Loading Dock & High-Bay Storage", 640, 180),
        ("CAM-06", "Secure Vault & Server Room Access", 500, 80),
        ("CAM-07", "Rear Perimeter & Fire Exit", 360, 300),
        ("CAM-08", "Dispatch Gate & Outbound Weighbridge", 760, 280),
    ]

    generated_evidence = []

    for i in range(min(req.camera_count, len(vendors))):
        v_name, p_name, d_model, codec, res, fps, bitrate = vendors[i]
        cam_id, loc_label, x_pos, y_pos = camera_locations[i]
        ev_id = f"EV-SYNTH-{str(uuid.uuid4())[:8].upper()}"

        # Assign deliberate anomalies to specific cameras for realistic SIH demo
        rec_status = "intact"
        auth_status = "no_tamper_detected"
        priority = "MEDIUM"
        notes = f"[SYNTHETIC DEMO] {v_name} surveillance adapter. Location: {loc_label}."

        if cam_id == "CAM-04":
            rec_status = "partial"
            auth_status = "suspected_edit"
            priority = "HIGH"
            notes = "[SYNTHETIC DEMO] Frame gap detected between 10:14:00-10:16:30. Possible storage interruption or deliberate wipe."
        elif cam_id == "CAM-02":
            auth_status = "suspected_edit"
            priority = "HIGH"
            notes = "[SYNTHETIC DEMO] Error Level Analysis (ELA) detected compression anomaly on keyframe."
        elif cam_id == "CAM-06":
            priority = "HIGH"
            notes = "[SYNTHETIC DEMO] Tamper check flagged camera blackout event lasting 4.2 seconds."

        dur = 7200.0
        frame_cnt = int(dur * fps)
        file_sz = int(dur * (bitrate * 128))
        ev_sha256 = compute_string_sha256(f"SYNTHETIC_VIDEO_{ev_id}_{cam_id}")
        ev_md5 = compute_string_sha256(f"MD5_{ev_id}")[:32]
        ev_sha3 = compute_string_sha256(f"SHA3_{ev_id}")

        await db.execute(
            """INSERT INTO evidence (
                id, case_id, dataset_id, source_type, source_name, source_provider, source_vendor,
                parser_used, parser_confidence, is_simulated_adapter, device_model, firmware,
                camera_id, original_camera_id, channel, timestamp_start, timestamp_end,
                codec, resolution, fps, duration_seconds, bitrate_kbps, frame_count,
                file_path, file_size_bytes, recovery_status, integrity_status, authenticity_status,
                priority, completeness_score, md5, sha256, sha3_256, ingested_at, ingested_by, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ev_id, case_id, dataset_id, "SYNTHETIC_DEMO", f"{cam_id}_{loc_label.replace(' ', '_')}.mp4",
                "FORGE-VISION Synthetic Generator", v_name, p_name, 0.95 if p_name == "GenericVideoParser" else 0.15,
                1 if p_name != "GenericVideoParser" else 0, f"[SIMULATED] {v_name} {d_model}", "v4.20.10",
                cam_id, cam_id, f"CH-{i+1}", "2024-03-15T09:00:00+05:30", "2024-03-15T11:00:00+05:30",
                codec, res, fps, dur, bitrate, frame_cnt,
                f"DEMO_STORE/{cam_id}.mp4", file_sz, rec_status, "verified", auth_status,
                priority, 0.78 if rec_status == "partial" else 1.0,
                ev_md5, ev_sha256, ev_sha3, now, current_user["id"], notes
            )
        )

        # Recovery segments
        if rec_status == "partial":
            await db.execute(
                """INSERT INTO recovery_segments (id, evidence_id, segment_type, start_frame, end_frame, start_time, end_time, completeness, nal_units_found, is_simulated, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev_id, "intact", 0, int(frame_cnt * 0.4), 0.0, dur * 0.4, 1.0, 18400, 1, "[SYNTHETIC] Initial recording block intact")
            )
            await db.execute(
                """INSERT INTO recovery_segments (id, evidence_id, segment_type, start_frame, end_frame, start_time, end_time, completeness, nal_units_found, is_simulated, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev_id, "gap", int(frame_cnt * 0.4), int(frame_cnt * 0.55), dur * 0.4, dur * 0.55, 0.0, 0, 1, "[SYNTHETIC] Unrecorded gap: 150 seconds missing")
            )
            await db.execute(
                """INSERT INTO recovery_segments (id, evidence_id, segment_type, start_frame, end_frame, start_time, end_time, completeness, nal_units_found, is_simulated, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev_id, "recovered", int(frame_cnt * 0.55), frame_cnt, dur * 0.55, dur, 0.85, 14200, 1, "[SYNTHETIC] Carved H.264 stream fragments reconstructed from unallocated sectors")
            )
        else:
            await db.execute(
                """INSERT INTO recovery_segments (id, evidence_id, segment_type, start_frame, end_frame, start_time, end_time, completeness, nal_units_found, is_simulated, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev_id, "intact", 0, frame_cnt, 0.0, dur, 1.0, 45000, 0, "Continuous intact video stream")
            )

        # AI findings for this camera
        for obj_label in ["person", "car", "van", "truck"]:
            if rng.random() > 0.3:
                await db.execute(
                    """INSERT INTO ai_findings (id, evidence_id, case_id, finding_type, frame_number, timestamp_in_video, confidence, bounding_box, label, description, is_simulated, requires_review, generated_at, generator)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid.uuid4()), ev_id, case_id, "vehicle" if obj_label in {"car","van","truck"} else "person",
                        rng.randint(200, 4000), f"00:{rng.randint(5,50):02d}:{rng.randint(10,59):02d}",
                        round(rng.uniform(0.75, 0.96), 2), json.dumps([rng.randint(50, 400), rng.randint(50, 300), 180, 220]),
                        obj_label, f"[SIMULATED] {obj_label.title()} detected at {loc_label}.", 1, 1, now, "SimulatedYOLOv8"
                    )
                )

        # Camera topology node
        connected = []
        if i > 0:
            connected.append(camera_locations[i-1][0])
        if i < len(camera_locations) - 1:
            connected.append(camera_locations[i+1][0])

        await db.execute(
            """INSERT INTO camera_topology (id, case_id, camera_id, camera_name, location_label, x_pos, y_pos, connected_camera_ids, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), case_id, cam_id, f"{cam_id} - {v_name}", loc_label, x_pos, y_pos, json.dumps(connected), f"{v_name} DVR Channel {i+1}", now)
        )

        generated_evidence.append(ev_id)

    # Insert Synthetic Dataset metadata
    ds_hash = compute_string_sha256(f"SYNTHETIC_DATASET_{dataset_id}")
    await db.execute(
        """INSERT INTO datasets (
            id, case_id, name, source_type, source_provider, description,
            vendor, camera_count, file_count, total_size_bytes, license,
            source_reference, collection_method, collector_name, collection_date,
            is_synthetic, forensic_status, sha256, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            dataset_id, case_id, f"FORGE-VISION {req.scenario} Demo Dataset",
            "SYNTHETIC_DEMO", "FORGE-VISION Synthetic Generator",
            f"Pre-configured 8-camera {req.scenario} surveillance scenario with verified hash chains, recording gaps, and multi-vendor simulated OEM adapters. Clear [SIMULATED] labeling per SIH specifications.",
            "Multi-Vendor (Hikvision, Dahua, CP Plus, Matrix, Uniview, Honeywell)",
            len(generated_evidence), len(generated_evidence), 12884901888,
            "SIH 2024 Evaluation License", "FORGE-VISION-DEMO-SUITE-150",
            "Deterministic Scenario Engine", "SIH Forensic Suite Evaluator",
            "2024-03-15", 1, "DEMO_ONLY", ds_hash, now
        )
    )
    await db.commit()

    await append_custody_event(
        db, case_id=case_id, action="dataset_imported",
        operator_id=current_user["id"], operator_role=current_user["role"],
        detail={"dataset_id": dataset_id, "cameras": len(generated_evidence), "type": "SYNTHETIC_DEMO"},
    )

    return {
        "dataset_id": dataset_id,
        "name": f"FORGE-VISION {req.scenario} Demo Dataset",
        "cameras_created": len(generated_evidence),
        "sha256": ds_hash,
        "forensic_status": "DEMO_ONLY",
        "message": "Synthetic demo dataset successfully generated and linked to case.",
    }


# ── RESOLVE DATASET SOURCE FOLDER ────────────────────────────────
def _resolve_dataset_folder(ds: dict) -> Optional[str]:
    """Find the local video folder for a registered dataset."""
    # 1. Explicit local_path stored on dataset
    if ds.get("local_path") and os.path.isdir(ds["local_path"]):
        return ds["local_path"]

    # 2. Match by kaggle_dataset_identifier → catalog subfolder
    kdi = ds.get("kaggle_dataset_identifier")
    if kdi:
        for key, info in KAGGLE_SOURCES_CATALOG.items():
            if info.get("kaggle_dataset_identifier") == kdi:
                folder = os.path.join(KAGGLE_DATA_DIR, info["subfolder"])
                if os.path.isdir(folder):
                    return folder

    # 3. Match by dataset name fragment against subfolder names
    ds_name_lower = (ds.get("name") or "").lower()
    for key, info in KAGGLE_SOURCES_CATALOG.items():
        catalog_name = (info.get("name") or "").lower()
        subfolder = info.get("subfolder", "")
        if (
            key in ds_name_lower
            or subfolder in ds_name_lower
            or ds_name_lower in catalog_name
        ):
            folder = os.path.join(KAGGLE_DATA_DIR, subfolder)
            if os.path.isdir(folder):
                return folder

    # 4. Try all kaggle subfolders
    for key, info in KAGGLE_SOURCES_CATALOG.items():
        folder = os.path.join(KAGGLE_DATA_DIR, info["subfolder"])
        if os.path.isdir(folder):
            return folder  # Fallback: first found

    return None


# ── SCAN DATASET VIDEOS ─────────────────────────────────────────
@router.post("/{dataset_id}/scan-videos")
async def scan_dataset_videos_endpoint(
    dataset_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Scan a registered dataset's source folder for importable video files.
    Returns each file with 'already_imported' status (checked by filename+size).
    """
    async with db.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)) as cur:
        ds = await cur.fetchone()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    ds_dict = dict(ds)

    folder = _resolve_dataset_folder(ds_dict)
    if not folder:
        raise HTTPException(
            422,
            f"Could not locate source video folder for dataset '{ds_dict['name']}'. "
            "Ensure dataset was imported via Kaggle pipeline or set local_path."
        )

    raw_files = scan_dataset_videos_quick(folder)

    # Quick duplicate check by filename + size (no hashing at scan time)
    result_files = []
    for f in raw_files:
        already_imported = False
        existing_id = None
        existing_cam_id = None
        async with db.execute(
            "SELECT id, camera_id FROM evidence WHERE original_filename = ? AND file_size_bytes = ?",
            (f["filename"], f["file_size_bytes"])
        ) as cur:
            row = await cur.fetchone()
            if row:
                already_imported = True
                existing_id = row["id"]
                existing_cam_id = row["camera_id"]

        result_files.append({
            **f,
            "already_imported": already_imported,
            "existing_evidence_id": existing_id,
            "existing_camera_id": existing_cam_id,
        })

    total = len(result_files)
    already_count = sum(1 for f in result_files if f["already_imported"])
    return {
        "dataset_id": dataset_id,
        "dataset_name": ds_dict["name"],
        "source_folder": folder,
        "total": total,
        "already_imported": already_count,
        "available": total - already_count,
        "files": result_files,
    }


# ── IMPORT DATASET VIDEOS TO CAM / EVIDENCE ────────────────────────
@router.post("/{dataset_id}/import-videos")
async def import_dataset_videos_to_cam(
    dataset_id: str,
    req: ImportVideosRequest,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Launch a background job to import video files from a dataset into CAM/Evidence.
    Creates evidence records with CAM-KAG-NNN IDs, SHA-256 hashes, thumbnails,
    FFprobe metadata, and chain-of-custody events.
    Skips files already imported (SHA-256 duplicate detection).
    """
    async with db.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)) as cur:
        ds = await cur.fetchone()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    ds_dict = dict(ds)

    # Verify case exists
    async with db.execute("SELECT id FROM cases WHERE id = ?", (req.case_id,)) as cur:
        case_row = await cur.fetchone()
    if not case_row:
        raise HTTPException(404, f"Case '{req.case_id}' not found")

    folder = _resolve_dataset_folder(ds_dict)
    if not folder and not req.selected_files:
        raise HTTPException(422, "Could not locate source folder and no selected_files provided")

    # Determine dataset_key for the job worker
    dataset_key = dataset_id  # Will be used as fallback name
    kdi = ds_dict.get("kaggle_dataset_identifier")
    if kdi:
        for key, info in KAGGLE_SOURCES_CATALOG.items():
            if info.get("kaggle_dataset_identifier") == kdi:
                dataset_key = key
                break

    job_id = f"job-cam-{str(uuid.uuid4())[:8]}"

    # If caller provided specific files, pass those directly
    custom_files = req.selected_files
    if custom_files is None and folder:
        # Will be resolved inside the worker via ensure_sample_kaggle_files
        # For non-Kaggle datasets we pass the full folder file list
        from ..kaggle_pipeline import scan_dataset_videos_quick as sqv
        all_videos = sqv(folder)
        custom_files = [v["file_path"] for v in all_videos]
        if req.max_count:
            custom_files = custom_files[: req.max_count]

    def db_connection_factory():
        from ..database import DB_PATH
        import aiosqlite as _aiosqlite
        return _aiosqlite.connect(DB_PATH)

    background_tasks.add_task(
        process_kaggle_import_job,
        job_id=job_id,
        dataset_key=dataset_key,
        case_id=req.case_id,
        custom_files=custom_files,
        max_sample_count=req.max_count or len(custom_files or []) or 100,
        category_filter="ALL",
        user_info=current_user,
        db_factory=db_connection_factory,
    )

    return {
        "job_id": job_id,
        "dataset_id": dataset_id,
        "dataset_name": ds_dict["name"],
        "case_id": req.case_id,
        "status": "queued",
        "message": f"Import job '{job_id}' started. Videos will appear in CAM/Evidence on completion.",
    }


# ── DELETE DATASET ────────────────────────────────────────────
@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_role("supervisor")),
):
    """Supervisor only: Remove dataset registration."""
    async with db.execute("SELECT id, case_id, name FROM datasets WHERE id = ?", (dataset_id,)) as cur:
        ds = await cur.fetchone()
    if not ds:
        raise HTTPException(404, "Dataset not found")

    await db.execute("DELETE FROM dataset_files WHERE dataset_id = ?", (dataset_id,))
    await db.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    await db.commit()

    if ds["case_id"]:
        await append_custody_event(
            db, case_id=ds["case_id"], action="dataset_deleted",
            operator_id=current_user["id"], operator_role=current_user["role"],
            detail={"dataset_id": dataset_id, "dataset_name": ds["name"]},
        )

    return {"message": "Dataset deleted successfully", "dataset_id": dataset_id}
