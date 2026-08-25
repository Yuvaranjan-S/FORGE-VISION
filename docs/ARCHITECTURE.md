# FORGE-VISION Architecture Specification

## Overview
**FORGE-VISION** is a multi-vendor digital forensics intelligence and evidence reconstruction platform built for the **Smart India Hackathon (SIH Problem Statement 150)**. It solves fragmented, vendor-proprietary CCTV evidence by standardizing disparate surveillance video into a single Common Evidence Model while strictly enforcing write-blocking and cryptographic hash-chain integrity.

```
Next.js 14 Frontend Workstation (Port 3000)
       │
       │ REST / JSON (OAuth2 JWT)
       ▼
Python FastAPI Backend (Port 8000)
       │
       ├── Core Forensic Engine
       │     ├── Acquisition & Write-Blocking Ingestion Store
       │     ├── Triple Hashing (MD5, SHA-256, SHA3-256)
       │     ├── Modular Vendor Adapter Dispatcher
       │     ├── Dataset Provenance & Registry Engine
       │     ├── Stream Continuity & H.264/H.265 NAL Carving
       │     ├── Authenticity & ELA Tamper Analysis
       │     ├── Cross-Camera Spatial Topology & ReID Correlation
       │     ├── Grounded NLP Evidence Query Engine
       │     └── 65B / BSA-2023 Forensic PDF Report Generator
       │
       └── Storage Layer
             ├── SQLite Database (`db/forensiq.db`) (WAL Mode)
             └── Read-Only Evidence Repository (`evidence_store/`)
```

---

## Modular Component Layers

### 1. Ingestion & Preservation Layer
- **Write-Blocking Principle**: Original files are never edited or overwritten in place.
- **Triple Hash Seal**: On ingestion, `MD5`, `SHA-256`, and `SHA3-256` are computed simultaneously via chunked streaming.
- **Working Copy Generation**: Analytical tasks (framing, differencing, ELA) execute on working copy derivatives.

### 2. Modular Vendor Parser Framework
- Every OEM DVR/NVR parser implements the abstract `VendorParser` interface:
  - `detect(file_path)`: Magic byte & extension signature identification
  - `identify_device(file_path)`: Extract vendor, model, firmware
  - `extract_metadata(file_path)`: Normalized FPS, resolution, duration, codec, bitrate
  - `detect_deleted_data(file_path)`: Scan for missing NAL units and GOP gaps
  - `recover_fragments(file_path)`: Stream continuity carving
  - `confidence_score()`: Precision index

### 3. Cryptographic Chain-of-Custody Ledger
- Tamper-evident blockchain-style ledger.
- Each event row stores:
  $$\text{this\_entry\_hash} = \text{SHA256}(\text{prev\_entry\_hash} + \text{event\_data})$$
- Full mathematical validation via `verify_chain()`.

### 4. Grounded NLP Investigation Engine
- Translates natural language questions into deterministic database queries with explicit citation links.
- Strictly refuses to hallucinate facts or manufacture evidence.

### 5. Section 65B / BSA-2023 Legal Reporting Engine
- ReportLab-based PDF generator containing 20 standardized forensic sections, provenance tables, bookmark ledgers, and formal electronic-record certificate templates under the Indian legal framework.
