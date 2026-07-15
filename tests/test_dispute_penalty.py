"""
Regression tests for the escrow-resolve → agent trust_score penalty path.

Unit tests (direct registry calls):
  Old behavior (record_transaction False): (0 success / 1 total) * 100 = 0 — instant zeroing.
  New behavior (file_dispute): flat -10, clamped at 0.

Integration tests (HTTP round-trips):
  Conditional penalty: penalty applies only when the agent's owning party lost the dispute.
  Agent owned by buyer: favor_buyer=False → buyer loses → -10; favor_buyer=True → no penalty.
"""
from agents.registry import AgentRegistry
from fastapi.testclient import TestClient
from api.server import app
from identity.did import canonical_message
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import ed25519

client = TestClient(app)


# ── unit test helpers ─────────────────────────────────────────────────────────

def _make_agent(registry: AgentRegistry) -> str:
    return registry.register("did:veritas:test", "test_agent", [])


# ── unit tests ────────────────────────────────────────────────────────────────

def test_dispute_penalty_is_graduated():
    reg = AgentRegistry()
    agent_id = _make_agent(reg)
    assert reg.get(agent_id)["trust_score"] == 50.0

    reg.file_dispute(agent_id, "dispute_lost_resolved_by_arbiter", "arbiter")
    assert reg.get(agent_id)["trust_score"] == 40.0, \
        f"Expected 40.0 after one dispute, got {reg.get(agent_id)['trust_score']}"

    reg.file_dispute(agent_id, "dispute_lost_resolved_by_arbiter", "arbiter")
    assert reg.get(agent_id)["trust_score"] == 30.0, \
        f"Expected 30.0 after two disputes, got {reg.get(agent_id)['trust_score']}"


def test_dispute_penalty_floors_at_zero():
    reg = AgentRegistry()
    agent_id = _make_agent(reg)
    assert reg.get(agent_id)["trust_score"] == 50.0

    # 5 disputes × -10 = -50 from baseline of 50 → floor at 0
    for _ in range(5):
        reg.file_dispute(agent_id, "dispute_lost", "arbiter")

    assert reg.get(agent_id)["trust_score"] == 0.0, \
        f"Expected 0.0 after 5 disputes, got {reg.get(agent_id)['trust_score']}"

    # Additional disputes must not go negative
    reg.file_dispute(agent_id, "one_more", "arbiter")
    score = reg.get(agent_id)["trust_score"]
    assert score == 0.0, f"Expected floor at 0.0, got {score}"
    assert score >= 0, f"Trust score went negative: {score}"


# ── integration test helpers ──────────────────────────────────────────────────

def _make_did():
    resp = client.post("/identity/did/create")
    assert resp.status_code == 200
    d = resp.json()
    pk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(d["private_key"]))
    return d["did"], pk


def _sign(pk, op, params):
    ts = datetime.now(timezone.utc).isoformat()
    msg = canonical_message(op, params, ts)
    return pk.sign(msg.encode()).hex(), ts


def _elect(arbiter_did):
    """Inject arbiter directly — skips proposal/vote/tally cycle for test isolation."""
    from api.governance_routes import gov_engine
    gov_engine.arbiters[arbiter_did] = {
        "did": arbiter_did,
        "elected_at": datetime.now(timezone.utc).isoformat(),
        "proposal_id": "test-inject",
        "active": True
    }


def _register_agent(buyer_did, buyer_pk):
    sig, ts = _sign(buyer_pk, "agent.register", {
        "agent_type": "purchasing_agent", "owner_did": buyer_did
    })
    r = client.post("/agents/register", json={
        "owner_did": buyer_did, "agent_type": "purchasing_agent",
        "capabilities": [], "signature": sig, "timestamp": ts
    })
    assert r.status_code == 200, f"register_agent failed: {r.text}"
    return r.json()["agent_id"]


