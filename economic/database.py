import aiosqlite
import json
from economic.escrow import EconomicEngine, EscrowStatus
from core.database import DB_PATH


async def init_economic_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                buyer_did TEXT,
                seller_did TEXT,
                agent_id TEXT,
                amount REAL,
                currency TEXT,
                description TEXT,
                created_at TEXT,
                status TEXT,
                escrow_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transaction_disputes (
                tx_id TEXT PRIMARY KEY,
                filed_by TEXT,
                reason TEXT,
                proof_hash TEXT,
                filed_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS escrows (
                escrow_id TEXT PRIMARY KEY,
                tx_id TEXT,
                amount REAL,
                currency TEXT,
                buyer_did TEXT,
                seller_did TEXT,
                status TEXT,
                funded_at TEXT,
                released_at TEXT,
                dispute_at TEXT,
                resolution TEXT
            )
        """)
        await db.commit()


async def save_transaction(tx: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tx["tx_id"], tx["buyer_did"], tx["seller_did"], tx["agent_id"],
             tx["amount"], tx["currency"], tx["description"], tx["created_at"],
             tx["status"], tx.get("escrow_id"))
        )
        await db.commit()

    if tx.get("dispute"):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO transaction_disputes (tx_id, filed_by, reason, proof_hash, filed_at) VALUES (?, ?, ?, ?, ?)",
                (tx["tx_id"], tx["dispute"]["filed_by"], tx["dispute"]["reason"],
                 tx["dispute"]["proof_hash"], tx["dispute"]["filed_at"])
            )
            await db.commit()


async def save_escrow(escrow: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO escrows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (escrow["escrow_id"], escrow["tx_id"], escrow["amount"], escrow["currency"],
             escrow["buyer_did"], escrow["seller_did"], escrow["status"].value,
             escrow["funded_at"], escrow.get("released_at"), escrow.get("dispute_at"),
             json.dumps(escrow.get("resolution")))
        )
        await db.commit()


async def load_economic_data(engine: EconomicEngine):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM transactions")
        rows = await cursor.fetchall()
        for row in rows:
            engine.transactions[row[0]] = {
                "tx_id": row[0], "buyer_did": row[1], "seller_did": row[2],
                "agent_id": row[3], "amount": row[4], "currency": row[5],
                "description": row[6], "created_at": row[7], "status": row[8],
                "escrow_id": row[9], "proofs": [], "dispute": None
            }
        cursor = await db.execute("SELECT * FROM transaction_disputes")
        rows = await cursor.fetchall()
        for row in rows:
            tx_id = row[0]
            if tx_id in engine.transactions:
                engine.transactions[tx_id]["dispute"] = {
                    "filed_by": row[1],
                    "reason": row[2],
                    "proof_hash": row[3],
                    "filed_at": row[4]
                }
        cursor = await db.execute("SELECT * FROM escrows")
        rows = await cursor.fetchall()
        for row in rows:
            engine.escrows[row[0]] = {
                "escrow_id": row[0], "tx_id": row[1], "amount": row[2],
                "currency": row[3], "buyer_did": row[4], "seller_did": row[5],
                "status": EscrowStatus(row[6]), "funded_at": row[7],
                "released_at": row[8], "dispute_at": row[9],
                "resolution": json.loads(row[10]) if row[10] else None
            }
