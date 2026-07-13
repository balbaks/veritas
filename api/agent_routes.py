from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.registry import AgentRegistry
from agents.delegation import DelegationManager
from agents.database import save_dispute, save_agent, save_delegation
from identity.did import DID
from datetime import datetime
from typing import List, Optional

agent_router = APIRouter()
agent_registry = AgentRegistry()
delegation_manager = DelegationManager()

did_store_ref = None


class RegisterAgentRequest(BaseModel):
    owner_did: str
    agent_type: str
    capabilities: List[str]
    metadata: Optional[dict] = None
    signature: str
    message: str


class TransactionRequest(BaseModel):
    agent_id: str
    success: bool
    details: str
    authorized_by: str
    signature: str
    message: str


class DisputeRequest(BaseModel):
    agent_id: str
    details: str
    filed_by: str
    signature: str
    message: str


class DelegateRequest(BaseModel):
    owner_did: str
    agent_id: str
    permissions: List[str]
    duration_hours: int = 24
    signature: str
    message: str


class RevokeRequest(BaseModel):
    delegation_id: str
    owner_did: str
    signature: str
    message: str


class LogActionRequest(BaseModel):
    delegation_id: str
    action: str
    details: str


def _verify_did(did: str, message: str, signature: str) -> bool:
    if did_store_ref is None:
        return False
    pub_key = did_store_ref.get(did, {}).get("public_key")
    if not pub_key:
        return False
    return DID.verify(did, message, signature, pub_key)


@agent_router.post("/register")
async def register_agent(req: RegisterAgentRequest):
    if not _verify_did(req.owner_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid owner signature")
    agent_id = agent_registry.register(
        req.owner_did, req.agent_type, req.capabilities, req.metadata
    )
    await save_agent(agent_registry.get(agent_id))
    return {
        "agent_id": agent_id,
        "owner_did": req.owner_did,
        "agent_type": req.agent_type
    }


@agent_router.post("/delegate")
async def delegate(req: DelegateRequest):
    if not _verify_did(req.owner_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid owner signature")
    del_id = delegation_manager.delegate(
        req.owner_did, req.agent_id, req.permissions, req.duration_hours
    )
    await save_delegation(delegation_manager.delegations[del_id])
    return {
        "delegation_id": del_id,
        "owner_did": req.owner_did,
        "agent_id": req.agent_id,
        "expires_in_hours": req.duration_hours
    }


@agent_router.get("/delegate/check/{agent_id}/{permission}")
def check_permission(agent_id: str, permission: str):
    has_perm = delegation_manager.check_permission(agent_id, permission)
    return {"agent_id": agent_id, "permission": permission, "granted": has_perm}


@agent_router.get("/owner/{owner_did}/delegations")
def get_owner_delegations(owner_did: str):
    return delegation_manager.get_active_delegations(owner_did)


@agent_router.post("/delegate/{delegation_id}/revoke")
def revoke_delegation(delegation_id: str, req: RevokeRequest):
    if not _verify_did(req.owner_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid owner signature")
    delegation_manager.revoke(delegation_id)
    return {"delegation_id": delegation_id, "active": False}


@agent_router.post("/delegate/log")
def log_action(req: LogActionRequest):
    delegation_manager.log_action(req.delegation_id, req.action, req.details)
    return {"delegation_id": req.delegation_id, "action": req.action, "logged": True}


@agent_router.post("/{agent_id}/transaction")
def record_transaction(agent_id: str, req: TransactionRequest):
    if not _verify_did(req.authorized_by, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    agent = agent_registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    is_owner = agent["owner_did"] == req.authorized_by
    has_delegation = len(delegation_manager.get_agent_delegations(agent_id)) > 0

    if not is_owner and not has_delegation:
        raise HTTPException(status_code=403, detail="Not authorized to record transactions for this agent")

    agent_registry.record_transaction(agent_id, req.success, req.details)
    agent = agent_registry.get(agent_id)
    return {
        "agent_id": agent_id,
        "trust_score": agent["trust_score"],
        "standing": agent_registry.get_standing(agent_id)
    }


@agent_router.post("/{agent_id}/dispute")
async def file_dispute(agent_id: str, req: DisputeRequest):
    if not _verify_did(req.filed_by, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    agent_registry.file_dispute(agent_id, req.details, req.filed_by)
    await save_dispute(agent_id, req.details, req.filed_by, datetime.utcnow().isoformat())
    agent = agent_registry.get(agent_id)
    return {
        "agent_id": agent_id,
        "trust_score": agent["trust_score"],
        "standing": agent_registry.get_standing(agent_id)
    }


@agent_router.get("/{agent_id}")
def get_agent(agent_id: str):
    agent = agent_registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
