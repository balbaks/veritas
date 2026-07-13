from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime
import hashlib
import json


class TrustScore(Enum):
    VERIFIED = 100
    LIKELY_TRUE = 75
    UNVERIFIED = 50
    SUSPICIOUS = 25
    DISPROVEN = 0


@dataclass
class Claim:
    id: str
    subject: str        # Who or what this claim is about
    predicate: str      # What is being claimed
    content_hash: str   # Hash of the actual content
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Proof:
    claim_id: str
    proof_type: str     # "signature", "hash_match", "zk_proof", "attestation"
    proof_data: str     # The actual proof payload
    verifier: str       # Who or what verified it
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TrustVerdict:
    claim_id: str
    score: TrustScore
    confidence: float   # 0.0 to 1.0
    proof_count: int
    source_count: int
    explanation: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
