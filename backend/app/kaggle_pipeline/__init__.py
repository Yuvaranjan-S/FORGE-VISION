"""
FORGE-VISION — Kaggle Pipeline Package
"""
from .kaggle_service import (
    KAGGLE_SOURCES_CATALOG,
    IMPORT_JOBS,
    KAGGLE_DATA_DIR,
    get_kaggle_auth_status,
    ensure_sample_kaggle_files,
    scan_dataset_directory,
    scan_dataset_videos_quick,
    process_kaggle_import_job,
)

__all__ = [
    "KAGGLE_SOURCES_CATALOG",
    "IMPORT_JOBS",
    "KAGGLE_DATA_DIR",
    "get_kaggle_auth_status",
    "ensure_sample_kaggle_files",
    "scan_dataset_directory",
    "scan_dataset_videos_quick",
    "process_kaggle_import_job",
]
