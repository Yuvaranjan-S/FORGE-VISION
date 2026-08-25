"""
FORGE-VISION — Evidence Bookmarks Router
Allows forensic investigators to bookmark key frames, timestamps, anomalies, and AI detections.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import get_db
from ..routers.auth import get_current_user
from ..custody.ledger import append_custody_event

router = APIRouter()


class BookmarkCreate(BaseModel):
    case_id: str
    evidence_id: str
    camera_id: Optional[str] = "CAM-01"
    frame_number: Optional[int] = 0
    timestamp_in_video: Optional[str] = "00:00:00"
    title: str
    notes: Optional[str] = None
    tag: str = "SUSPECT" # SUSPECT | VEHICLE | ANOMALY | RECOVERED | CUSTOM


@router.get("/case/{case_id}")
async def get_case_bookmarks(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all investigator bookmarks for a case."""
    async with db.execute(
        """SELECT b.*, e.source_vendor, e.file_path, e.is_simulated_adapter
           FROM bookmarks b
           LEFT JOIN evidence e ON b.evidence_id = e.id
           WHERE b.case_id = ?
           ORDER BY b.created_at DESC""",
        (case_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


@router.post("/")
async def create_bookmark(
    req: BookmarkCreate,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new bookmark on a specific video frame/timestamp."""
    bookmark_id = f"BM-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO bookmarks (
            id, case_id, evidence_id, camera_id, frame_number,
            timestamp_in_video, title, notes, tag, created_by, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            bookmark_id, req.case_id, req.evidence_id, req.camera_id,
            req.frame_number, req.timestamp_in_video, req.title,
            req.notes, req.tag, current_user["full_name"] or current_user["username"], now
        )
    )
    await db.commit()

    await append_custody_event(
        db, case_id=req.case_id, action="bookmark_created",
        operator_id=current_user["id"], operator_role=current_user["role"],
        evidence_id=req.evidence_id,
        detail={"bookmark_id": bookmark_id, "title": req.title, "tag": req.tag, "timestamp": req.timestamp_in_video},
    )

    return {
        "id": bookmark_id,
        "case_id": req.case_id,
        "evidence_id": req.evidence_id,
        "title": req.title,
        "created_at": now,
        "message": "Bookmark successfully saved to case record."
    }


@router.delete("/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove a bookmark."""
    async with db.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)) as cur:
        bm = await cur.fetchone()
    if not bm:
        raise HTTPException(404, "Bookmark not found")

    await db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
    await db.commit()
    return {"message": "Bookmark removed", "id": bookmark_id}
