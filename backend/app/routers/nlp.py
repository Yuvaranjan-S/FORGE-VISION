"""FORGE-VISION — NLP query router"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import aiosqlite
from ..database import get_db
from ..routers.auth import get_current_user
from ..nlp.query_engine import handle_query

router = APIRouter()


class QueryRequest(BaseModel):
    query: str


@router.post("/case/{case_id}/query")
async def query_evidence(
    case_id: str,
    req: QueryRequest,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    return await handle_query(db, case_id, req.query)
