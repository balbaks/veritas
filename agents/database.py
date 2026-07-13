import aiosqlite
import json
from agents.registry import AgentRegistry
from agents.delegation import DelegationManager

DB_PATH = "veritas.db"


async def init_agent_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                owner_did TEXT,
                agent_type TEXT,
                capabilities TEXT,
                metadata TEXT,
                created_at TEXT,
                active INTEGER,
                trust_score REAL,
                transactions_count INTEGER,
                successful_transactions INTEGER,
                failed_transactions INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_disputes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                details TEXT,
                filed_by TEXT,
                timestamp TEXT,
                resolved INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS delegations (
                delegation_id TEXT PRIMARY KEY,
                owner_did TEXT,
                agent_id TEXT,
                permissions TEXT,
                created_at TEXT,
                expires_at TEXT,
                active INTEGER
            )
        """)
        await db.commit()


async def save_agent(agent: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO agents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (agent["agent_id"], agent["owner_did"], agent["agent_type"],
             json.dumps(agent["capabilities"]), json.dumps(agent["metadata"]),
             agent["created_at"], int(agent["active"]), agent["trust_score"],
             agent["transactions_count"], agent["successful_transactions"],
             agent["failed_transactions"])
        )
        await db.commit()


async def save_delegation(del_data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO delegations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (del_data["delegation_id"], del_data["owner_did"], del_data["agent_id"],
             json.dumps(del_data["permissions"]), del_data["created_at"],
             del_data["expires_at"], int(del_data["active"]))
        )
        await db.commit()


async def save_dispute(agent_id: str, details: str, filed_by: str, timestamp: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO agent_disputes (agent_id, details, filed_by, timestamp, resolved) VALUES (?, ?, ?, ?, 0)",
            (agent_id, details, filed_by, timestamp)
        )
        await db.commit()


async def load_agents(agent_registry: AgentRegistry):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM agents")
        rows = await cursor.fetchall()
        for row in rows:
            agent_registry.agents[row[0]] = {
                "agent_id": row[0], "owner_did": row[1], "agent_type": row[2],
                "capabilities": json.loads(row[3]), "metadata": json.loads(row[4]),
                "created_at": row[5], "active": bool(row[6]), "trust_score": row[7],
                "transactions_count": row[8], "successful_transactions": row[9],
                "failed_transactions": row[10], "disputes": []
            }
        cursor = await db.execute("SELECT * FROM agent_disputes ORDER BY timestamp")
        dispute_rows = await cursor.fetchall()
        for row in dispute_rows:
            agent_id = row[1]
            if agent_id in agent_registry.agents:
                agent_registry.agents[agent_id]["disputes"].append({
                    "details": row[2],
                    "filed_by": row[3],
                    "timestamp": row[4],
                    "resolved": bool(row[5])
                })


async def load_delegations(delegation_manager: DelegationManager):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM delegations")
        rows = await cursor.fetchall()
        for row in rows:
            delegation_manager.delegations[row[0]] = {
                "delegation_id": row[0], "owner_did": row[1], "agent_id": row[2],
                "permissions": json.loads(row[3]), "created_at": row[4],
                "expires_at": row[5], "active": bool(row[6]), "actions_taken": []
            }
