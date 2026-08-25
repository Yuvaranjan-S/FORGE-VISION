import asyncio, aiosqlite, os, sys
sys.path.insert(0, ".")
from app.database import DB_PATH

async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, camera_id, original_filename, file_path, file_size_bytes FROM evidence WHERE case_id=? ORDER BY camera_id",
            ("CASE-DEMO001",)
        ) as cur:
            rows = await cur.fetchall()
        print(f"{'Evidence ID':30s} {'Camera':12s} {'File Exists':12s} {'Filename'}")
        print("-" * 90)
        for r in rows[:10]:
            fp = r["file_path"] or ""
            exists = os.path.exists(fp) if fp else False
            fn = r["original_filename"] or os.path.basename(fp)
            print(f"{r['id']:30s} {r['camera_id']:12s} {'YES' if exists else 'NO':12s} {fn}")

asyncio.run(main())
