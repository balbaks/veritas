import hashlib
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class EscrowStatus(Enum):
    FUNDED = "funded"
    RELEASED = "released"
    DISPUTED = "disputed"
    RESOLVED_BUYER = "resolved_buyer"
    RESOLVED_SELLER = "resolved_seller"
    REFUNDED = "refunded"


class EconomicEngine:
    def __init__(self):
        self.transactions: dict = {}
        self.escrows: dict = {}

    def create_transaction(self, buyer_did: str, seller_did: str, agent_id: str, amount: float, currency: str, description: str) -> str:
        tx_data = f"{buyer_did}{seller_did}{amount}{currency}{datetime.now(timezone.utc).isoformat()}"
        tx_id = hashlib.sha256(tx_data.encode()).hexdigest()[:16]

        self.transactions[tx_id] = {
            "tx_id": tx_id,
            "buyer_did": buyer_did,
            "seller_did": seller_did,
            "agent_id": agent_id,
            "amount": amount,
            "currency": currency,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "escrow_id": None,
            "proofs": [],
            "dispute": None
        }
        return tx_id

    def fund_escrow(self, tx_id: str) -> str:
        tx = self.transactions.get(tx_id)
        if not tx:
            return None
        if tx["status"] != "pending":
            return None

        escrow_id = hashlib.sha256(f"escrow:{tx_id}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16]
        self.escrows[escrow_id] = {
            "escrow_id": escrow_id,
            "tx_id": tx_id,
            "amount": tx["amount"],
            "currency": tx["currency"],
            "buyer_did": tx["buyer_did"],
            "seller_did": tx["seller_did"],
            "status": EscrowStatus.FUNDED,
            "funded_at": datetime.now(timezone.utc).isoformat(),
            "released_at": None,
            "dispute_at": None,
            "resolution": None
        }
        tx["status"] = "funded"
        tx["escrow_id"] = escrow_id
        return escrow_id

    def release_escrow(self, escrow_id: str) -> bool:
        escrow = self.escrows.get(escrow_id)
        if not escrow or escrow["status"] != EscrowStatus.FUNDED:
            return False
        escrow["status"] = EscrowStatus.RELEASED
        escrow["released_at"] = datetime.now(timezone.utc).isoformat()
        tx = self.transactions.get(escrow["tx_id"])
        if tx:
            tx["status"] = "completed"
        return True

    def file_dispute(self, escrow_id: str, filed_by: str, reason: str, proof_hash: str) -> bool:
        escrow = self.escrows.get(escrow_id)
        if not escrow or escrow["status"] != EscrowStatus.FUNDED:
            return False
        escrow["status"] = EscrowStatus.DISPUTED
        escrow["dispute_at"] = datetime.now(timezone.utc).isoformat()
        tx = self.transactions.get(escrow["tx_id"])
        if tx:
            tx["status"] = "disputed"
            tx["dispute"] = {
                "filed_by": filed_by,
                "reason": reason,
                "proof_hash": proof_hash,
                "filed_at": datetime.now(timezone.utc).isoformat()
            }
        return True

    def resolve_dispute(self, escrow_id: str, favor_buyer: bool, resolved_by: str) -> bool:
        escrow = self.escrows.get(escrow_id)
        if not escrow or escrow["status"] != EscrowStatus.DISPUTED:
            return False
        escrow["status"] = EscrowStatus.RESOLVED_BUYER if favor_buyer else EscrowStatus.RESOLVED_SELLER
        escrow["resolution"] = {
            "favor": "buyer" if favor_buyer else "seller",
            "resolved_by": resolved_by,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }
        tx = self.transactions.get(escrow["tx_id"])
        if tx:
            tx["status"] = "refunded" if favor_buyer else "completed"
        return True

    def get_transaction(self, tx_id: str) -> Optional[dict]:
        return self.transactions.get(tx_id)

    def get_escrow(self, escrow_id: str) -> Optional[dict]:
        return self.escrows.get(escrow_id)
