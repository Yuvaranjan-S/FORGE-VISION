"""FORGE-VISION — Evidence CRUD + detail router"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
import aiosqlite
from ..database import get_db
from ..routers.auth import get_current_user, SECRET_KEY, ALGORITHM

router = APIRouter()

THUMB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence_store", "thumbnails")


# ── MEDIA AUTH DEPENDENCY ─────────────────────────────────────
# HTML5 <img> and <video> elements cannot set Authorization headers,
# so media endpoints accept the JWT via ?token= query param instead.

async def _media_user(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
    token: str | None = None,
):
    """Accept JWT from Authorization header OR ?token= query param (needed for browser media elements)."""
    from jose import JWTError, jwt as jose_jwt

    raw = token or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not raw:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jose_jwt.decode(raw, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid token")
    async with db.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(401, "User not found")
    return user_id


# ── EVIDENCE EXPLORER (GLOBAL LIST & FILTERS) ─────────────────
@router.get("/")
async def list_all_evidence(
    case_id: str | None = None,
    source_type: str | None = None,
    source_platform: str | None = None,
    vendor: str | None = None,
    vendor_classification_status: str | None = None,
    camera_id: str | None = None,
    integrity_status: str | None = None,
    recovery_status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Universal Evidence Explorer query endpoint with multi-vendor and source filters."""
    query = "SELECT * FROM evidence WHERE 1=1"
    params = []

    if case_id:
        query += " AND case_id = ?"
        params.append(case_id)
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if source_platform:
        query += " AND source_platform = ?"
        params.append(source_platform)
    if vendor:
        if vendor.lower() in ("generic/unknown", "generic_unknown", "unknown"):
            query += " AND (source_vendor = 'Generic' OR source_vendor = 'Unknown' OR source_vendor IS NULL)"
        else:
            query += " AND source_vendor = ?"
            params.append(vendor)
    if vendor_classification_status:
        query += " AND vendor_classification_status = ?"
        params.append(vendor_classification_status)
    if camera_id:
        query += " AND (camera_id = ? OR original_camera_id = ?)"
        params.extend([camera_id, camera_id])
    if integrity_status:
        query += " AND integrity_status = ?"
        params.append(integrity_status)
    if recovery_status:
        query += " AND recovery_status = ?"
        params.append(recovery_status)
    if search:
        s = f"%{search}%"
        query += " AND (id LIKE ? OR source_name LIKE ? OR original_filename LIKE ? OR camera_id LIKE ? OR notes LIKE ?)"
        params.extend([s, s, s, s, s])

    query += " ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with db.execute(query, tuple(params)) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    for ev in rows:
        eid = ev["id"]
        async with db.execute(
            "SELECT finding_type, COUNT(*) as cnt FROM ai_findings WHERE evidence_id = ? GROUP BY finding_type",
            (eid,)
        ) as cur:
            ev["findings_summary"] = {r["finding_type"]: r["cnt"] for r in await cur.fetchall()}

        async with db.execute(
            "SELECT * FROM recovery_segments WHERE evidence_id = ?", (eid,)
        ) as cur:
            ev["recovery_segments"] = [dict(r) for r in await cur.fetchall()]

    return rows


