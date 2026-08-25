"""FORGE-VISION — Timeline router"""
from fastapi import APIRouter, Depends
import aiosqlite
from ..database import get_db
from ..routers.auth import get_current_user

router = APIRouter()


@router.get("/case/{case_id}")
async def get_timeline(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return unified timeline data: evidence tracks + AI events + custody events."""
    # Evidence tracks
    async with db.execute(
        "SELECT * FROM evidence WHERE case_id = ? ORDER BY ingested_at ASC", (case_id,)
    ) as cur:
        evidence_list = [dict(r) for r in await cur.fetchall()]

    # Recovery segments per evidence
    segments_by_ev = {}
    for ev in evidence_list:
        async with db.execute(
            "SELECT * FROM recovery_segments WHERE evidence_id = ?", (ev["id"],)
        ) as cur:
            segments_by_ev[ev["id"]] = [dict(r) for r in await cur.fetchall()]

    # AI findings (for event markers)
    async with db.execute(
        "SELECT * FROM ai_findings WHERE case_id = ? ORDER BY frame_number ASC", (case_id,)
    ) as cur:
        ai_events = [dict(r) for r in await cur.fetchall()]

    # Authenticity findings
    async with db.execute(
        """SELECT af.*, e.camera_id FROM authenticity_findings af
           JOIN evidence e ON af.evidence_id = e.id
           WHERE e.case_id = ?""", (case_id,)
    ) as cur:
        auth_events = [dict(r) for r in await cur.fetchall()]

    # Correlation hops
    async with db.execute(
        "SELECT * FROM correlation_hops WHERE case_id = ? ORDER BY created_at ASC", (case_id,)
    ) as cur:
        reid_hops = [dict(r) for r in await cur.fetchall()]

    # Build tracks
    tracks = []
    for ev in evidence_list:
        tracks.append({
            "evidence_id": ev["id"],
            "camera_id": ev.get("camera_id") or "Unknown",
            "channel": ev.get("channel") or "CH-?",
            "source_vendor": ev.get("source_vendor"),
            "is_simulated": bool(ev.get("is_simulated_adapter")),
            "duration_seconds": ev.get("duration_seconds") or 0,
            "timestamp_start": ev.get("timestamp_start"),
            "integrity_status": ev.get("integrity_status"),
            "authenticity_status": ev.get("authenticity_status"),
            "recovery_status": ev.get("recovery_status"),
            "completeness_score": ev.get("completeness_score") or 1.0,
            "segments": segments_by_ev.get(ev["id"], []),
        })

    return {
        "case_id": case_id,
        "tracks": tracks,
        "ai_events": ai_events,
        "authenticity_events": auth_events,
        "reid_hops": reid_hops,
        "track_count": len(tracks),
        "event_count": len(ai_events),
    }
