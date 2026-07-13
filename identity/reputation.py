from datetime import datetime, timedelta
from typing import Optional, Callable


class ReputationRegistry:
    def __init__(self):
        self.scores: dict = {}
        self.history: dict = {}
        self.stakes: dict = {}

    def new_identity(self, did: str):
        if did not in self.scores:
            self.scores[did] = 50.0
            self.history[did] = []

    def increment(self, did: str, amount: float, reason: str):
        self.new_identity(did)
        self.scores[did] = min(100, self.scores[did] + amount)
        self.history[did].append({
            "action": "increment",
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

    def decrement(self, did: str, amount: float, reason: str):
        self.new_identity(did)
        self.scores[did] = max(0, self.scores[did] - amount)
        self.history[did].append({
            "action": "decrement",
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_score(self, did: str) -> Optional[float]:
        return self.scores.get(did)

    def get_history(self, did: str) -> list:
        return self.history.get(did, [])

    def get_standing(self, did: str) -> str:
        score = self.get_score(did)
        if score is None:
            return "UNKNOWN"
        if score >= 80:
            return "TRUSTED"
        elif score >= 60:
            return "GOOD"
        elif score >= 40:
            return "NEUTRAL"
        elif score >= 20:
            return "LOW"
        else:
            return "UNTRUSTWORTHY"

    def stake(self, did: str, amount: float) -> bool:
        if amount <= 0:
            return False
        self.stakes[did] = self.stakes.get(did, 0) + amount
        self.increment(did, min(amount / 10, 20), "reputation_stake")
        return True

    def get_voting_power(self, did: str) -> float:
        base_score = self.get_score(did) or 50.0
        stake = self.stakes.get(did, 0)
        return (base_score / 50.0) * (1 + (stake ** 0.5) / 10)

    def slash_stake(self, did: str, amount: float, authorized_by: str, arbiter_check: Callable) -> bool:
        if not arbiter_check(authorized_by):
            return False
        if did not in self.stakes or self.stakes[did] < amount:
            return False
        self.stakes[did] -= amount
        self.decrement(did, amount / 5, f"stake_slashed_by_{authorized_by}")
        return True
