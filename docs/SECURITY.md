# Security & Forensic Integrity Specification

## Forensic Integrity Principles

1. **Read-Only Preservation (Write-Blocking)**
   - Master evidence files are stored in read-only repositories.
   - All analytical processes (framing, differential analysis, ELA, YOLO inference) are executed on detached working copy derivatives.

2. **Triple-Hash Verification**
   - Ingested evidence is sealed with `MD5`, `SHA-256`, and `SHA3-256`.
   - Hashes are verified periodically or on demand. Any modification immediately triggers a `MISMATCH` alert.

3. **Tamper-Evident Hash Chain**
   - The chain-of-custody ledger links every event to the cryptographic hash of its predecessor:
     $$\text{EntryHash}_n = \text{SHA256}(\text{EntryHash}_{n-1} + \text{Data}_n)$$
   - Modification or deletion of any intermediate record breaks the mathematical chain, exposing the sequence where tampering occurred.

4. **Role-Based Access Control (RBAC)**
   - **`investigator`**: Ingest evidence, run analytics, create bookmarks, draft reports.
   - **`supervisor`**: Approve cases, finalize/export court-ready forensic reports, manage datasets.
   - **`auditor`**: Read-only oversight, verify cryptographic hash chains, inspect immutable audit logs.

5. **Local-First & Offline Architecture**
   - Zero telemetry.
   - Video evidence is never transmitted to external cloud endpoints. All forensic algorithms execute locally on the workstation.
