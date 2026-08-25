"""
FORGE-VISION — Database initialization and session management
"""
import os
import aiosqlite

raw_db_url = os.getenv("DATABASE_URL", "")
if raw_db_url.startswith("sqlite:///"):
    # Strip sqlite:/// prefix
    DB_PATH = os.path.abspath(raw_db_url.replace("sqlite:///", ""))
elif raw_db_url and not raw_db_url.startswith("postgres"):
    DB_PATH = os.path.abspath(raw_db_url)
else:
    if os.getenv("VERCEL") == "1":
        DB_PATH = "/tmp/forensiq.db"
    else:
        DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "db", "forensiq.db"))

SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.sql"))

# Ensure database directory exists immediately
try:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
except Exception:
    DB_PATH = "/tmp/forensiq.db"
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


async def check_database_connection() -> bool:
    """Check whether the database is accessible and responsive."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1") as cur:
                res = await cur.fetchone()
                return res is not None
    except Exception:
        return False


async def get_db():
    """Dependency: yields an aiosqlite connection per request."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db


from datetime import datetime, timezone
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def safe_hash_password(password: str) -> str:
    return pwd_context.hash(str(password)[:72])

DEMO_USERS = [
    ("user-investigator-01", "investigator", "Arjun Sharma", "investigator", "forensiq2024"),
    ("user-supervisor-01", "supervisor", "Dr. Priya Mehta", "supervisor", "supervisor2024"),
    ("user-auditor-01", "auditor", "Rahul Verma", "auditor", "auditor2024"),
]

DEMO_CASES = [
    ("CASE-DEMO001", "Operation Kite — Bank Robbery Investigation", "Multi-vendor DVR footage and public research benchmarks.", "active", "user-supervisor-01", "Asia/Kolkata"),
    ("CASE-DEMO002", "Commercial Complex Fire — Evidence Recovery", "Partial NVR data recovery after thermal damage.", "active", "user-supervisor-01", "Asia/Kolkata"),
    ("CASE-DEMO-MULTIVENDOR", "Multi-Vendor DVR/NVR Architecture Evaluation", "Controlled SIH multi-vendor demonstration case.", "active", "user-supervisor-01", "Asia/Kolkata"),
]


async def seed_demo_users_and_data(db: aiosqlite.Connection):
    """Guarantees demo accounts, cases, evidence, datasets, custody ledger, and AI findings exist in the database."""
    try:
        import sys
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from seed import _seed_with_db
        await _seed_with_db(db)
    except Exception as e:
        import traceback
        print(f"[SEEDS] Exception during full seed: {e}")
        traceback.print_exc()


async def init_db():
    """Initialize database with schema on startup and ensure column migrations."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema)
        
        # Safe column additions if migrating from earlier schema
        migrations = [
            ("datasets", "platform", "TEXT DEFAULT 'Local'"),
            ("datasets", "kaggle_dataset_identifier", "TEXT"),
            ("datasets", "sha256_manifest", "TEXT"),
            ("datasets", "local_path", "TEXT"),
            ("evidence", "source_platform", "TEXT DEFAULT 'Direct'"),
            ("evidence", "source_reference", "TEXT"),
            ("evidence", "vendor_classification_status", "TEXT DEFAULT 'UNKNOWN'"),
            ("evidence", "original_filename", "TEXT"),
            ("evidence", "normalized_camera_id", "TEXT"),
            ("evidence", "import_date", "TEXT"),
        ]
        for tbl, col, col_def in migrations:
            try:
                await db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Column already exists

        await db.commit()
        await seed_demo_users_and_data(db)

    print(f"[FORGE-VISION] Database initialized with demo accounts at {DB_PATH}")

