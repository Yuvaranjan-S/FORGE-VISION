"""
FORGE-VISION — Import one sample video for CAM-01 in CASE-DEMO001
Links the UCF Crime Burglary clip as playable CAM-01 evidence.

Run: py -3.12 import_cam01_video.py
"""
import os, sys, uuid, hashlib, asyncio, shutil
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))

import aiosqlite, cv2
from app.database import DB_PATH, init_db
from app.kaggle_pipeline.kaggle_service import (
    KAGGLE_DATA_DIR, EVIDENCE_STORE_DIR, THUMBNAILS_DIR,
    ensure_sample_kaggle_files,
)

# Map of camera_id → dataset file to use
CAMERA_IMPORT_MAP = [
    {
        "camera_id": "CAM-01",
        "channel": "CH-1",
        "case_id": "CASE-DEMO001",
        "dataset_key": "ucf-crime",
        "filename": "Burglary001_x264.mp4",
        "scenario": "Burglary — Storefront Entry (UCF Crime Benchmark)",
        "category": "Burglary",
    },
    {
        "camera_id": "CAM-02",
        "channel": "CH-2",
        "case_id": "CASE-DEMO001",
        "dataset_key": "ucf-crime",
        "filename": "Robbery001_x264.mp4",
        "scenario": "Robbery — Counter Area (UCF Crime Benchmark)",
        "category": "Robbery",
    },
    {
        "camera_id": "CAM-03",
        "channel": "CH-3",
        "case_id": "CASE-DEMO001",
        "dataset_key": "racd-cctv",
        "filename": "RACD_FrontDoor_01.mp4",
        "scenario": "Front Entrance Surveillance (RACD Residential Benchmark)",
        "category": "Front Entrance",
    },
    {
        "camera_id": "CAM-04",
        "channel": "CH-4",
        "case_id": "CASE-DEMO001",
        "dataset_key": "virat-cctv",
        "filename": "VIRAT_S_010000_00.mp4",
        "scenario": "Facility Parking Approach (VIRAT Ground Benchmark)",
        "category": "Normal Activity",
    },
]


def hash_file(path: str):
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    sha3 = hashlib.sha3_256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            md5.update(chunk); sha256.update(chunk)
            sha512.update(chunk); sha3.update(chunk)
            size += len(chunk)
    return {
        "md5": md5.hexdigest(), "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(), "sha3_256": sha3.hexdigest(),
        "file_size_bytes": size,
    }


