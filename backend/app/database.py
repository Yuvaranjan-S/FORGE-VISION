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
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "db", "forensiq.db"))

SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.sql"))

# Ensure database directory exists immediately
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

        # Check if users table is empty; if so, trigger auto-seeding
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            res = await cur.fetchone()
            count = res[0] if res else 0

    if count == 0:
        print("[FORGE-VISION] Empty database detected. Auto-seeding default demo users & cases...")
        try:
            import sys
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            from seed import seed as run_seed
            await run_seed()
        except Exception as e:
            print(f"[FORGE-VISION] Auto-seed error/warning: {e}")

    print(f"[FORGE-VISION] Database initialized at {DB_PATH}")

