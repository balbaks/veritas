import hashlib
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


class ProposalStatus(Enum):
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class ProposalType(Enum):
    PARAMETER_CHANGE = "parameter_change"
    ARBITER_ELECTION = "arbiter_election"
    PROTOCOL_UPGRADE = "protocol_upgrade"
    DISPUTE_RESOLUTION = "dispute_resolution"
    GENERAL = "general"


class GovernanceEngine:
    def __init__(self):
        self.proposals: dict = {}
        self.arbiters: dict = {}
        self.parameters: dict = {
            "trust_threshold": 60,
            "dispute_timeout_hours": 72,
            "arbiter_count": 5,
            "voting_period_hours": 48,
            "quorum_percent": 20
        }

    def create_proposal(self, proposer_did: str, title: str, description: str, proposal_type: ProposalType, changes: dict = None, duration_hours: int = None) -> str:
        if duration_hours is None:
            duration_hours = self.parameters["voting_period_hours"]

        prop_data = f"{proposer_did}{title}{datetime.now(timezone.utc).isoformat()}"
        prop_id = hashlib.sha256(prop_data.encode()).hexdigest()[:16]

        self.proposals[prop_id] = {
            "prop_id": prop_id,
            "proposer_did": proposer_did,
            "title": title,
            "description": description,
            "proposal_type": proposal_type,
            "changes": changes or {},
            "status": ProposalStatus.ACTIVE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat(),
            "votes_for": 0,
            "votes_against": 0,
            "voters": {},
            "executed_at": None
        }
        return prop_id

    def vote(self, prop_id: str, voter_did: str, support: bool, voting_power: float = 1.0) -> bool:
        prop = self.proposals.get(prop_id)
        if not prop or prop["status"] != ProposalStatus.ACTIVE:
            return False
        if datetime.now(timezone.utc) > datetime.fromisoformat(prop["expires_at"]):
            prop["status"] = ProposalStatus.EXPIRED
            return False
        if voter_did in prop["voters"]:
            return False

        prop["voters"][voter_did] = {"support": support, "voting_power": voting_power}
        if support:
            prop["votes_for"] += voting_power
        else:
            prop["votes_against"] += voting_power
        return True

    def tally(self, prop_id: str, total_voting_power: float) -> Optional[dict]:
        prop = self.proposals.get(prop_id)
        if not prop:
            return None

        total_votes = prop["votes_for"] + prop["votes_against"]
        participation = (total_votes / total_voting_power) * 100 if total_voting_power > 0 else 0

        if participation < self.parameters["quorum_percent"]:
            return {"passed": False, "reason": "Quorum not met", "participation": participation}

        passed = prop["votes_for"] > prop["votes_against"]
        prop["status"] = ProposalStatus.PASSED if passed else ProposalStatus.REJECTED

        return {
            "passed": passed,
            "votes_for": prop["votes_for"],
            "votes_against": prop["votes_against"],
            "participation": participation,
            "status": prop["status"].value
        }

    def execute(self, prop_id: str) -> bool:
        prop = self.proposals.get(prop_id)
        if not prop or prop["status"] != ProposalStatus.PASSED:
            return False

        if prop["proposal_type"] == ProposalType.PARAMETER_CHANGE:
            for key, value in prop["changes"].items():
                if key in self.parameters:
                    self.parameters[key] = value

        elif prop["proposal_type"] == ProposalType.ARBITER_ELECTION:
            arbiter_did = prop["changes"].get("arbiter_did")
            if arbiter_did:
                self.arbiters[arbiter_did] = {
                    "did": arbiter_did,
                    "elected_at": datetime.now(timezone.utc).isoformat(),
                    "proposal_id": prop_id,
                    "active": True
                }

        prop["status"] = ProposalStatus.EXECUTED
        prop["executed_at"] = datetime.now(timezone.utc).isoformat()
        return True

    def get_proposal(self, prop_id: str) -> Optional[dict]:
        return self.proposals.get(prop_id)

    def get_parameters(self) -> dict:
        return self.parameters

    def get_arbiters(self) -> dict:
        return self.arbiters

    def is_arbiter(self, did: str) -> bool:
        return did in self.arbiters and self.arbiters[did]["active"]
