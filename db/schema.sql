-- FORGE-VISION Forensic Database Schema
-- SQLite schema for Common Evidence Model + Datasets + Hash-chained Custody Ledger + Audit

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ──────────────────────────────────────────────────────────────
-- USERS / RBAC
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'investigator', -- investigator|supervisor|auditor
    hashed_password TEXT NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- CASES
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cases (
    id                 TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT,
    status             TEXT NOT NULL DEFAULT 'active', -- active|closed|archived
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    created_by         TEXT NOT NULL,
    assigned_to        TEXT,
    reference_clock    TEXT,   -- ISO8601 reference timestamp for drift correction
    reference_timezone TEXT DEFAULT 'Asia/Kolkata'
);

-- ──────────────────────────────────────────────────────────────
-- DATASETS (Provenance & Source Classification)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS datasets (
    id                 TEXT PRIMARY KEY,
    case_id            TEXT REFERENCES cases(id),
    name               TEXT NOT NULL,
    source_type        TEXT NOT NULL DEFAULT 'USER_UPLOADED',
    -- PUBLIC_RESEARCH_DATASET | AUTHORIZED_DVR_EXPORT | AUTHORIZED_CCTV_RECORDING |
    -- VENDOR_SAMPLE | FORENSIC_DISK_IMAGE | TEAM_COLLECTED_TEST_DATA | SYNTHETIC_DEMO | USER_UPLOADED
    source_provider    TEXT NOT NULL DEFAULT 'Local Upload',
    description        TEXT,
    vendor             TEXT DEFAULT 'Generic',
    device_model       TEXT,
    camera_count       INTEGER DEFAULT 0,
    file_count         INTEGER DEFAULT 0,
    total_size_bytes   INTEGER DEFAULT 0,
    license            TEXT DEFAULT 'Authorized Investigation Use',
    source_reference   TEXT,
    collection_method  TEXT DEFAULT 'Direct Ingest',
    collector_name     TEXT,
    collection_date    TEXT,
    is_synthetic       INTEGER NOT NULL DEFAULT 0,
    forensic_status    TEXT NOT NULL DEFAULT 'AUTHENTIC', -- AUTHENTIC | RESEARCH_BENCHMARK | VENDOR_SAMPLE | DEMO_ONLY
    platform           TEXT DEFAULT 'Local',             -- Kaggle | Direct Export | Disk Image | Local
    kaggle_dataset_identifier TEXT,                      -- e.g. hasibalhaq/virat-video-dataset
    sha256_manifest    TEXT,
    local_path         TEXT,
    sha256             TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_files (
    id                 TEXT PRIMARY KEY,
    dataset_id         TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    file_name          TEXT NOT NULL,
    file_path          TEXT NOT NULL,
    file_size_bytes    INTEGER NOT NULL,
    sha256             TEXT NOT NULL,
    detected_vendor    TEXT,
    file_type          TEXT,
    status             TEXT NOT NULL DEFAULT 'ingested',
    created_at         TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- EVIDENCE (Common Evidence Model)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence (
    id                    TEXT PRIMARY KEY,
    case_id               TEXT NOT NULL REFERENCES cases(id),
    dataset_id            TEXT REFERENCES datasets(id),
    source_type           TEXT NOT NULL DEFAULT 'USER_UPLOADED',
    source_platform       TEXT DEFAULT 'Direct',            -- Kaggle | Disk Image | DVR Hardware | Synthetic
    source_name           TEXT,
    source_provider       TEXT,
    source_reference      TEXT,
    source_vendor         TEXT NOT NULL DEFAULT 'Unknown',
    vendor_classification_status TEXT NOT NULL DEFAULT 'UNKNOWN', -- CONFIRMED | INFERRED | UNKNOWN | USER_ASSIGNED | SIMULATED_DEMO
    parser_used           TEXT,
    parser_confidence     REAL DEFAULT 0.0,
    is_simulated_adapter  INTEGER NOT NULL DEFAULT 0,  -- BOOL
    device_model          TEXT,
    device_serial         TEXT,
    firmware              TEXT,
    camera_id             TEXT,
    original_camera_id    TEXT,
    normalized_camera_id  TEXT,
    channel               TEXT,
    original_filename     TEXT,
    timestamp_start       TEXT,
    timestamp_end         TEXT,
    original_timestamp    TEXT,
    normalized_timestamp  TEXT,
    container_timestamp   TEXT,
    osd_timestamp         TEXT,
    timestamp_status      TEXT DEFAULT 'verified', -- verified | discrepancy | unverified
    timezone              TEXT DEFAULT 'Asia/Kolkata',
    clock_drift_seconds   REAL DEFAULT 0.0,
    codec                 TEXT,
    resolution            TEXT,
    fps                   REAL,
    duration_seconds      REAL,
    bitrate_kbps          REAL,
    frame_count           INTEGER,
    has_audio             INTEGER DEFAULT 0,
    file_path             TEXT NOT NULL,
    working_copy_path     TEXT,
    file_size_bytes       INTEGER,
    recovery_status       TEXT NOT NULL DEFAULT 'intact',  -- intact|partial|reconstructed|carved
    integrity_status      TEXT NOT NULL DEFAULT 'unverified', -- verified|mismatch|unverifiable|unverified
    authenticity_status   TEXT NOT NULL DEFAULT 'pending',    -- no_tamper_detected|suspected_edit|inconclusive|pending
    analysis_status       TEXT NOT NULL DEFAULT 'pending',    -- pending|in_progress|completed
    priority              TEXT NOT NULL DEFAULT 'MEDIUM',     -- HIGH | MEDIUM | LOW
    completeness_score    REAL DEFAULT 1.0,   -- 0.0-1.0, for reconstructed segments
    md5                   TEXT,
    sha256                TEXT,
    sha512                TEXT,
    sha3_256              TEXT,
    custody_chain_ref     TEXT,   -- ID of first custody entry for this evidence
    thumbnail_path        TEXT,
    ingested_at           TEXT NOT NULL,
    ingested_by           TEXT NOT NULL,
    import_date           TEXT,
    notes                 TEXT
);

-- ──────────────────────────────────────────────────────────────
-- AI FINDINGS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_findings (
    id                  TEXT PRIMARY KEY,
    evidence_id         TEXT NOT NULL REFERENCES evidence(id),
    case_id             TEXT NOT NULL REFERENCES cases(id),
    finding_type        TEXT NOT NULL,   -- object|face|vehicle|anomaly|tamper|camera_tamper|authenticity
    frame_number        INTEGER,
    timestamp_in_video  TEXT,
    confidence          REAL NOT NULL,
    bounding_box        TEXT,            -- JSON array [x,y,w,h]
    label               TEXT,
    description         TEXT,
    is_simulated        INTEGER NOT NULL DEFAULT 0,
    requires_review     INTEGER NOT NULL DEFAULT 1,
    linked_evidence_ids TEXT,        -- JSON array
    generated_at        TEXT NOT NULL,
    generator           TEXT NOT NULL    -- module name
);

-- ──────────────────────────────────────────────────────────────
-- AUTHENTICITY FINDINGS (detailed tamper analysis)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS authenticity_findings (
    id                  TEXT PRIMARY KEY,
    evidence_id         TEXT NOT NULL REFERENCES evidence(id),
    check_type          TEXT NOT NULL,  -- ela|frame_dup|scene_change|encoding_inconsistency|clone_region
    frame_number        INTEGER,
    timestamp_in_video  TEXT,
    severity            TEXT NOT NULL,  -- low|medium|high
    confidence          REAL NOT NULL,
    detail              TEXT,
    is_simulated        INTEGER NOT NULL DEFAULT 0,
    generated_at        TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- RECOVERY SEGMENTS (carved/reconstructed fragments)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recovery_segments (
    id                  TEXT PRIMARY KEY,
    evidence_id         TEXT NOT NULL REFERENCES evidence(id),
    segment_type        TEXT NOT NULL,  -- intact|gap|recovered|simulated_carved
    start_frame         INTEGER,
    end_frame           INTEGER,
    start_time          REAL,
    end_time            REAL,
    completeness        REAL DEFAULT 1.0,
    nal_units_found     INTEGER,
    is_simulated        INTEGER NOT NULL DEFAULT 0,
    notes               TEXT
);

-- ──────────────────────────────────────────────────────────────
-- CROSS-CAMERA CORRELATION HOPS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS correlation_hops (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL REFERENCES cases(id),
    subject_label       TEXT NOT NULL,  -- "Suspect A", "Vehicle-Red-Sedan"
    from_evidence_id    TEXT NOT NULL REFERENCES evidence(id),
    from_frame          INTEGER,
    from_timestamp      TEXT,
    to_evidence_id      TEXT NOT NULL REFERENCES evidence(id),
    to_frame            INTEGER,
    to_timestamp        TEXT,
    similarity_score    REAL NOT NULL,
    match_basis         TEXT,  -- "clothing-color, build" etc.
    is_simulated        INTEGER NOT NULL DEFAULT 0,
    disclaimer          TEXT DEFAULT 'Appearance-based similarity only. Not biometric identification.',
    created_at          TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- CAMERA TOPOLOGY & SPATIAL NETWORK
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS camera_topology (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL REFERENCES cases(id),
    camera_id           TEXT NOT NULL,
    camera_name         TEXT NOT NULL,
    location_label      TEXT NOT NULL,
    x_pos               INTEGER DEFAULT 100,
    y_pos               INTEGER DEFAULT 100,
    connected_camera_ids TEXT DEFAULT '[]', -- JSON array of camera_ids
    notes               TEXT,
    created_at          TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- EVIDENCE BOOKMARKS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bookmarks (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL REFERENCES cases(id),
    evidence_id         TEXT NOT NULL REFERENCES evidence(id),
    camera_id           TEXT,
    frame_number        INTEGER,
    timestamp_in_video  TEXT,
    title               TEXT NOT NULL,
    notes               TEXT,
    tag                 TEXT DEFAULT 'SUSPECT', -- SUSPECT|VEHICLE|ANOMALY|RECOVERED|CUSTOM
    created_by          TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- REPORTS ARCHIVE
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL REFERENCES cases(id),
    title               TEXT NOT NULL,
    report_type         TEXT NOT NULL DEFAULT 'COMPREHENSIVE_FORENSIC', -- COMPREHENSIVE_FORENSIC | BSA_65B_CERTIFICATE | CUSTODY_LEDGER
    generated_by        TEXT NOT NULL,
    file_path           TEXT NOT NULL,
    file_size_bytes     INTEGER,
    sha256              TEXT NOT NULL,
    summary_findings    TEXT,
    created_at          TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- HASH-CHAINED CHAIN OF CUSTODY LEDGER
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS custody_ledger (
    id                  TEXT PRIMARY KEY,
    seq                 INTEGER NOT NULL,          -- monotonically increasing
    case_id             TEXT NOT NULL REFERENCES cases(id),
    evidence_id         TEXT,                      -- NULL for case-level events
    action              TEXT NOT NULL,             -- ingest|hash_verify|parse|recover|analyze|export|report|bookmark|dataset_import
    operator_id         TEXT NOT NULL,
    operator_role       TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    evidence_hash_before TEXT,
    evidence_hash_after  TEXT,
    detail              TEXT,                      -- JSON blob with action-specific details
    prev_entry_hash     TEXT,                      -- SHA256 of the previous row (chain link)
    this_entry_hash     TEXT NOT NULL              -- SHA256 of this row's content (excluding this field)
);

-- ──────────────────────────────────────────────────────────────
-- AUDIT LOG (Every UI & API action)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL,
    action              TEXT NOT NULL,
    resource            TEXT,           -- evidence_id, case_id, or dataset_id
    detail              TEXT,
    ip_address          TEXT,
    timestamp           TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- INDEXES
-- ──────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_dataset ON evidence(dataset_id);
CREATE INDEX IF NOT EXISTS idx_datasets_case ON datasets(case_id);
CREATE INDEX IF NOT EXISTS idx_findings_evidence ON ai_findings(evidence_id);
CREATE INDEX IF NOT EXISTS idx_findings_case ON ai_findings(case_id);
CREATE INDEX IF NOT EXISTS idx_custody_case ON custody_ledger(case_id);
CREATE INDEX IF NOT EXISTS idx_custody_seq ON custody_ledger(seq);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_correlation_case ON correlation_hops(case_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_case ON bookmarks(case_id);
CREATE INDEX IF NOT EXISTS idx_topology_case ON camera_topology(case_id);
CREATE INDEX IF NOT EXISTS idx_reports_case ON reports(case_id);
