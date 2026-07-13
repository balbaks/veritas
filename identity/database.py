import aiosqlite
from identity.reputation import ReputationRegistry

DB_PATH = "veritas.db"


async def init_identity_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS identities (
                did TEXT PRIMARY KEY,
                public_key TEXT,
                private_key TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reputation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                did TEXT,
                action TEXT,
                amount REAL,
                reason TEXT,
                timestamp TEXT,
                FOREIGN KEY (did) REFERENCES identities(did)
            )
        """)
        await db.commit()


async def save_identity(did: str, public_key: str, private_key: str, created_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO identities VALUES (?, ?, ?, ?)",
            (did, public_key, private_key, created_at)
        )
        await db.commit()


async def save_reputation_event(did: str, action: str, amount: float, reason: str, timestamp: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reputation_events (did, action, amount, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (did, action, amount, reason, timestamp)
        )
        await db.commit()


async def load_identities():
    identities = {}
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM identities")
        rows = await cursor.fetchall()
        for row in rows:
            identities[row[0]] = {
                "public_key": row[1],
                "private_key": row[2],
                "created_at": row[3]
            }
    return identities


async def load_reputation_events(rep_registry: ReputationRegistry):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM reputation_events ORDER BY timestamp")
        rows = await cursor.fetchall()
        for row in rows:
            did, action, amount, reason = row[1], row[2], row[3], row[4]
            if action == "increment":
                rep_registry.increment(did, amount, reason)
            elif action == "decrement":
                rep_registry.decrement(did, amount, reason)
