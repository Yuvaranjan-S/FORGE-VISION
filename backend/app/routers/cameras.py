"""
FORGE-VISION — Camera Topology & Spatial Correlation Router
Manages camera nodes, physical layout labels, and transition graphs for cross-camera correlation.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import get_db
from ..routers.auth import get_current_user

router = APIRouter()


class CameraNodeUpdate(BaseModel):
    camera_id: str
    camera_name: str
    location_label: str
    x_pos: int
    y_pos: int
    connected_camera_ids: List[str]
    notes: Optional[str] = None


class TopologySaveRequest(BaseModel):
    case_id: str
    nodes: List[CameraNodeUpdate]


@router.get("/case/{case_id}/topology")
async def get_camera_topology(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve spatial camera node network and connections for a case."""
    async with db.execute(
        """SELECT * FROM camera_topology WHERE case_id = ? ORDER BY camera_id ASC""", (case_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    # If no topology recorded yet, auto-populate from existing evidence
    if not rows:
        async with db.execute(
            """SELECT DISTINCT camera_id, source_vendor, channel FROM evidence WHERE case_id = ?""", (case_id,)
        ) as cur:
            ev_cams = await cur.fetchall()

        now = datetime.now(timezone.utc).isoformat()
        default_layout = [
            ("Main Gate", 100, 140),
            ("Perimeter North", 240, 90),
            ("Main Reception", 380, 150),
            ("Central Corridor", 520, 220),
            ("High-Bay Warehouse", 660, 180),
            ("Vault Entrance", 520, 80),
            ("Loading Bay", 380, 290),
            ("Exit Barrier", 780, 270),
        ]

        for i, row in enumerate(ev_cams):
            cam_id = row["camera_id"]
            loc_label, x, y = default_layout[i % len(default_layout)]
            node_id = str(uuid.uuid4())
            connected = []
            if i > 0:
                connected.append(ev_cams[i-1]["camera_id"])
            if i < len(ev_cams) - 1:
                connected.append(ev_cams[i+1]["camera_id"])

            await db.execute(
                """INSERT INTO camera_topology (id, case_id, camera_id, camera_name, location_label, x_pos, y_pos, connected_camera_ids, notes, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (node_id, case_id, cam_id, f"{cam_id} ({row['source_vendor']})", loc_label, x, y, json.dumps(connected), f"Auto-mapped {row['source_vendor']} camera", now)
            )
        await db.commit()

        async with db.execute("SELECT * FROM camera_topology WHERE case_id = ?", (case_id,)) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    for r in rows:
        try:
            r["connected_camera_ids"] = json.loads(r["connected_camera_ids"] or "[]")
        except Exception:
            r["connected_camera_ids"] = []

    return {"case_id": case_id, "nodes": rows}


@router.post("/topology")
async def save_camera_topology(
    req: TopologySaveRequest,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Save custom camera layout and network node links."""
    now = datetime.now(timezone.utc).isoformat()
    await db.execute("DELETE FROM camera_topology WHERE case_id = ?", (req.case_id,))

    for node in req.nodes:
        node_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO camera_topology (id, case_id, camera_id, camera_name, location_label, x_pos, y_pos, connected_camera_ids, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (node_id, req.case_id, node.camera_id, node.camera_name, node.location_label, node.x_pos, node.y_pos, json.dumps(node.connected_camera_ids), node.notes, now)
        )
    await db.commit()
    return {"message": "Camera topology layout updated", "node_count": len(req.nodes)}
