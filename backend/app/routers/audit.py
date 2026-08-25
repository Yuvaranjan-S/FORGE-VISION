"""
FORGE-VISION — Audit Log Router
Allows Auditor and Supervisor roles to inspect immutable forensic operation logs.
"""
from typing import Optional
import aiosqlite
from fastapi import APIRouter, Depends
from ..database import get_db
from ..routers.auth import get_current_user, require_role

router = APIRouter()


@router.get("/logs")
async def get_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(require_role("auditor", "supervisor", "investigator")),
):
    """Retrieve forensic audit logs with filter and search capabilities."""
    query = """
        SELECT a.*, u.username, u.full_name, u.role
        FROM audit_log a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    """
    params = []
    if user_id:
        query += " AND a.user_id = ?"
        params.append(user_id)
    if action:
        query += " AND a.action LIKE ?"
        params.append(f"%{action}%")

    query += " ORDER BY a.timestamp DESC LIMIT ?"
    params.append(limit)

    async with db.execute(query, tuple(params)) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    return {"total": len(rows), "logs": rows}
