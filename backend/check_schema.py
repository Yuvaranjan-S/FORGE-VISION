import asyncio, aiosqlite, sys, os
sys.path.insert(0, os.path.abspath("."))
from app.database import DB_PATH

async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(evidence)") as cur:
            cols = await cur.fetchall()
        print(f"evidence table has {len(cols)} columns:")
        for c in cols:
            print(f"  {c[0]:3d}. {c[1]}")
        # Also check failed_files in recent jobs
        async with db.execute("SELECT COUNT(*) FROM evidence WHERE source_type='PUBLIC_RESEARCH_DATASET'") as cur:
            row = await cur.fetchone()
        print(f"\nPublic research evidence rows in DB: {row[0]}")

asyncio.run(main())
