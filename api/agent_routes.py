from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.registry import AgentRegistry
from agents.delegation import DelegationManager
from typing import List, Optional

agent_router = APIRouter()
agent_registry = AgentRegistry()
delegation_manager = DelegationManager()


class RegisterAgentRequest(BaseModel):
    owner_did: str
    agent_type: str
    capabilities: List[str]
    metadata: Optional[dict] = None


class TransactionRequest(BaseModel):
    agent_id: str
    success: bool
    details: str


class DisputeRequest(BaseModel):
    agent_id: str
    details: str
    filed_by: str


class DelegateRequest(BaseModel):
    owner_did: str
    agent_id: str
    permissions: List[str]
    duration_hours: int = 24


class LogActionRequest(BaseModel):
    delegation_id: str
    action: str
    details: str


@agent_router.post("/register")
def register_agent(req: RegisterAgentRequest):
    agent_id = agent_registry.register(req.owner_did, req.agent_type, req.capabilities, req.metadata)
    return {"agent_id": agent_id, "owner_did": req.owner_did, "agent_type": req.agent_type}


@agent_router.get("/{agent_id}")
def get_agent(agent_id: str):
    agent = agent_registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@agent_router.post("/{agent_id}/transaction")
def record_transaction(agent_id: str, req: TransactionRequest):
    agent_registry.record_transaction(agent_id, req.success, req.details)
    agent = agent_registry.get(agent_id)
    return {"agent_id": agent_id, "trust_score": agent["trust_score"], "standing": agent_registry.get_standing(agent_id)}


@agent_router.post("/{agent_id}/dispute")
def file_dispute(agent_id: str, req: DisputeRequest):
    agent_registry.file_dispute(agent_id, req.details, req.filed_by)
    agent = agent_registry.get(agent_id)
    return {"agent_id": agent_id, "trust_score": agent["trust_score"], "standing": agent_registry.get_standing(agent_id)}


@agent_router.post("/delegate")
def delegate(req: DelegateRequest):
    del_id = delegation_manager.delegate(req.owner_did, req.agent_id, req.permissions, req.duration_hours)
    return {"delegation_id": del_id, "owner_did": req.owner_did, "agent_id": req.agent_id, "expires_in_hours": req.duration_hours}


@agent_router.post("/delegate/{delegation_id}/revoke")
def revoke_delegation(delegation_id: str):
    delegation_manager.revoke(delegation_id)
    return {"delegation_id": delegation_id, "active": False}


@agent_router.get("/delegate/check/{agent_id}/{permission}")
def check_permission(agent_id: str, permission: str):
    has_perm = delegation_manager.check_permission(agent_id, permission)
    return {"agent_id": agent_id, "permission": permission, "granted": has_perm}


@agent_router.post("/delegate/log")
def log_action(req: LogActionRequest):
    delegation_manager.log_action(req.delegation_id, req.action, req.details)
    return {"delegation_id": req.delegation_id, "action": req.action, "logged": True}


@agent_router.get("/owner/{owner_did}/delegations")
def get_owner_delegations(owner_did: str):
    return delegation_manager.get_active_delegations(owner_did)
