from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.registry import AgentRegistry
from agents.delegation import DelegationManager
from agents.database import save_dispute, save_agent, save_delegation
from identity.did import verify_request
from datetime import datetime, timezone
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
    timestamp: str


class TransactionRequest(BaseModel):
    agent_id: str
    success: bool
    details: str
    authorized_by: str
    signature: str
    timestamp: str


class DisputeRequest(BaseModel):
    agent_id: str
    details: str
    filed_by: str
    signature: str
    timestamp: str


class DelegateRequest(BaseModel):
    owner_did: str
    agent_id: str
    permissions: List[str]
    duration_hours: int = 24
    signature: str
    timestamp: str


class RevokeRequest(BaseModel):
    delegation_id: str
    owner_did: str
    signature: str
    timestamp: str


class LogActionRequest(BaseModel):
    delegation_id: str
    action: str
    details: str
    authorized_by: str
    signature: str
    timestamp: str


@agent_router.post("/register")
async def register_agent(req: RegisterAgentRequest):
    if not verify_request(req.owner_did, "agent.register",
                          {"agent_type": req.agent_type, "owner_did": req.owner_did},
                          req.timestamp, req.signature, did_store_ref or {}):
        raise HTTPException(status_code=403, detail="Invalid or expired owner signature")
    agent_id = agent_registry.register(
        req.owner_did, req.agent_type, req.capabilities, req.metadata
    )
    await save_agent(agent_registry.get(agent_id))
    return {"agent_id": agent_id, "owner_did": req.owner_did, "agent_type": req.agent_type}


@agent_router.post("/delegate")
async def delegate(req: DelegateRequest):
    if not verify_request(req.owner_did, "agent.delegate",
                          {"agent_id": req.agent_id, "owner_did": req.owner_did},
                          req.timestamp, req.signature, did_store_ref or {}):
        raise HTTPException(status_code=403, detail="Invalid or expired owner signature")
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
    if not verify_request(req.owner_did, "agent.delegate.revoke",
                          {"delegation_id": delegation_id, "owner_did": req.owner_did},
                          req.timestamp, req.signature, did_store_ref or {}):
        raise HTTPException(status_code=403, detail="Invalid or expired owner signature")
    delegation_manager.revoke(delegation_id)
    return {"delegation_id": delegation_id, "active": False}


@agent_router.post("/delegate/log")
def log_action(req: LogActionRequest):
    if not verify_request(req.authorized_by, "agent.delegate.log",
                          {"action": req.action, "authorized_by": req.authorized_by,
                           "delegation_id": req.delegation_id},
                          req.timestamp, req.signature, did_store_ref or {}):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")
    delegation_manager.log_action(req.delegation_id, req.action, req.details)
    return {"delegation_id": req.delegation_id, "action": req.action, "logged": True}


@agent_router.post("/{agent_id}/transaction")
def record_transaction(agent_id: str, req: TransactionRequest):
    if not verify_request(req.authorized_by, "agent.transaction",
                          {"agent_id": agent_id, "authorized_by": req.authorized_by,
                           "success": req.success},
                          req.timestamp, req.signature, did_store_ref or {}):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")

    agent = agent_registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    is_owner = agent["owner_did"] == req.authorized_by
    has_delegation = len(delegation_manager.get_agent_delegations(agent_id, req.authorized_by)) > 0

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
    if not verify_request(req.filed_by, "agent.dispute",
                          {"agent_id": agent_id, "filed_by": req.filed_by},
                          req.timestamp, req.signature, did_store_ref or {}):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")
    agent_registry.file_dispute(agent_id, req.details, req.filed_by)
    await save_dispute(agent_id, req.details, req.filed_by, datetime.now(timezone.utc).isoformat())
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
