"""FORGE-VISION — Cases router"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import aiosqlite
from ..database import get_db
from ..routers.auth import get_current_user
from ..custody.ledger import append_custody_event

router = APIRouter()


class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    reference_timezone: str = "Asia/Kolkata"


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.post("/")
async def create_case(
    case_in: CaseCreate,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    case_id = f"CASE-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO cases (id, title, description, status, created_at, updated_at, created_by, reference_timezone)
           VALUES (?,?,?,?,?,?,?,?)""",
        (case_id, case_in.title, case_in.description, "active", now, now,
         current_user["id"], case_in.reference_timezone)
    )
    await db.commit()

    await append_custody_event(
        db, case_id=case_id, action="case_created",
        operator_id=current_user["id"], operator_role=current_user["role"],
        detail={"title": case_in.title},
    )
    return {"case_id": case_id, "title": case_in.title, "status": "active", "created_at": now}


@router.get("/")
async def list_cases(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute(
        """SELECT
               c.*,
               COUNT(DISTINCT e.id)   AS evidence_count,
               COUNT(DISTINCT f.id)   AS ai_finding_count,
               COUNT(DISTINCT cu.id)  AS custody_entry_count
           FROM cases c
           LEFT JOIN evidence e  ON e.case_id  = c.id
           LEFT JOIN ai_findings f  ON f.case_id  = c.id
           LEFT JOIN custody_ledger cu ON cu.case_id = c.id
           GROUP BY c.id ORDER BY c.created_at DESC"""
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    return rows


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    async with db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)) as cur:
        case = await cur.fetchone()
    if not case:
        raise HTTPException(404, "Case not found")

    async with db.execute("SELECT COUNT(*) as cnt FROM evidence WHERE case_id = ?", (case_id,)) as cur:
        ev_count = (await cur.fetchone())["cnt"]
    async with db.execute("SELECT COUNT(*) as cnt FROM ai_findings WHERE case_id = ?", (case_id,)) as cur:
        ai_count = (await cur.fetchone())["cnt"]
    async with db.execute("SELECT COUNT(*) as cnt FROM custody_ledger WHERE case_id = ?", (case_id,)) as cur:
        cust_count = (await cur.fetchone())["cnt"]

    result = dict(case)
    result.update({"evidence_count": ev_count, "ai_finding_count": ai_count, "custody_entry_count": cust_count})
    return result


@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    update: CaseUpdate,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    fields = {k: v for k, v in update.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(f"UPDATE cases SET {set_clause} WHERE id = ?",
                     (*fields.values(), case_id))
    await db.commit()
    return {"case_id": case_id, "updated": list(fields.keys())}
