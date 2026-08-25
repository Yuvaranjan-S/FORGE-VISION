"""Quick verification script for the Import-to-CAM pipeline."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.kaggle_pipeline import scan_dataset_videos_quick, KAGGLE_DATA_DIR

print("=" * 60)
print("FORGE-VISION — Import-to-CAM Pipeline Verification")
print("=" * 60)
print(f"KAGGLE_DATA_DIR: {KAGGLE_DATA_DIR}")
print()

# Scan all known subfolders
subfolders = {
    "VIRAT": "virat",
    "UCF Crime": "ucf_crime",
    "RACD": "racd",
    "CCTV Action": "cctv_action",
    "Traffic": "traffic",
}

total_videos = 0
for name, subfolder in subfolders.items():
    folder = os.path.join(KAGGLE_DATA_DIR, subfolder)
    if os.path.isdir(folder):
        vids = scan_dataset_videos_quick(folder)
        total_videos += len(vids)
        print(f"[OK] {name}: {len(vids)} video(s) found in {folder}")
        for v in vids[:3]:
            size_mb = v["file_size_bytes"] / (1024 * 1024)
            print(f"     - {v['filename']} ({size_mb:.1f} MB)")
        if len(vids) > 3:
            print(f"     ... and {len(vids) - 3} more")
    else:
        print(f"[--] {name}: folder not found ({folder})")

print()
print(f"Total scannable videos: {total_videos}")
print()

# Verify imports
from app.routers.datasets import _resolve_dataset_folder
print("[OK] _resolve_dataset_folder helper imported")

from app.kaggle_pipeline import process_kaggle_import_job
print("[OK] process_kaggle_import_job imported")
print()
print("All imports OK — backend pipeline ready.")
