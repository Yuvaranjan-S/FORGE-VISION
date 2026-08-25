"""FORGE-VISION — Custody ledger router"""
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
from ..database import get_db
from ..routers.auth import get_current_user
from ..hash_engine import verify_chain
from ..custody.ledger import get_custody_chain, get_evidence_custody

router = APIRouter()


@router.get("/case/{case_id}")
async def get_case_custody(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    entries = await get_custody_chain(db, case_id)
    verification = verify_chain(entries)
    return {"entries": entries, "chain_verification": verification}


@router.get("/case/{case_id}/verify")
async def verify_custody_chain(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    entries = await get_custody_chain(db, case_id)
    return verify_chain(entries)


@router.get("/evidence/{evidence_id}")
async def get_evidence_custody_log(
    evidence_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    entries = await get_evidence_custody(db, evidence_id)
    return {"evidence_id": evidence_id, "entries": entries}
