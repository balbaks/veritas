from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from economic.escrow import EconomicEngine
from typing import Optional

economic_router = APIRouter()
economic_engine = EconomicEngine()


class CreateTransactionRequest(BaseModel):
    buyer_did: str
    seller_did: str
    agent_id: str
    amount: float
    currency: str
    description: str


class FundRequest(BaseModel):
    tx_id: str


class DisputeRequest(BaseModel):
    escrow_id: str
    filed_by: str
    reason: str
    proof_hash: str


class ResolveRequest(BaseModel):
    escrow_id: str
    favor_buyer: bool
    resolved_by: str


@economic_router.post("/transaction")
def create_transaction(req: CreateTransactionRequest):
    tx_id = economic_engine.create_transaction(
        req.buyer_did, req.seller_did, req.agent_id,
        req.amount, req.currency, req.description
    )
    return {"tx_id": tx_id, "status": "pending"}


@economic_router.post("/escrow/fund")
def fund_escrow(req: FundRequest):
    escrow_id = economic_engine.fund_escrow(req.tx_id)
    if not escrow_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"escrow_id": escrow_id, "status": "funded"}


@economic_router.post("/escrow/{escrow_id}/release")
def release_escrow(escrow_id: str):
    success = economic_engine.release_escrow(escrow_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot release")
    return {"escrow_id": escrow_id, "status": "released"}


@economic_router.post("/escrow/{escrow_id}/dispute")
def file_dispute(escrow_id: str, req: DisputeRequest):
    success = economic_engine.file_dispute(escrow_id, req.filed_by, req.reason, req.proof_hash)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot dispute")
    return {"escrow_id": escrow_id, "status": "disputed"}


@economic_router.post("/escrow/{escrow_id}/resolve")
def resolve_dispute(escrow_id: str, req: ResolveRequest):
    success = economic_engine.resolve_dispute(escrow_id, req.favor_buyer, req.resolved_by)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resolve")
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