# ── EVIDENCE BY CASE ──────────────────────────────────────────
@router.get("/case/{case_id}")
async def list_evidence(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        "SELECT * FROM evidence WHERE case_id = ? ORDER BY ingested_at ASC", (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    # Enrich each row with findings_summary, segments, and authenticity_findings
    for ev in rows:
        eid = ev["id"]
        async with db.execute(
            "SELECT finding_type, COUNT(*) as cnt FROM ai_findings WHERE evidence_id = ? GROUP BY finding_type",
            (eid,)
        ) as cur:
            ev["findings_summary"] = {r["finding_type"]: r["cnt"] for r in await cur.fetchall()}

        async with db.execute(
            "SELECT * FROM recovery_segments WHERE evidence_id = ?", (eid,)
        ) as cur:
            ev["recovery_segments"] = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT * FROM authenticity_findings WHERE evidence_id = ?", (eid,)
        ) as cur:
            ev["authenticity_findings"] = [dict(r) for r in await cur.fetchall()]

    return rows


@router.get("/{evidence_id}")
async def get_evidence(
    evidence_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)) as cur:
        ev = await cur.fetchone()
    if not ev:
        raise HTTPException(404, "Evidence not found")

    ev_dict = dict(ev)

    async with db.execute(
        "SELECT finding_type, COUNT(*) as cnt FROM ai_findings WHERE evidence_id = ? GROUP BY finding_type",
        (evidence_id,)
    ) as cur:
        ev_dict["findings_summary"] = {r["finding_type"]: r["cnt"] for r in await cur.fetchall()}

    async with db.execute(
        "SELECT * FROM recovery_segments WHERE evidence_id = ?", (evidence_id,)
    ) as cur:
        ev_dict["recovery_segments"] = [dict(r) for r in await cur.fetchall()]

    async with db.execute(
        "SELECT * FROM authenticity_findings WHERE evidence_id = ?", (evidence_id,)
    ) as cur:
        ev_dict["authenticity_findings"] = [dict(r) for r in await cur.fetchall()]

    return ev_dict


# ── MEDIA ENDPOINTS (use _media_user for <img>/<video> compat) ─

@router.get("/{evidence_id}/thumbnail")
async def get_thumbnail(
    evidence_id: str,
    _user: str = Depends(_media_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT thumbnail_path FROM evidence WHERE id = ?", (evidence_id,)) as cur:
        row = await cur.fetchone()
    if not row or not row["thumbnail_path"] or not os.path.exists(row["thumbnail_path"]):
        raise HTTPException(404, "Thumbnail not available")
    return FileResponse(row["thumbnail_path"], media_type="image/jpeg")


@router.get("/{evidence_id}/heatmap")
async def get_heatmap(
    evidence_id: str,
    _user: str = Depends(_media_user),
):
    heatmap_path = os.path.join(THUMB_DIR, f"{evidence_id}_heatmap.jpg")
    if not os.path.exists(heatmap_path):
        raise HTTPException(404, "Heatmap not yet generated. Run motion analysis first.")
    return FileResponse(heatmap_path, media_type="image/jpeg")


@router.get("/{evidence_id}/ela")
async def get_ela(
    evidence_id: str,
    _user: str = Depends(_media_user),
):
    ela_path = os.path.join(THUMB_DIR, f"{evidence_id}_keyframe_ela.jpg")
    if not os.path.exists(ela_path):
        raise HTTPException(404, "ELA image not yet generated. Run authenticity analysis first.")
    return FileResponse(ela_path, media_type="image/jpeg")


@router.get("/{evidence_id}/findings")
async def get_findings(
    evidence_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        "SELECT * FROM ai_findings WHERE evidence_id = ? ORDER BY frame_number ASC", (evidence_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── VIDEO STREAMING ───────────────────────────────────────────

@router.get("/{evidence_id}/video")
async def stream_video(
    evidence_id: str,
    request: Request,
    _user: str = Depends(_media_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Stream evidence video with HTTP Range support for HTML5 video player."""
    async with db.execute("SELECT file_path, codec FROM evidence WHERE id = ?", (evidence_id,)) as cur:
        row = await cur.fetchone()
    if not row or not row["file_path"]:
        raise HTTPException(404, "Video file not found")

    file_path = row["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(404, "Evidence file missing from store")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    # Determine MIME type
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
                ".mov": "video/quicktime", ".ts": "video/mp2t", ".m4v": "video/mp4"}
    media_type = mime_map.get(ext, "video/mp4")

    CHUNK = 1024 * 1024  # 1MB chunks

    if range_header:
        parts = range_header.replace("bytes=", "").split("-")
        start = int(parts[0])
        end = int(parts[1]) if parts[1] else min(start + CHUNK * 8, file_size - 1)
        content_length = end - start + 1

        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = f.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            },
        )

    def iter_full():
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK):
                yield chunk

    return StreamingResponse(
        iter_full(),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )
