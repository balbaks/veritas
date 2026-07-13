from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime
import hashlib
import json


class TrustScore(Enum):
    WELL_ATTESTED = 100
    LIKELY_AUTHENTIC = 75
    UNVERIFIED = 50
    POORLY_ATTESTED = 25
    CONTRADICTED = 0


@dataclass
class Claim:
    id: str
    subject: str
    predicate: str
    content_hash: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Proof:
    claim_id: str
    proof_type: str
    proof_data: str
    verifier: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TrustVerdict:
    claim_id: str
    score: TrustScore
    confidence: float
    proof_count: int
    source_count: int
    explanation: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
