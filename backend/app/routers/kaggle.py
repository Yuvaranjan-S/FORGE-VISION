"""
FORGE-VISION — Kaggle CCTV Dataset Ingestion Router
Provides endpoints for:
- Listing legitimate Kaggle surveillance benchmark sources (VIRAT, UCF Crime, RACD, CCTV Action, Traffic)
- Safe Kaggle authentication status
- Local folder scanning
- Background sample and directory import jobs
- Real-time job polling
"""
import uuid
import asyncio
from typing import Optional, List, Dict, Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..database import get_db, DB_PATH
from ..routers.auth import get_current_user
from ..kaggle_pipeline import (
    KAGGLE_SOURCES_CATALOG,
    IMPORT_JOBS,
    get_kaggle_auth_status,
    scan_dataset_directory,
    process_kaggle_import_job,
)

router = APIRouter()


class ScanLocalRequest(BaseModel):
    directory_path: str


class ImportSampleRequest(BaseModel):
    dataset_key: str
    case_id: Optional[str] = "CASE-DEMO001"
    sample_count: Optional[int] = 5
    category: Optional[str] = "ALL"


class ImportLocalDirectoryRequest(BaseModel):
    dataset_key: str
    directory_path: str
    case_id: Optional[str] = "CASE-DEMO001"
    selected_files: Optional[List[str]] = None


# Helper to get standalone db connection for background tasks
def db_connection_factory():
    return aiosqlite.connect(DB_PATH)


@router.get("/sources")
async def get_kaggle_sources(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve catalog of all configured Kaggle CCTV benchmark datasets with provenance & import status."""
    auth = get_kaggle_auth_status()
    results = []

    for key, info in KAGGLE_SOURCES_CATALOG.items():
        item = dict(info)
        item["is_authenticated"] = auth["authenticated"]

        # Check if already imported in database
        async with db.execute(
            "SELECT id, file_count, created_at FROM datasets WHERE (kaggle_dataset_identifier = ? OR id LIKE ?) ORDER BY created_at DESC LIMIT 1",
            (info.get("kaggle_dataset_identifier"), f"%{key}%")
        ) as cur:
            row = await cur.fetchone()

        if row:
            item["status"] = "IMPORTED"
            item["imported_dataset_id"] = row["id"]
            item["imported_file_count"] = row["file_count"]
            item["imported_at"] = row["created_at"]
        elif auth["authenticated"]:
            item["status"] = "AVAILABLE"
        else:
            item["status"] = "SAMPLE_READY"

        results.append(item)

    return results


@router.get("/auth-status")
async def get_auth_status(
    current_user: dict = Depends(get_current_user),
):
    """Inspect Kaggle API authentication safely without leaking private credentials."""
    return get_kaggle_auth_status()


@router.post("/scan-local")
async def scan_local_folder(
    req: ScanLocalRequest,
    current_user: dict = Depends(get_current_user),
):
    """Scan a local directory for surveillance media, annotations, and metadata."""
    res = scan_dataset_directory(req.directory_path)
    if not res.get("valid"):
        raise HTTPException(400, res.get("error", "Invalid directory path"))
    return res


@router.post("/import-sample")
async def import_kaggle_sample(
    req: ImportSampleRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Launch asynchronous background job to import sample CCTV footage from selected Kaggle dataset."""
    if req.dataset_key not in KAGGLE_SOURCES_CATALOG:
        raise HTTPException(404, f"Dataset key '{req.dataset_key}' not recognized in catalog")

    job_id = f"job-{str(uuid.uuid4())[:8]}"

    background_tasks.add_task(
        process_kaggle_import_job,
        job_id=job_id,
        dataset_key=req.dataset_key,
        case_id=req.case_id or "CASE-DEMO001",
        custom_files=None,
        max_sample_count=req.sample_count or 5,
        category_filter=req.category or "ALL",
        user_info=current_user,
        db_factory=db_connection_factory,
    )

    return {
        "job_id": job_id,
        "dataset_key": req.dataset_key,
        "case_id": req.case_id,
        "status": "queued",
        "message": f"Kaggle sample import job '{job_id}' started in background.",
    }


@router.post("/import-local-directory")
async def import_local_directory(
    req: ImportLocalDirectoryRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Launch asynchronous background job to import videos from a local folder."""
    job_id = f"job-{str(uuid.uuid4())[:8]}"

    background_tasks.add_task(
        process_kaggle_import_job,
        job_id=job_id,
        dataset_key=req.dataset_key,
        case_id=req.case_id or "CASE-DEMO001",
        custom_files=req.selected_files,
        max_sample_count=len(req.selected_files) if req.selected_files else 100,
        category_filter="ALL",
        user_info=current_user,
        db_factory=db_connection_factory,
    )

    return {
        "job_id": job_id,
        "dataset_key": req.dataset_key,
        "directory_path": req.directory_path,
        "status": "queued",
        "message": f"Local folder import job '{job_id}' started in background.",
    }


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Poll progress status of an active or completed Kaggle import job."""
    job = IMPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return job
