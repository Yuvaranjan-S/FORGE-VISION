"""
FORGE-VISION — Core hash engine
Triple-hashing: MD5 + SHA256 + SHA3-256
All acquisition operations must use this module.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Optional


CHUNK_SIZE = 65536  # 64KB chunks for large file hashing


def compute_file_hashes(file_path: str) -> dict:
    """
    Compute MD5, SHA256, and SHA3-256 of a file.
    Returns dict with all three hashes.
    """
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    sha3_256 = hashlib.sha3_256()

    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            md5.update(chunk)
            sha256.update(chunk)
            sha3_256.update(chunk)

    return {
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
        "sha3_256": sha3_256.hexdigest(),
        "file_size_bytes": os.path.getsize(file_path),
    }


def compute_string_sha256(data: str) -> str:
    """SHA256 of a UTF-8 string — used for custody chain entries."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_custody_entry_hash(entry: dict, exclude_key: str = "this_entry_hash") -> str:
    """
    Compute the canonical hash of a custody ledger entry.
    Excludes `this_entry_hash` itself (obviously) to avoid circular dependency.
    Sorts keys for determinism.
    """
    payload = {k: v for k, v in entry.items() if k != exclude_key}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return compute_string_sha256(canonical)


def verify_chain(entries: list[dict]) -> dict:
    """
    Verify the hash chain of custody ledger entries.
    Returns a report with: is_valid, broken_at_seq, details.
    """
    if not entries:
        return {"is_valid": True, "broken_at_seq": None, "entry_count": 0, "details": []}

    details = []
    broken_at = None

    for i, entry in enumerate(entries):
        # Verify this_entry_hash
        expected_hash = compute_custody_entry_hash(entry)
        actual_hash = entry.get("this_entry_hash", "")
        hash_ok = expected_hash == actual_hash

        # Verify prev_entry_hash linkage
        if i == 0:
            chain_ok = entry.get("prev_entry_hash") is None or entry.get("prev_entry_hash") == ""
        else:
            chain_ok = entry.get("prev_entry_hash") == entries[i - 1].get("this_entry_hash")

        ok = hash_ok and chain_ok
        if not ok and broken_at is None:
            broken_at = entry.get("seq", i)

        details.append({
            "seq": entry.get("seq"),
            "id": entry.get("id"),
            "hash_ok": hash_ok,
            "chain_ok": chain_ok,
            "valid": ok,
        })

    return {
        "is_valid": broken_at is None,
        "broken_at_seq": broken_at,
        "entry_count": len(entries),
        "details": details,
    }
