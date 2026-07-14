from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from identity.did import DID, verify_request
from identity.reputation import ReputationRegistry
from identity.database import save_identity, save_reputation_event, save_stake
from datetime import datetime, timezone

identity_router = APIRouter()
reputation = ReputationRegistry()
did_store: dict = {}


class ReputationAction(BaseModel):
    amount: float
    reason: str
    signature: str
    timestamp: str


class StakeRequest(BaseModel):
    did: str
    amount: float
    signature: str
    timestamp: str


@identity_router.post("/did/create")
async def create_did():
    identity = DID()
    public_key = identity.export_public_key()
    private_key = identity.private_key.private_bytes_raw().hex()
    created_at = datetime.now(timezone.utc).isoformat()

    did_store[identity.did] = {"public_key": public_key}
    reputation.new_identity(identity.did)
    await save_identity(identity.did, public_key, created_at)

    return {
        "did": identity.did,
        "public_key": public_key,
        "private_key": private_key,
        "warning": "STORE THIS PRIVATE KEY SECURELY. It will NEVER be shown again and is NOT stored on the server."
    }


@identity_router.get("/reputation/{did}")
def get_reputation(did: str):
    score = reputation.get_score(did)
    if score is None:
        raise HTTPException(status_code=404, detail="DID not found")
    return {
        "did": did,
        "score": score,
        "standing": reputation.get_standing(did),
        "history": reputation.get_history(did),
        "staked": reputation.stakes.get(did, 0)
    }


@identity_router.post("/reputation/{did}/increment")
async def increment_reputation(did: str, req: ReputationAction):
    if not verify_request(did, "identity.reputation.increment",
                          {"amount": req.amount, "did": did, "reason": req.reason},
                          req.timestamp, req.signature, did_store):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")
    reputation.increment(did, req.amount, req.reason)
    await save_reputation_event(did, "increment", req.amount, req.reason, datetime.now(timezone.utc).isoformat())
    return {"did": did, "score": reputation.get_score(did), "standing": reputation.get_standing(did)}


@identity_router.post("/reputation/{did}/decrement")
async def decrement_reputation(did: str, req: ReputationAction):
    if not verify_request(did, "identity.reputation.decrement",
                          {"amount": req.amount, "did": did, "reason": req.reason},
                          req.timestamp, req.signature, did_store):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")
    reputation.decrement(did, req.amount, req.reason)
    await save_reputation_event(did, "decrement", req.amount, req.reason, datetime.now(timezone.utc).isoformat())
    return {"did": did, "score": reputation.get_score(did), "standing": reputation.get_standing(did)}


@identity_router.post("/stake")
async def stake(req: StakeRequest):
    if not verify_request(req.did, "identity.stake",
                          {"amount": req.amount, "did": req.did},
                          req.timestamp, req.signature, did_store):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")
    success = reputation.stake(req.did, req.amount)
    if not success:
        raise HTTPException(status_code=400, detail="Stake amount must be positive")
    await save_stake(req.did, reputation.stakes.get(req.did, 0))
    return {"did": req.did, "staked": req.amount, "total_staked": reputation.stakes.get(req.did, 0)}
