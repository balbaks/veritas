from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from economic.escrow import EconomicEngine
from economic.database import save_transaction, save_escrow
from identity.did import DID
from typing import Optional

economic_router = APIRouter()
economic_engine = EconomicEngine()

did_store_ref = None


def _verify_did(did: str, message: str, signature: str) -> bool:
    if did_store_ref is None:
        return False
    pub_key = did_store_ref.get(did, {}).get("public_key")
    if not pub_key:
        return False
    return DID.verify(did, message, signature, pub_key)


class CreateTransactionRequest(BaseModel):
    buyer_did: str
    seller_did: str
    agent_id: str
    amount: float
    currency: str
    description: str
    signature: str
    message: str


class FundRequest(BaseModel):
    tx_id: str
    buyer_did: str
    signature: str
    message: str


class ReleaseRequest(BaseModel):
    escrow_id: str
    seller_did: str
    signature: str
    message: str


class DisputeRequest(BaseModel):
    escrow_id: str
    filed_by: str
    reason: str
    proof_hash: str
    signature: str
    message: str


class ResolveRequest(BaseModel):
    escrow_id: str
    favor_buyer: bool
    resolved_by: str
    signature: str
    message: str


@economic_router.post("/transaction")
async def create_transaction(req: CreateTransactionRequest):
    if not _verify_did(req.buyer_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid buyer signature")
    tx_id = economic_engine.create_transaction(
        req.buyer_did, req.seller_did, req.agent_id,
        req.amount, req.currency, req.description
    )
    await save_transaction(economic_engine.get_transaction(tx_id))
    return {"tx_id": tx_id, "status": "pending"}


@economic_router.post("/escrow/fund")
async def fund_escrow(req: FundRequest):
    if not _verify_did(req.buyer_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid buyer signature")
    escrow_id = economic_engine.fund_escrow(req.tx_id)
    if not escrow_id:
        raise HTTPException(status_code=404, detail="Transaction not found or already funded")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    await save_transaction(economic_engine.get_transaction(req.tx_id))
    return {"escrow_id": escrow_id, "status": "funded"}


@economic_router.post("/escrow/{escrow_id}/release")
async def release_escrow(escrow_id: str, req: ReleaseRequest):
    if not _verify_did(req.seller_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid seller signature")
    success = economic_engine.release_escrow(escrow_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot release")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    escrow = economic_engine.get_escrow(escrow_id)
    await save_transaction(economic_engine.get_transaction(escrow["tx_id"]))
    return {"escrow_id": escrow_id, "status": "released"}


@economic_router.post("/escrow/{escrow_id}/dispute")
async def file_dispute(escrow_id: str, req: DisputeRequest):
    if not _verify_did(req.filed_by, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    success = economic_engine.file_dispute(escrow_id, req.filed_by, req.reason, req.proof_hash)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot dispute")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    escrow = economic_engine.get_escrow(escrow_id)
    await save_transaction(economic_engine.get_transaction(escrow["tx_id"]))
    return {"escrow_id": escrow_id, "status": "disputed"}


@economic_router.post("/escrow/{escrow_id}/resolve")
async def resolve_dispute(escrow_id: str, req: ResolveRequest):
    if not _verify_did(req.resolved_by, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid resolver signature")
    success = economic_engine.resolve_dispute(escrow_id, req.favor_buyer, req.resolved_by)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resolve")
    await save_escrow(economic_engine.get_escrow(escrow_id))
    escrow = economic_engine.get_escrow(escrow_id)
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
