from core.models import Claim, Proof, TrustVerdict, TrustScore
from typing import List
import hashlib


class TrustEngine:
    def __init__(self):
        self.claims: dict = {}
        self.proofs: dict = {}

    def hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def submit_claim(self, subject: str, predicate: str, content: str) -> Claim:
        content_hash = self.hash_content(content)
        claim_id = hashlib.sha256(f"{subject}{predicate}{content_hash}".encode()).hexdigest()
        claim = Claim(id=claim_id, subject=subject, predicate=predicate, content_hash=content_hash)
        self.claims[claim_id] = claim
        return claim

    def submit_proof(self, claim_id: str, proof_type: str, proof_data: str, verifier: str) -> Proof:
        proof = Proof(claim_id=claim_id, proof_type=proof_type, proof_data=proof_data, verifier=verifier)
        if claim_id not in self.proofs:
            self.proofs[claim_id] = []
        self.proofs[claim_id].append(proof)
        return proof

    def _validate_proof(self, claim: Claim, proof: Proof) -> bool:
        if proof.proof_type == "hash_match":
            return proof.proof_data == claim.content_hash
        elif proof.proof_type == "signature":
            return len(proof.proof_data) >= 64 and proof.verifier != ""
        elif proof.proof_type == "attestation":
            return len(proof.proof_data) >= 16 and proof.verifier != ""
        elif proof.proof_type == "zk_proof":
            return proof.proof_data.startswith("zk:") and len(proof.proof_data) > 16
        return False

    def evaluate(self, claim_id: str) -> TrustVerdict:
        claim = self.claims.get(claim_id)
        if not claim:
            return TrustVerdict(
                claim_id=claim_id,
                score=TrustScore.UNVERIFIED,
                confidence=0.0,
                proof_count=0,
                source_count=0,
                explanation="Claim not found in registry."
            )

        proofs = self.proofs.get(claim_id, [])
        valid_proofs = [p for p in proofs if self._validate_proof(claim, p)]
        invalid_count = len(proofs) - len(valid_proofs)
        verifiers = set(p.verifier for p in valid_proofs)
        proof_count = len(valid_proofs)
        source_count = len(verifiers)

        if invalid_count > 0 and proof_count == 0:
            return TrustVerdict(
                claim_id=claim_id,
                score=TrustScore.CONTRADICTED,
                confidence=0.1,
                proof_count=0,
                source_count=0,
                explanation=f"All {invalid_count} proofs failed validation."
            )

        if proof_count == 0:
            return TrustVerdict(
                claim_id=claim_id,
                score=TrustScore.UNVERIFIED,
                confidence=0.0,
                proof_count=0,
                source_count=0,
                explanation="No valid proofs submitted for this claim."
            )

        if proof_count >= 3 and source_count >= 2:
            score = TrustScore.WELL_ATTESTED
            confidence = 0.95
        elif proof_count >= 2:
            score = TrustScore.LIKELY_AUTHENTIC
            confidence = 0.75
        elif proof_count == 1:
            score = TrustScore.UNVERIFIED
            confidence = 0.4
        else:
            score = TrustScore.POORLY_ATTESTED
            confidence = 0.2

        explanation = f"Evidence based on {proof_count} valid attestations from {source_count} independent sources."
        if invalid_count > 0:
            explanation += f" ({invalid_count} invalid proofs rejected.)"

        return TrustVerdict(
            claim_id=claim_id,
            score=score,
            confidence=confidence,
            proof_count=proof_count,
            source_count=source_count,
            explanation=explanation
        )
