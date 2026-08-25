"""
FORGE-VISION — Sample CCTV Dataset Generator & Auto-Importer
Generates realistic synthetic surveillance MP4 clips for all 5 Kaggle benchmark datasets
and ingests them into the evidence database.

Run: py -3.12 generate_sample_videos.py
"""
import os
import sys
import asyncio
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.kaggle_pipeline.kaggle_service import (
    ensure_sample_kaggle_files,
    KAGGLE_DATA_DIR,
    KAGGLE_SOURCES_CATALOG,
)

API_BASE = "http://127.0.0.1:8000/api"

# ── ALL 5 DATASET KEYS ────────────────────────────────────────────────
ALL_DATASETS = ["virat-cctv", "ucf-crime", "racd-cctv", "cctv-action", "traffic-intersection"]

CASE_MAP = {
    "virat-cctv": "CASE-DEMO002",
    "ucf-crime": "CASE-DEMO001",
    "racd-cctv": "CASE-DEMO001",
    "cctv-action": "CASE-DEMO001",
    "traffic-intersection": "CASE-DEMO002",
}


def generate_all_sample_videos():
    """Generate MP4 sample files for all 5 benchmark datasets."""
    print("=" * 64)
    print("  FORGE-VISION CCTV SAMPLE VIDEO GENERATOR")
    print("  Generating realistic surveillance benchmark clips...")
    print("=" * 64)

    total_files = 0
    for key in ALL_DATASETS:
        src = KAGGLE_SOURCES_CATALOG[key]
        print(f"\n[{key.upper()}] Generating samples for: {src['name']}")
        files = ensure_sample_kaggle_files(key)
        total_files += len(files)
        for f in files:
            size_mb = f.get("file_size_bytes", 0) / (1024 * 1024)
            print(f"  + {f['filename']}  ({size_mb:.1f} MB)  [{f.get('category', '')}]")

    print(f"\n[OK] Generated {total_files} sample video files total.")
    print(f"     Storage location: {KAGGLE_DATA_DIR}")
    return total_files


async def get_token():
    """Login and get JWT token for API calls."""
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(
            f"{API_BASE}/auth/token",
            data={"username": "investigator", "password": "forensiq2024"},
        )
        if res.status_code != 200:
            print("[WARN] Could not authenticate — skipping database import.")
            return None
        return res.json()["access_token"]


async def import_all_into_db(token: str):
    """Call the Kaggle import-sample endpoint for each dataset."""
    print("\n" + "=" * 64)
    print("  IMPORTING SAMPLE VIDEOS INTO FORENSIQ DATABASE")
    print("=" * 64)

    headers = {"Authorization": f"Bearer {token}"}

    for key in ALL_DATASETS:
        src = KAGGLE_SOURCES_CATALOG[key]
        case_id = CASE_MAP[key]
        count = src["default_sample_count"]

        print(f"\n[{key}] Submitting import job for {count} samples into {case_id}...")
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{API_BASE}/kaggle/import-sample",
                json={
                    "dataset_key": key,
                    "case_id": case_id,
                    "sample_count": count,
                    "category": "ALL",
                },
                headers=headers,
            )
            if res.status_code != 200:
                print(f"  [ERR] Failed to start job: {res.text}")
                continue

            job = res.json()
            job_id = job["job_id"]
            print(f"  Job started: {job_id}")

            # Poll until done
            for _ in range(60):
                await asyncio.sleep(1)
                pr = await client.get(f"{API_BASE}/kaggle/jobs/{job_id}", headers=headers)
                if pr.status_code != 200:
                    break
                status = pr.json()
                if status["status"] in ("completed", "failed"):
                    s = status["status"]
                    imported = status.get("imported_count", 0)
                    evidence_ids = status.get("evidence_ids", [])
                    if s == "completed":
                        print(f"  [OK] Completed: {imported} video(s) imported.")
                        for eid in evidence_ids:
                            print(f"       Evidence ID: {eid}")
                    else:
                        print(f"  [ERR] Job failed: {status.get('error')}")
                    break
                pct = status.get("progress_percent", 0)
                stage = status.get("stage", "...")
                print(f"  [{pct}%] {stage}...", end="\r")


def list_generated_files():
    """Print a tree of all generated data files."""
    print("\n" + "=" * 64)
    print("  GENERATED DATASET FILE TREE")
    print("=" * 64)
    total_size = 0
    total_count = 0
    for root, dirs, files in os.walk(KAGGLE_DATA_DIR):
        level = root.replace(KAGGLE_DATA_DIR, "").count(os.sep)
        indent = "  " * level
        folder = os.path.basename(root)
        print(f"{indent}[{folder}/]")
        sub = "  " * (level + 1)
        for f in sorted(files):
            fpath = os.path.join(root, f)
            sz = os.path.getsize(fpath)
            total_size += sz
            total_count += 1
            print(f"{sub}{f}  ({sz / (1024*1024):.2f} MB)")
    print(f"\n  Total: {total_count} files  |  {total_size / (1024*1024):.2f} MB")


async def main():
    # Step 1: Generate video files locally
    generate_all_sample_videos()

    # Step 2: Show file tree
    list_generated_files()

    # Step 3: Import into DB if backend is running
    token = await get_token()
    if token:
        await import_all_into_db(token)
        print("\n" + "=" * 64)
        print("  ALL SAMPLE VIDEOS IMPORTED SUCCESSFULLY!")
        print("  Open http://localhost:3000/evidence to view all records.")
        print("=" * 64)
    else:
        print("\n[NOTE] Backend not reachable — files generated locally.")
        print(f"       Run seed.py then start the server to import: py -3.12 seed.py")


if __name__ == "__main__":
    asyncio.run(main())
