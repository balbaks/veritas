from datetime import datetime, timedelta, timezone
from typing import Optional


class DelegationManager:
    def __init__(self):
        self.delegations: dict = {}

    def delegate(self, owner_did: str, agent_id: str, permissions: list, duration_hours: int = 24) -> str:
        delegation_id = f"del:{owner_did}:{agent_id}:{datetime.now(timezone.utc).timestamp()}"
        self.delegations[delegation_id] = {
            "delegation_id": delegation_id,
            "owner_did": owner_did,
            "agent_id": agent_id,
            "permissions": permissions,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat(),
            "active": True,
            "actions_taken": []
        }
        return delegation_id

    def revoke(self, delegation_id: str):
        if delegation_id in self.delegations:
            self.delegations[delegation_id]["active"] = False

    def check_permission(self, agent_id: str, permission: str) -> bool:
        for d in self.delegations.values():
            if d["agent_id"] == agent_id and d["active"]:
                if datetime.fromisoformat(d["expires_at"]) > datetime.now(timezone.utc):
                    if permission in d["permissions"]:
                        return True
        return False

    def log_action(self, delegation_id: str, action: str, details: str):
        if delegation_id in self.delegations:
            self.delegations[delegation_id]["actions_taken"].append({
                "action": action,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    def get_active_delegations(self, owner_did: str) -> list:
        active = []
        for d in self.delegations.values():
            if d["owner_did"] == owner_did and d["active"]:
                if datetime.fromisoformat(d["expires_at"]) > datetime.now(timezone.utc):
                    active.append(d)
        return active

    def get_agent_delegations(self, agent_id: str, owner_did: str = None) -> list:
        active = []
        for d in self.delegations.values():
            if d["agent_id"] == agent_id and d["active"]:
                if datetime.fromisoformat(d["expires_at"]) > datetime.now(timezone.utc):
                    if owner_did is None or d["owner_did"] == owner_did:
                        active.append(d)
        return active