def _run_dispute_cycle(buyer_did, buyer_pk, seller_did, agent_id,
                       arbiter_did, arbiter_pk, favor_buyer):
    """Full escrow cycle: create TX → fund → dispute → resolve."""
    sig, ts = _sign(buyer_pk, "escrow.transaction.create", {
        "amount": 100.0, "buyer_did": buyer_did, "currency": "credits",
        "seller_did": seller_did
    })
    r = client.post("/economic/transaction", json={
        "buyer_did": buyer_did, "seller_did": seller_did, "agent_id": agent_id,
        "amount": 100.0, "currency": "credits", "description": "integration test",
        "signature": sig, "timestamp": ts
    })
    assert r.status_code == 200, f"create_transaction failed: {r.text}"
    tx_id = r.json()["tx_id"]

    sig, ts = _sign(buyer_pk, "escrow.fund", {"tx_id": tx_id})
    r = client.post("/economic/escrow/fund", json={
        "tx_id": tx_id, "buyer_did": buyer_did, "signature": sig, "timestamp": ts
    })
    assert r.status_code == 200, f"fund_escrow failed: {r.text}"
    escrow_id = r.json()["escrow_id"]

    sig, ts = _sign(buyer_pk, "escrow.dispute", {
        "escrow_id": escrow_id, "reason": "cap exceeded"
    })
    r = client.post(f"/economic/escrow/{escrow_id}/dispute", json={
        "escrow_id": escrow_id, "filed_by": buyer_did, "reason": "cap exceeded",
        "proof_hash": "test-hash", "signature": sig, "timestamp": ts
    })
    assert r.status_code == 200, f"file_dispute failed: {r.text}"

    sig, ts = _sign(arbiter_pk, "escrow.resolve", {
        "escrow_id": escrow_id, "favor_buyer": favor_buyer
    })
    r = client.post(f"/economic/escrow/{escrow_id}/resolve", json={
        "escrow_id": escrow_id, "favor_buyer": favor_buyer,
        "resolved_by": arbiter_did, "signature": sig, "timestamp": ts
    })
    assert r.status_code == 200, f"resolve_dispute failed: {r.text}"


# ── integration tests ─────────────────────────────────────────────────────────

def test_penalty_applies_when_agent_loses():
    """Agent owned by buyer: favor_buyer=False → buyer loses → agent loses → 50→40."""
    buyer_did, buyer_pk = _make_did()
    seller_did, _ = _make_did()
    arbiter_did, arbiter_pk = _make_did()

    agent_id = _register_agent(buyer_did, buyer_pk)
    assert client.get(f"/agents/{agent_id}").json()["trust_score"] == 50.0

    _elect(arbiter_did)
    _run_dispute_cycle(buyer_did, buyer_pk, seller_did, agent_id,
                       arbiter_did, arbiter_pk, favor_buyer=False)

    score = client.get(f"/agents/{agent_id}").json()["trust_score"]
    assert score == 40.0, f"Expected 40.0 (buyer's agent lost), got {score}"


def test_no_penalty_when_agent_wins():
    """Agent owned by buyer: favor_buyer=True → buyer wins → agent wins → score stays 50."""
    buyer_did, buyer_pk = _make_did()
    seller_did, _ = _make_did()
    arbiter_did, arbiter_pk = _make_did()

    agent_id = _register_agent(buyer_did, buyer_pk)
    assert client.get(f"/agents/{agent_id}").json()["trust_score"] == 50.0

    _elect(arbiter_did)
    _run_dispute_cycle(buyer_did, buyer_pk, seller_did, agent_id,
                       arbiter_did, arbiter_pk, favor_buyer=True)

    score = client.get(f"/agents/{agent_id}").json()["trust_score"]
    assert score == 50.0, f"Expected 50.0 (buyer's agent won — no penalty), got {score}"


def test_repeated_won_disputes_no_accumulation():
    """3 consecutive wins for buyer's agent → trust_score stays 50.0 throughout."""
    buyer_did, buyer_pk = _make_did()
    seller_did, _ = _make_did()
    arbiter_did, arbiter_pk = _make_did()

    agent_id = _register_agent(buyer_did, buyer_pk)
    _elect(arbiter_did)

    for i in range(3):
        _run_dispute_cycle(buyer_did, buyer_pk, seller_did, agent_id,
                           arbiter_did, arbiter_pk, favor_buyer=True)
        score = client.get(f"/agents/{agent_id}").json()["trust_score"]
        assert score == 50.0, f"Expected 50.0 after win {i + 1}, got {score}"
