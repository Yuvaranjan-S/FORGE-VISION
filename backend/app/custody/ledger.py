"""
FORGE-VISION — Hash-Chained Chain of Custody Ledger
Every action on evidence writes a tamper-evident ledger entry.
Each entry's hash is computed from its own content, and stores the
hash of the previous entry — forming a blockchain-style chain.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from ..hash_engine import compute_custody_entry_hash


async def append_custody_event(
    db: aiosqlite.Connection,
    case_id: str,
    action: str,
    operator_id: str,
    operator_role: str,
    evidence_id: Optional[str] = None,
    evidence_hash_before: Optional[str] = None,
    evidence_hash_after: Optional[str] = None,
    detail: Optional[dict] = None,
) -> dict:
    """
    Append a new entry to the chain-of-custody ledger.
    Reads the last entry's hash to form the chain link.
    Returns the new entry dict.
    """
    # Get current sequence and previous hash
    async with db.execute(
        "SELECT seq, this_entry_hash FROM custody_ledger ORDER BY seq DESC LIMIT 1"
    ) as cur:
        row = await cur.fetchone()

    prev_seq = row["seq"] if row else 0
    prev_hash = row["this_entry_hash"] if row else None
    new_seq = prev_seq + 1

    entry_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    entry = {
        "id": entry_id,
        "seq": new_seq,
        "case_id": case_id,
        "evidence_id": evidence_id,
        "action": action,
        "operator_id": operator_id,
        "operator_role": operator_role,
        "timestamp": timestamp,
        "evidence_hash_before": evidence_hash_before,
        "evidence_hash_after": evidence_hash_after,
        "detail": json.dumps(detail or {}),
        "prev_entry_hash": prev_hash,
        "this_entry_hash": "",  # Placeholder — computed below
    }

    # Compute this entry's hash (excluding this_entry_hash field itself)
    this_hash = compute_custody_entry_hash(entry, exclude_key="this_entry_hash")
    entry["this_entry_hash"] = this_hash

    await db.execute(
        """INSERT INTO custody_ledger
           (id, seq, case_id, evidence_id, action, operator_id, operator_role,
            timestamp, evidence_hash_before, evidence_hash_after, detail,
            prev_entry_hash, this_entry_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            entry["id"], entry["seq"], entry["case_id"], entry["evidence_id"],
            entry["action"], entry["operator_id"], entry["operator_role"],
            entry["timestamp"], entry["evidence_hash_before"], entry["evidence_hash_after"],
            entry["detail"], entry["prev_entry_hash"], entry["this_entry_hash"],
        ),
    )
    await db.commit()
    return entry


async def get_custody_chain(db: aiosqlite.Connection, case_id: str) -> list[dict]:
    """Return all ledger entries for a case, ordered by sequence."""
    async with db.execute(
        "SELECT * FROM custody_ledger WHERE case_id = ? ORDER BY seq ASC", (case_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_evidence_custody(db: aiosqlite.Connection, evidence_id: str) -> list[dict]:
    """Return all ledger entries for a specific evidence item."""
    async with db.execute(
        "SELECT * FROM custody_ledger WHERE evidence_id = ? ORDER BY seq ASC", (evidence_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
