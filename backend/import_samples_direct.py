"""
FORGE-VISION — Direct In-Process Sample Video Importer
Bypasses the API entirely and writes directly to the SQLite database.
Generates 23 sample CCTV MP4 clips and creates proper evidence records.

Run: py -3.12 import_samples_direct.py
"""
import os, sys, uuid, hashlib, json, asyncio
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))

import aiosqlite
from app.database import DB_PATH, init_db
from app.kaggle_pipeline.kaggle_service import (
    ensure_sample_kaggle_files,
    KAGGLE_SOURCES_CATALOG,
    EVIDENCE_STORE_DIR,
    THUMBNAILS_DIR,
)

import cv2

CASE_MAP = {
    "virat-cctv": "CASE-DEMO002",
    "ucf-crime": "CASE-DEMO001",
    "racd-cctv": "CASE-DEMO001",
    "cctv-action": "CASE-DEMO001",
    "traffic-intersection": "CASE-DEMO002",
}

ALL_DATASETS = ["virat-cctv", "ucf-crime", "racd-cctv", "cctv-action", "traffic-intersection"]


def hash_file(path: str):
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    sha3 = hashlib.sha3_256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            md5.update(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
            sha3.update(chunk)
            size += len(chunk)
    return {
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(),
        "sha3_256": sha3.hexdigest(),
        "file_size_bytes": size,
    }


def make_thumbnail(video_path: str, thumb_path: str) -> bool:
    try:
        cap = cv2.VideoCapture(video_path)
        ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            thumb = cv2.resize(frame, (480, 270))
            cv2.imwrite(thumb_path, thumb)
            return True
    except Exception:
        pass
    return False


async def import_all():
    print("=" * 64)
    print("  FORGE-VISION DIRECT SAMPLE IMPORT")
    print("  Generating + hashing + indexing all CCTV benchmarks")
    print("=" * 64)

    await init_db()
    now = datetime.now(timezone.utc).isoformat()
    total_imported = 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")

        for key in ALL_DATASETS:
            src = KAGGLE_SOURCES_CATALOG[key]
            case_id = CASE_MAP[key]
            print(f"\n[{key.upper()}] {src['name']}")

            # 1. Generate sample MP4s
            sample_files = ensure_sample_kaggle_files(key)
            print(f"  Files ready: {len(sample_files)}")

            # 2. Create dataset provenance record
            dataset_id = f"DS-KAG-{str(uuid.uuid4())[:6].upper()}"
            total_bytes = sum(f.get("file_size_bytes", 0) for f in sample_files)
            await db.execute(
                """INSERT OR IGNORE INTO datasets (
                    id, case_id, name, source_type, source_provider, description,
                    vendor, device_model, camera_count, file_count, total_size_bytes,
                    license, source_reference, collection_method, collector_name,
                    collection_date, is_synthetic, forensic_status, platform,
                    kaggle_dataset_identifier, sha256, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    dataset_id, case_id, src["name"], "PUBLIC_RESEARCH_DATASET",
                    src["provider"], src["description"], "Unknown",
                    "Research Dataset Camera", len(sample_files), len(sample_files),
                    total_bytes, src["license"], src["source_reference"],
                    "Kaggle Public Dataset Pipeline", "SIH Investigator",
                    now[:10], 0, "RESEARCH_DATA", "Kaggle",
                    src.get("kaggle_dataset_identifier", key),
                    hashlib.sha256(f"{dataset_id}:{now}".encode()).hexdigest(), now,
                )
            )
            await db.commit()

            # 3. Import each video
            for idx, item in enumerate(sample_files, 1):
                src_path = item["file_path"]
                orig_name = item["filename"]
                category = item.get("category", "General")

                print(f"  [{idx}/{len(sample_files)}] Hashing: {orig_name}...", end=" ")

                try:
                    hashes = hash_file(src_path)
                    file_sz = hashes["file_size_bytes"]

                    # Check if already imported (by sha256)
                    async with db.execute(
                        "SELECT id FROM evidence WHERE sha256 = ? AND case_id = ?",
                        (hashes["sha256"], case_id)
                    ) as cur:
                        existing = await cur.fetchone()
                    if existing:
                        print(f"already exists ({existing[0]})")
                        total_imported += 1
                        continue

                    # Copy to evidence_store
                    evidence_id = f"EVD-KAG-{str(uuid.uuid4())[:8].upper()}"
                    dest_name = f"{evidence_id}_{orig_name}"
                    dest_path = os.path.join(EVIDENCE_STORE_DIR, dest_name)
                    with open(src_path, "rb") as sf, open(dest_path, "wb") as df:
                        while chunk := sf.read(65536):
                            df.write(chunk)

                    # Thumbnail
                    thumb_path = os.path.join(THUMBNAILS_DIR, f"{evidence_id}_thumb.jpg")
                    make_thumbnail(dest_path, thumb_path)

                    cam_num = (idx % 8) + 1
                    cam_id = f"DATASET_CAM_{cam_num:02d}"
                    channel = f"CH-{cam_num}"

                    # Get video metadata via OpenCV
                    codec, resolution, fps_val, duration, frame_count, bitrate = (
                        "H.264", "1280x720", 25.0, 10.0, 250, 2048.0
                    )
                    try:
                        cap = cv2.VideoCapture(dest_path)
                        fps_val = cap.get(cv2.CAP_PROP_FPS) or 25.0
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        duration = frame_count / fps_val if fps_val > 0 else 10.0
                        resolution = f"{w}x{h}" if w and h else "1280x720"
                        bitrate = round((file_sz * 8) / (duration * 1000), 1) if duration > 0 else 2048.0
                        cap.release()
                    except Exception:
                        pass

                    # Insert into evidence with all 56 columns
                    await db.execute(
                        """INSERT INTO evidence (
                            id, case_id, dataset_id, source_type, source_name,
                            source_provider, source_vendor, parser_used, parser_confidence,
                            is_simulated_adapter, device_model, device_serial, firmware,
                            camera_id, original_camera_id, channel,
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
                            evidence_id, case_id, dataset_id,
                            "PUBLIC_RESEARCH_DATASET", orig_name,
                            src["provider"], "Unknown",
                            "GenericVideoParser", 1.0, 0,
                            "Research Dataset Camera", None, None,
                            cam_id, orig_name, channel,
                            now, now, "RELATIVE_TO_START", "RELATIVE TO VIDEO START",
                            None, None, "research_footage",
                            "UTC", 0.0,
                            codec, resolution, fps_val, duration, bitrate, frame_count,
                            0, dest_path, dest_path, file_sz,
                            "intact", "verified", "no_tamper_detected",
                            "pending", "HIGH", 1.0,
                            hashes["md5"], hashes["sha256"], hashes["sha512"], hashes["sha3_256"],
                            None, thumb_path if os.path.exists(thumb_path) else None,
                            now, "user-investigator-01",
                            f"[{category}] Imported from '{src['name']}' (Kaggle CCTV Ingestion Pipeline). "
                            f"Public research dataset — not original case-acquired DVR evidence.",
                            "Kaggle", src["source_reference"], "UNKNOWN",
                            orig_name, cam_id, now[:10],
                        )
                    )
                    await db.commit()

                    print(f"OK ({evidence_id}) [{category}] {resolution} {duration:.1f}s {file_sz//1048576}MB")
                    total_imported += 1

                except Exception as err:
                    print(f"ERROR: {err}")

    print("\n" + "=" * 64)
    print(f"  IMPORT COMPLETE: {total_imported} evidence records created")
    print(f"  Videos stored at: {EVIDENCE_STORE_DIR}")
    print(f"  View all at: http://localhost:3000/evidence")
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(import_all())
