from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from identity.did import DID
from identity.reputation import ReputationRegistry

identity_router = APIRouter()
reputation = ReputationRegistry()

# In-memory DID store (will be persisted later)
did_store: dict = {}


class VerifyRequest(BaseModel):
    did: str
    message: str
    signature: str
    public_key: str


class ReputationAction(BaseModel):
    amount: float
    reason: str


@identity_router.post("/did/create")
def create_did():
    identity = DID()
    did_store[identity.did] = {
        "public_key": identity.export_public_key(),
        "private_key": identity.private_key.private_bytes_raw().hex()
    }
    reputation.new_identity(identity.did)
    return {
        "did": identity.did,
        "public_key": identity.export_public_key()[:32] + "...",
        "private_key": identity.private_key.private_bytes_raw().hex()[:32] + "..."
    }


@identity_router.post("/did/verify")
def verify_did(req: VerifyRequest):
    valid = DID.verify(req.did, req.message, req.signature, req.public_key)
    return {"did": req.did, "valid": valid}


@identity_router.get("/reputation/{did}")
def get_reputation(did: str):
    score = reputation.get_score(did)
    if score is None:
        raise HTTPException(status_code=404, detail="DID not found")
    return {
        "did": did,
        "score": score,
        "standing": reputation.get_standing(did),
        "history": reputation.get_history(did)
    }


@identity_router.post("/reputation/{did}/increment")
def increment_reputation(did: str, req: ReputationAction):
    reputation.increment(did, req.amount, req.reason)
    return {"did": did, "score": reputation.get_score(did), "standing": reputation.get_standing(did)}


@identity_router.post("/reputation/{did}/decrement")
def decrement_reputation(did: str, req: ReputationAction):
    reputation.decrement(did, req.amount, req.reason)
    return {"did": did, "score": reputation.get_score(did), "standing": reputation.get_standing(did)}
