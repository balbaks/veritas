from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from economic.escrow import EconomicEngine
from economic.database import save_transaction, save_escrow
from identity.did import DID

economic_router = APIRouter()
economic_engine = EconomicEngine()

did_store_ref = None


def _verify_did(did: str, message: str, signature: str, timestamp: str) -> bool:
    if did_store_ref is None:
        return False
    pub_key = did_store_ref.get(did, {}).get("public_key")
    if not pub_key:
        return False
    return DID.verify_with_timestamp(did, message, signature, pub_key, timestamp)


class CreateTransactionRequest(BaseModel):
    buyer_did: str
    seller_did: str
    agent_id: str
    amount: float
    currency: str
    description: str
    signature: str
    timestamp: str


class FundRequest(BaseModel):
    tx_id: str
    buyer_did: str
    signature: str
    timestamp: str


class ReleaseRequest(BaseModel):
    escrow_id: str
    seller_did: str
    signature: str
    timestamp: str


class DisputeRequest(BaseModel):
    escrow_id: str
    filed_by: str
    reason: str
    proof_hash: str
    signature: str
    timestamp: str


class ResolveRequest(BaseModel):
    escrow_id: str
    favor_buyer: bool
    resolved_by: str
    signature: str
    timestamp: str


@economic_router.post("/transaction")
async def create_transaction(req: CreateTransactionRequest):
    msg = DID.build_message("economic_transaction", {
        "amount": str(req.amount), "buyer_did": req.buyer_did,
        "currency": req.currency, "seller_did": req.seller_did
    }, req.timestamp)
    if not _verify_did(req.buyer_did, msg, req.signature, req.timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired buyer signature")
    tx_id = economic_engine.create_transaction(
        req.buyer_did, req.seller_did, req.agent_id,
        req.amount, req.currency, req.description
    )
    await save_transaction(economic_engine.get_transaction(tx_id))
    return {"tx_id": tx_id, "status": "pending"}


@economic_router.post("/escrow/fund")
async def fund_escrow(req: FundRequest):
    msg = DID.build_message("economic_fund", {"buyer_did": req.buyer_did, "tx_id": req.tx_id}, req.timestamp)
    if not _verify_did(req.buyer_did, msg, req.signature, req.timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired buyer signature")

    tx = economic_engine.get_transaction(req.tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if req.buyer_did != tx["buyer_did"]:
        raise HTTPException(status_code=403, detail="Only the transaction buyer can fund escrow")

    escrow_id = economic_engine.fund_escrow(req.tx_id)
    if not escrow_id:
        raise HTTPException(status_code=400, detail="Transaction not found or already funded")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    await save_transaction(economic_engine.get_transaction(req.tx_id))
    return {"escrow_id": escrow_id, "status": "funded"}


@economic_router.post("/escrow/{escrow_id}/release")
async def release_escrow(escrow_id: str, req: ReleaseRequest):
    msg = DID.build_message("economic_release", {"escrow_id": escrow_id, "seller_did": req.seller_did}, req.timestamp)
    if not _verify_did(req.seller_did, msg, req.signature, req.timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired seller signature")

    escrow = economic_engine.get_escrow(escrow_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    if req.seller_did != escrow["seller_did"]:
        raise HTTPException(status_code=403, detail="Only the escrow seller can release funds")

    success = economic_engine.release_escrow(escrow_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot release")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    await save_transaction(economic_engine.get_transaction(escrow["tx_id"]))
    return {"escrow_id": escrow_id, "status": "released"}


@economic_router.post("/escrow/{escrow_id}/dispute")
async def file_dispute(escrow_id: str, req: DisputeRequest):
    msg = DID.build_message("economic_dispute", {
        "escrow_id": escrow_id, "filed_by": req.filed_by, "reason": req.reason
    }, req.timestamp)
    if not _verify_did(req.filed_by, msg, req.signature, req.timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")

    escrow = economic_engine.get_escrow(escrow_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    if req.filed_by not in [escrow["buyer_did"], escrow["seller_did"]]:
        raise HTTPException(status_code=403, detail="Only escrow buyer or seller can file dispute")

    success = economic_engine.file_dispute(escrow_id, req.filed_by, req.reason, req.proof_hash)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot dispute")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    await save_transaction(economic_engine.get_transaction(escrow["tx_id"]))
    return {"escrow_id": escrow_id, "status": "disputed"}


@economic_router.post("/escrow/{escrow_id}/resolve")
async def resolve_dispute(escrow_id: str, req: ResolveRequest):
    msg = DID.build_message("economic_resolve", {
        "escrow_id": escrow_id, "favor_buyer": str(req.favor_buyer), "resolved_by": req.resolved_by
    }, req.timestamp)
    if not _verify_did(req.resolved_by, msg, req.signature, req.timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired resolver signature")

    escrow = economic_engine.get_escrow(escrow_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")

    from api.governance_routes import gov_engine
    if not gov_engine.is_arbiter(req.resolved_by):
        raise HTTPException(status_code=403, detail="Only elected arbiters can resolve disputes")

    success = economic_engine.resolve_dispute(escrow_id, req.favor_buyer, req.resolved_by)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resolve")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    await save_transaction(economic_engine.get_transaction(escrow["tx_id"]))
    return {"escrow_id": escrow_id, "status": "resolved"}


@economic_router.get("/transaction/{tx_id}")
def get_transaction(tx_id: str):
    tx = economic_engine.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@economic_router.get("/escrow/{escrow_id}")
def get_escrow(escrow_id: str):
    escrow = economic_engine.get_escrow(escrow_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    return escrow
