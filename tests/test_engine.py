from core.engine import TrustEngine
from core.models import TrustScore


def test_submit_claim():
    engine = TrustEngine()
    claim = engine.submit_claim("user1", "says", "hello world")
    assert claim.subject == "user1"
    assert claim.predicate == "says"
    assert claim.content_hash is not None


def test_no_proofs_returns_unverified():
    engine = TrustEngine()
    claim = engine.submit_claim("user1", "says", "hello")
    verdict = engine.evaluate(claim.id)
    assert verdict.score == TrustScore.UNVERIFIED
    assert verdict.confidence == 0.0


def test_valid_proofs_return_well_attested():
    engine = TrustEngine()
    claim = engine.submit_claim("user1", "says", "hello")
    engine.submit_proof(claim.id, "hash_match", claim.content_hash, "verifierA")
    engine.submit_proof(claim.id, "attestation", "a" * 16, "verifierB")
    engine.submit_proof(claim.id, "signature", "a" * 64, "verifierC")
    verdict = engine.evaluate(claim.id)
    assert verdict.score == TrustScore.WELL_ATTESTED
    assert verdict.confidence == 0.95


def test_invalid_proof_returns_contradicted():
    engine = TrustEngine()
    claim = engine.submit_claim("user1", "says", "hello")
    engine.submit_proof(claim.id, "hash_match", "wrong_hash", "verifierA")
    verdict = engine.evaluate(claim.id)
    assert verdict.score == TrustScore.CONTRADICTED