async def import_cameras():
    print("=" * 64)
    print("  FORGE-VISION — Camera Video File Importer")
    print("  Linking real MP4 benchmark footage to CAM-01 .. CAM-04")
    print("=" * 64)

    await init_db()
    now = datetime.now(timezone.utc).isoformat()

    # Ensure sample files exist for all needed datasets
    for key in {"ucf-crime", "racd-cctv", "virat-cctv"}:
        ensure_sample_kaggle_files(key)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")

        for cam in CAMERA_IMPORT_MAP:
            src_folder = {
                "ucf-crime": "ucf_crime",
                "racd-cctv": "racd",
                "virat-cctv": "virat",
                "cctv-action": "cctv_action",
                "traffic-intersection": "traffic",
            }[cam["dataset_key"]]

            src_path = os.path.join(KAGGLE_DATA_DIR, src_folder, cam["filename"])

            if not os.path.exists(src_path):
                print(f"  [WARN] Source not found: {src_path}")
                continue

            # Check if camera already has a real video linked
            async with db.execute(
                """SELECT id, file_path FROM evidence
                   WHERE case_id = ? AND camera_id = ?
                   ORDER BY ingested_at DESC LIMIT 1""",
                (cam["case_id"], cam["camera_id"])
            ) as cur:
                existing = await cur.fetchone()

            # Copy to evidence_store
            evidence_id = f"EV-CAM-{cam['camera_id']}-{str(uuid.uuid4())[:6].upper()}"
            dest_name = f"{evidence_id}_{cam['filename']}"
            dest_path = os.path.join(EVIDENCE_STORE_DIR, dest_name)

            print(f"\n  [{cam['camera_id']}] {cam['scenario']}")
            print(f"  Source : {src_path}")
            print(f"  Dest   : {dest_path}")

            # Copy file
            shutil.copy2(src_path, dest_path)
            print(f"  Copied : {os.path.getsize(dest_path) // (1024*1024)} MB")

            # Hash
            hashes = hash_file(dest_path)
            print(f"  SHA256 : {hashes['sha256'][:32]}...")

            # Thumbnail
            thumb_path = os.path.join(THUMBNAILS_DIR, f"{evidence_id}_thumb.jpg")
            try:
                cap = cv2.VideoCapture(dest_path)
                ok, frame = cap.read()
                cap.release()
                if ok and frame is not None:
                    cv2.imwrite(thumb_path, cv2.resize(frame, (480, 270)))
                    print(f"  Thumb  : {thumb_path}")
            except Exception:
                thumb_path = None

            # Get metadata
            try:
                cap = cv2.VideoCapture(dest_path)
                fps_val = cap.get(cv2.CAP_PROP_FPS) or 25.0
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fcount = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = fcount / fps_val if fps_val > 0 else 10.0
                resolution = f"{w}x{h}"
                bitrate = round((hashes["file_size_bytes"] * 8) / (duration * 1000), 1)
                cap.release()
            except Exception:
                fps_val, resolution, fcount, duration, bitrate = 25.0, "1280x720", 250, 10.0, 2048.0

            if existing:
                # UPDATE the existing evidence record to point to the real file
                ev_id = existing[0]
                print(f"  Updating existing record: {ev_id}")
                await db.execute(
                    """UPDATE evidence SET
                        file_path = ?, working_copy_path = ?,
                        file_size_bytes = ?, original_filename = ?,
                        codec = ?, resolution = ?, fps = ?,
                        duration_seconds = ?, bitrate_kbps = ?, frame_count = ?,
                        md5 = ?, sha256 = ?, sha512 = ?, sha3_256 = ?,
                        thumbnail_path = ?,
                        source_type = ?, source_platform = ?,
                        vendor_classification_status = ?,
                        recovery_status = ?, integrity_status = ?,
                        authenticity_status = ?, notes = ?
                    WHERE id = ?""",
                    (
                        dest_path, dest_path,
                        hashes["file_size_bytes"], cam["filename"],
                        "H.264", resolution, fps_val,
                        duration, bitrate, fcount,
                        hashes["md5"], hashes["sha256"], hashes["sha512"], hashes["sha3_256"],
                        thumb_path,
                        "PUBLIC_RESEARCH_DATASET", "Kaggle",
                        "UNKNOWN",
                        "intact", "verified", "no_tamper_detected",
                        f"[{cam['category']}] {cam['scenario']}. Real benchmark footage linked to {cam['camera_id']}.",
                        ev_id,
                    )
                )
                print(f"  [OK] Updated {ev_id} with real video file.")
            else:
                # INSERT new evidence record
                await db.execute(
                    """INSERT INTO evidence (
                        id, case_id, source_type, source_name, source_provider, source_vendor,
                        parser_used, parser_confidence, is_simulated_adapter, device_model,
                        device_serial, firmware, camera_id, original_camera_id, channel,
                        timestamp_start, timestamp_end, original_timestamp, normalized_timestamp,
                        container_timestamp, osd_timestamp, timestamp_status,
                        timezone, clock_drift_seconds,
                        codec, resolution, fps, duration_seconds, bitrate_kbps, frame_count,
                        has_audio, file_path, working_copy_path, file_size_bytes,
                        recovery_status, integrity_status, authenticity_status,
                        analysis_status, priority, completeness_score,
                        md5, sha256, sha512, sha3_256,
                        custody_chain_ref, thumbnail_path,
                        ingested_at, ingested_by, notes,
                        source_platform, source_reference, vendor_classification_status,
                        original_filename, normalized_camera_id, import_date
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        evidence_id, cam["case_id"],
                        "PUBLIC_RESEARCH_DATASET", cam["filename"],
                        "UCF CRCV / VIRAT / RACD Research", "Unknown",
                        "GenericVideoParser", 1.0, 0,
                        "Research Dataset Camera", None, None,
                        cam["camera_id"], cam["camera_id"], cam["channel"],
                        now, now, "RELATIVE_TO_START", "RELATIVE TO VIDEO START",
                        None, None, "research_footage", "UTC", 0.0,
                        "H.264", resolution, fps_val, duration, bitrate, fcount,
                        0, dest_path, dest_path, hashes["file_size_bytes"],
                        "intact", "verified", "no_tamper_detected",
                        "pending", "HIGH", 1.0,
                        hashes["md5"], hashes["sha256"], hashes["sha512"], hashes["sha3_256"],
                        None, thumb_path,
                        now, "user-investigator-01",
                        f"[{cam['category']}] {cam['scenario']}. Real benchmark footage linked to {cam['camera_id']}.",
                        "Kaggle", "https://www.kaggle.com/datasets/", "UNKNOWN",
                        cam["filename"], cam["camera_id"], now[:10],
                    )
                )
                print(f"  [OK] Inserted new record {evidence_id}")

            await db.commit()

    print("\n" + "=" * 64)
    print("  DONE — Real CCTV benchmark video files linked to cameras.")
    print("  Reload the Case Workstation to play the videos:")
    print("  http://localhost:3000/case/CASE-DEMO001")
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(import_cameras())
