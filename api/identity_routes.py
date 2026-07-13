from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from identity.did import DID
from identity.reputation import ReputationRegistry
from identity.database import save_identity, save_reputation_event
from datetime import datetime

identity_router = APIRouter()
reputation = ReputationRegistry()
did_store: dict = {}


class VerifyRequest(BaseModel):
    did: str
    message: str
    signature: str
    public_key: str


class ReputationAction(BaseModel):
    amount: float
    reason: str
    signature: str = None
    message: str = None


@identity_router.post("/did/create")
async def create_did():
    identity = DID()
    public_key = identity.export_public_key()
    private_key = identity.private_key.private_bytes_raw().hex()
    created_at = datetime.utcnow().isoformat()

    did_store[identity.did] = {
        "public_key": public_key
    }
    reputation.new_identity(identity.did)
    await save_identity(identity.did, public_key, created_at)

    return {
        "did": identity.did,
        "public_key": public_key,
        "private_key": private_key,
        "warning": "STORE THIS PRIVATE KEY SECURELY. It will NEVER be shown again and is NOT stored on the server."
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
async def increment_reputation(did: str, req: ReputationAction):
    if req.signature and req.message:
        pub_key = did_store.get(did, {}).get("public_key")
        if pub_key:
            valid = DID.verify(did, req.message, req.signature, pub_key)
            if not valid:
                raise HTTPException(status_code=403, detail="Invalid signature")

    reputation.increment(did, req.amount, req.reason)
    await save_reputation_event(did, "increment", req.amount, req.reason, datetime.utcnow().isoformat())
    return {"did": did, "score": reputation.get_score(did), "standing": reputation.get_standing(did)}


@identity_router.post("/reputation/{did}/decrement")
async def decrement_reputation(did: str, req: ReputationAction):
    if req.signature and req.message:
        pub_key = did_store.get(did, {}).get("public_key")
        if pub_key:
            valid = DID.verify(did, req.message, req.signature, pub_key)
            if not valid:
                raise HTTPException(status_code=403, detail="Invalid signature")

    reputation.decrement(did, req.amount, req.reason)
    await save_reputation_event(did, "decrement", req.amount, req.reason, datetime.utcnow().isoformat())
    return {"did": did, "score": reputation.get_score(did), "standing": reputation.get_standing(did)}
