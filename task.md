# FORGE-VISION Build Tasks

## Phase 1: Scaffold & Foundation
- [x] Project directory structure
- [x] Backend: FastAPI app skeleton + requirements.txt
- [x] Database: SQLite schema (evidence model + custody ledger)
- [x] Frontend: Next.js scaffold

## Phase 2: Core Backend Modules
- [x] Hash engine (MD5 + SHA256 + SHA3-256)
- [x] Hash-chained custody ledger
- [x] Forensic acquisition/ingest endpoint
- [x] GenericVideoParser (FFprobe metadata)
- [x] Vendor detection + parser dispatch (Hikvision/Dahua/CP Plus adapters — labeled [SIMULATED])
- [x] ELA + frame-diff analysis endpoints (REAL — PIL/numpy)
- [x] Recovery/carving detection endpoint (segments stored in DB)
- [x] Timestamp normalization
- [x] Camera tamper / scene-change detection (blackout: REAL, defocus/spray: SIMULATED)
- [x] AI findings (simulated YOLO detections) endpoints
- [x] Cross-camera re-ID (simulated) endpoint
- [x] NLP query engine (grounded, rule-based, no hallucination)
- [x] PDF report generator (ReportLab, BSA-2023 template)
- [x] Demo data seeder (seed.py)
- [x] Evidence list endpoint enriched with findings/segments/auth findings
- [x] Case list endpoint enriched with ai_finding_count + custody_entry_count

## Phase 3: Frontend UI
- [x] Global CSS (dark forensic theme, glassmorphism, amber/cyan palette)
- [x] Dashboard / case list page (with sidebar stats + capabilities panel)
- [x] Case creation flow (modal, POST /api/cases)
- [x] Investigation workstation (4-pane shell: evidence tree, center tabs, right metadata, custody footer)
- [x] Video player + metadata panel (thumbnail, hash values, device info, video properties)
- [x] Multi-track timeline view (segments, gap markers, AI event markers)
- [x] AI findings panel (per-camera, SIMULATED labeled)
- [x] Authenticity panel (ELA + frame-dup cards with severity/confidence)
- [x] Custody ledger viewer (table with hash chain, chain status banner)
- [x] Cross-camera ReID view (hop graph with similarity scores)
- [x] NLP query interface (example chips, answer with citations + grounding rule)
- [x] Report preview & export (PDF download via REPORT button)
- [x] RBAC login + role gating (JWT, demo credential quick-fill buttons)
- [x] Ingest modal (file upload → triple hash → sealed evidence)

## Phase 4: Polish
- [x] Demo data seed script (4 cameras, varied statuses, custody chain)
- [x] Startup scripts (start_backend.bat, start_frontend.bat)
- [x] README with demo sequence and SIH judging notes

## Remaining / Nice-to-have
- [ ] Video playback (HTML5 video player for ingested MP4 evidence)
- [ ] Timeline zoom/pan with real timestamps (currently width-proportional)
- [ ] Notification toast for custody chain events on other tabs
- [ ] Case status update (close/archive) from dashboard
- [ ] Auditor-only read-only view enforcement in workstation
