import aiosqlite
import json
from governance.proposals import GovernanceEngine, ProposalStatus, ProposalType
from governance.curation import CurationEngine

DB_PATH = "veritas.db"


async def init_governance_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                prop_id TEXT PRIMARY KEY,
                proposer_did TEXT,
                title TEXT,
                description TEXT,
                proposal_type TEXT,
                changes TEXT,
                status TEXT,
                created_at TEXT,
                expires_at TEXT,
                votes_for REAL,
                votes_against REAL,
                voters TEXT,
                executed_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS arbiters (
                did TEXT PRIMARY KEY,
                elected_at TEXT,
                proposal_id TEXT,
                active INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS curated_lists (
                list_id TEXT PRIMARY KEY,
                owner_did TEXT,
                name TEXT,
                description TEXT,
                criteria TEXT,
                items TEXT,
                curators TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.commit()


async def save_proposal(prop: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO proposals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (prop["prop_id"], prop["proposer_did"], prop["title"], prop["description"],
             prop["proposal_type"].value, json.dumps(prop["changes"]), prop["status"].value,
             prop["created_at"], prop["expires_at"], prop["votes_for"], prop["votes_against"],
             json.dumps(prop["voters"]), prop.get("executed_at"))
        )
        await db.commit()


async def save_arbiter(did: str, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO arbiters VALUES (?, ?, ?, ?)",
            (did, data["elected_at"], data["proposal_id"], int(data["active"]))
        )
        await db.commit()


async def save_curated_list(lst: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO curated_lists VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lst["list_id"], lst["owner_did"], lst["name"], lst["description"],
             json.dumps(lst["criteria"]), json.dumps(lst["items"]), json.dumps(lst["curators"]),
             lst["created_at"], lst["updated_at"])
        )
        await db.commit()


async def load_governance_data(gov_engine: GovernanceEngine, curation_engine: CurationEngine):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM proposals")
        rows = await cursor.fetchall()
        for row in rows:
            gov_engine.proposals[row[0]] = {
                "prop_id": row[0], "proposer_did": row[1], "title": row[2],
                "description": row[3], "proposal_type": ProposalType(row[4]),
                "changes": json.loads(row[5]), "status": ProposalStatus(row[6]),
                "created_at": row[7], "expires_at": row[8], "votes_for": row[9],
                "votes_against": row[10], "voters": json.loads(row[11]),
                "executed_at": row[12]
            }
        cursor = await db.execute("SELECT * FROM arbiters")
        rows = await cursor.fetchall()
        for row in rows:
            gov_engine.arbiters[row[0]] = {
                "did": row[0], "elected_at": row[1], "proposal_id": row[2], "active": bool(row[3])
            }
        cursor = await db.execute("SELECT * FROM curated_lists")
        rows = await cursor.fetchall()
        for row in rows:
            curation_engine.curated_lists[row[0]] = {
                "list_id": row[0], "owner_did": row[1], "name": row[2],
                "description": row[3], "criteria": json.loads(row[4]),
                "items": json.loads(row[5]), "curators": json.loads(row[6]),
                "created_at": row[7], "updated_at": row[8]
            }
