import hashlib
from datetime import datetime, timezone
from typing import Optional


class AgentRegistry:
    def __init__(self):
        self.agents: dict = {}

    def register(self, owner_did: str, agent_type: str, capabilities: list, metadata: dict = None) -> str:
        agent_data = f"{owner_did}{agent_type}{str(capabilities)}{datetime.now(timezone.utc).isoformat()}"
        agent_id = hashlib.sha256(agent_data.encode()).hexdigest()[:16]
        
        self.agents[agent_id] = {
            "agent_id": agent_id,
            "owner_did": owner_did,
            "agent_type": agent_type,
            "capabilities": capabilities,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
            "trust_score": 50.0,
            "transactions_count": 0,
            "successful_transactions": 0,
            "failed_transactions": 0,
            "disputes": []
        }
        return agent_id

    def get(self, agent_id: str) -> Optional[dict]:
        return self.agents.get(agent_id)

    def deactivate(self, agent_id: str):
        if agent_id in self.agents:
            self.agents[agent_id]["active"] = False

    def record_transaction(self, agent_id: str, success: bool, details: str):
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent["transactions_count"] += 1
            if success:
                agent["successful_transactions"] += 1
            else:
                agent["failed_transactions"] += 1
            self._recalculate_trust(agent_id)

    def file_dispute(self, agent_id: str, dispute_details: str, filed_by: str):
        if agent_id in self.agents:
            self.agents[agent_id]["disputes"].append({
                "details": dispute_details,
                "filed_by": filed_by,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "resolved": False
            })
            self.agents[agent_id]["trust_score"] = max(0, self.agents[agent_id]["trust_score"] - 10)

    def _recalculate_trust(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if not agent or agent["transactions_count"] == 0:
            return
        success_rate = agent["successful_transactions"] / agent["transactions_count"]
        dispute_penalty = len([d for d in agent["disputes"] if not d["resolved"]]) * 5
        agent["trust_score"] = max(0, min(100, (success_rate * 100) - dispute_penalty))

    def get_standing(self, agent_id: str) -> str:
        agent = self.agents.get(agent_id)
        if not agent:
            return "UNKNOWN"
        if not agent["active"]:
            return "INACTIVE"
        score = agent["trust_score"]
        if score >= 80:
            return "TRUSTED_AGENT"
        elif score >= 60:
            return "RELIABLE_AGENT"
        elif score >= 40:
            return "NEUTRAL_AGENT"
        elif score >= 20:
            return "UNRELIABLE_AGENT"
        else:
            return "MALICIOUS_AGENT"
