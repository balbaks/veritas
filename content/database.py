import aiosqlite
import json
from core.database import DB_PATH


async def init_content_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                hash TEXT PRIMARY KEY,
                size INTEGER,
                mime_type TEXT,
                creator_did TEXT,
                timestamp TEXT,
                metadata TEXT,
                origin_verified INTEGER,
                ai_generated_score REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS edits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT,
                editor_did TEXT,
                new_hash TEXT,
                edit_type TEXT,
                timestamp TEXT,
                FOREIGN KEY (content_hash) REFERENCES contents(hash)
            )
        """)
        await db.commit()


async def save_content(content_hash: str, size: int, mime_type: str, creator_did: str, timestamp: str, metadata: dict, origin_verified: bool, ai_score: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO contents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (content_hash, size, mime_type, creator_did, timestamp, json.dumps(metadata), int(origin_verified), ai_score)
        )
        await db.commit()


async def save_edit(content_hash: str, editor_did: str, new_hash: str, edit_type: str, timestamp: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO edits (content_hash, editor_did, new_hash, edit_type, timestamp) VALUES (?, ?, ?, ?, ?)",
            (content_hash, editor_did, new_hash, edit_type, timestamp)
        )
        await db.commit()


async def load_contents(registry):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM contents")
        rows = await cursor.fetchall()
        for row in rows:
            registry.contents[row[0]] = {
                "hash": row[0],
                "size": row[1],
                "mime_type": row[2],
                "creator_did": row[3],
                "timestamp": row[4],
                "metadata": json.loads(row[5]),
                "origin_verified": bool(row[6]),
                "ai_generated_score": row[7],
                "edit_chain": []
            }
        cursor = await db.execute("SELECT * FROM edits")
        rows = await cursor.fetchall()
        for row in rows:
            content_hash = row[1]
            if content_hash in registry.contents:
                registry.contents[content_hash]["edit_chain"].append({
                    "editor_did": row[2],
                    "new_hash": row[3],
                    "edit_type": row[4],
                    "timestamp": row[5]
                })
