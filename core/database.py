import aiosqlite
from core.models import Claim, Proof

DB_PATH = "veritas.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                subject TEXT,
                predicate TEXT,
                content_hash TEXT,
                timestamp TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS proofs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT,
                proof_type TEXT,
                proof_data TEXT,
                verifier TEXT,
                timestamp TEXT,
                FOREIGN KEY (claim_id) REFERENCES claims(id)
            )
        """)
        await db.commit()


async def save_claim(claim: Claim):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO claims VALUES (?, ?, ?, ?, ?)",
            (claim.id, claim.subject, claim.predicate, claim.content_hash, claim.timestamp)
        )
        await db.commit()


async def save_proof(proof: Proof):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO proofs (claim_id, proof_type, proof_data, verifier, timestamp) VALUES (?, ?, ?, ?, ?)",
            (proof.claim_id, proof.proof_type, proof.proof_data, proof.verifier, proof.timestamp)
        )
        await db.commit()


async def load_claims() -> dict:
    claims = {}
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM claims")
        rows = await cursor.fetchall()
        for row in rows:
            claim = Claim(id=row[0], subject=row[1], predicate=row[2], content_hash=row[3], timestamp=row[4])
            claims[claim.id] = claim
    return claims


async def load_proofs() -> dict:
    proofs = {}
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM proofs")
        rows = await cursor.fetchall()
        for row in rows:
            proof = Proof(claim_id=row[1], proof_type=row[2], proof_data=row[3], verifier=row[4], timestamp=row[5])
            if proof.claim_id not in proofs:
                proofs[proof.claim_id] = []
            proofs[proof.claim_id].append(proof)
    return proofs
