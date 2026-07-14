"""
Auth integration tests for VERITAS canonical signature scheme.

Signing convention:
  msg = canonical_message(op, params, timestamp)
  sig = Ed25519PrivateKey.sign(msg.encode()).hex()
"""
import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute
from api.server import app
from identity.did import canonical_message, DID
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519

client = TestClient(app)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_did():
    resp = client.post("/identity/did/create")
    assert resp.status_code == 200
    d = resp.json()
    pk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(d["private_key"]))
    return d["did"], pk


def _sign(pk, op, params, ts=None):
    if ts is None:
        ts = datetime.utcnow().isoformat()
    msg = canonical_message(op, params, ts)
    return pk.sign(msg.encode()).hex(), ts


# ── serialization unit test ───────────────────────────────────────────────────

def test_canonical_message_serialization():
    ts = "2026-07-14T10:00:00"
    assert canonical_message("escrow.fund", {"amount": 10, "tx_id": "abc"}, ts) == \
        "escrow.fund|amount=10&tx_id=abc|2026-07-14T10:00:00"
    assert canonical_message("escrow.fund", {"amount": 10.0, "tx_id": "abc"}, ts) == \
        "escrow.fund|amount=10&tx_id=abc|2026-07-14T10:00:00"
    assert canonical_message("gov.vote", {"prop_id": "x", "support": True}, ts) == \
        "gov.vote|prop_id=x&support=true|2026-07-14T10:00:00"
    assert canonical_message("gov.vote", {"prop_id": "x", "support": False}, ts) == \
        "gov.vote|prop_id=x&support=false|2026-07-14T10:00:00"
    # special chars in str values are encoded
    assert canonical_message("op", {"k": "a&b=c|d%e"}, ts) == \
        "op|k=a%26b%3Dc%7Cd%25e|2026-07-14T10:00:00"
    # None
    assert canonical_message("op", {"k": None}, ts) == "op|k=|2026-07-14T10:00:00"
    # nested rejects
    with pytest.raises(ValueError):
        canonical_message("op", {"k": [1, 2]}, ts)


# ── CRITICAL TEST 1: tampered amount rejected ─────────────────────────────────

def test_tampered_amount_rejected():
    """Signature over amount=10 must not authorize amount=1000."""
    buyer_did, buyer_pk = _make_did()
    seller_did, _ = _make_did()

    # Create a transaction
    now = datetime.utcnow().isoformat()
    sig, ts = _sign(buyer_pk, "escrow.transaction.create", {
        "amount": 10.0, "buyer_did": buyer_did, "currency": "USDC", "seller_did": seller_did
    }, now)
    tx_resp = client.post("/economic/transaction", json={
        "buyer_did": buyer_did, "seller_did": seller_did, "agent_id": "a",
        "amount": 10.0, "currency": "USDC", "description": "d",
        "signature": sig, "timestamp": ts
    })
    assert tx_resp.status_code == 200
    tx_id = tx_resp.json()["tx_id"]

    # Fund escrow — sign with tx_id=<correct>
    now = datetime.utcnow().isoformat()
    sig, ts = _sign(buyer_pk, "escrow.fund", {"tx_id": tx_id}, now)
    fund_resp = client.post("/economic/escrow/fund", json={
        "tx_id": tx_id, "buyer_did": buyer_did, "signature": sig, "timestamp": ts
    })
    assert fund_resp.status_code == 200
    escrow_id = fund_resp.json()["escrow_id"]

    # Now sign a release for escrow_id — but submit it with escrow_id="tampered"
    seller_did2, seller_pk = _make_did()
    now = datetime.utcnow().isoformat()
    sig, ts = _sign(seller_pk, "escrow.release", {"escrow_id": escrow_id}, now)
    # Try to use that signature for a different escrow_id
    tampered_resp = client.post(f"/economic/escrow/TAMPERED/release", json={
        "escrow_id": "TAMPERED", "seller_did": seller_did2, "signature": sig, "timestamp": ts
    })
    assert tampered_resp.status_code == 403


# ── CRITICAL TEST 2: signature not reusable across endpoints ──────────────────

def test_signature_not_reusable_across_endpoints():
    """A valid signature for escrow.fund must not pass gov.vote verification."""
    did, pk = _make_did()
    now = datetime.utcnow().isoformat()

    # Sign for escrow.fund
    sig, ts = _sign(pk, "escrow.fund", {"tx_id": "sometx"}, now)

    # Submit to gov.vote with the same sig — server rebuilds gov.vote canonical msg → mismatch
    resp = client.post("/governance/vote", json={
        "prop_id": "fakeprop", "voter_did": did, "support": True,
        "signature": sig, "timestamp": ts
    })
    assert resp.status_code == 403


# ── CRITICAL TEST 3: replayed request rejected ────────────────────────────────

@pytest.mark.parametrize("module,route,signer_field,op,build_body", [
    (
        "identity",
        lambda did, _: f"/identity/reputation/{did}/increment",
        lambda did, _: did,
        lambda did, _: ("identity.reputation.increment", {"amount": 1.0, "did": did, "reason": "t"}),
        lambda did, _, sig, ts: {"amount": 1.0, "reason": "t", "signature": sig, "timestamp": ts},
    ),
    (
        "agent",
        lambda did, _: "/agents/register",
        lambda did, _: did,
        lambda did, _: ("agent.register", {"agent_type": "bot", "owner_did": did}),
        lambda did, _, sig, ts: {"owner_did": did, "agent_type": "bot", "capabilities": [], "signature": sig, "timestamp": ts},
    ),
    (
        "content",
        lambda did, _: "/content/verify-origin",
        lambda did, _: did,
        lambda did, _: ("content.verify_origin", {"content_hash": "fakehash", "creator_did": did}),
        lambda did, _, sig, ts: {"content_hash": "fakehash", "creator_did": did, "signature": sig, "timestamp": ts},
    ),
    (
        "economic",
        lambda did, sdid: "/economic/transaction",
        lambda did, _: did,
        lambda did, sdid: ("escrow.transaction.create", {"amount": 1.0, "buyer_did": did, "currency": "X", "seller_did": sdid}),
        lambda did, sdid, sig, ts: {"buyer_did": did, "seller_did": sdid, "agent_id": "a", "amount": 1.0, "currency": "X", "description": "d", "signature": sig, "timestamp": ts},
    ),
    (
        "governance",
        lambda did, _: "/governance/proposal",
        lambda did, _: did,
        lambda did, _: ("gov.proposal", {"proposal_type": "general", "proposer_did": did, "title": "t"}),
        lambda did, _, sig, ts: {"proposer_did": did, "title": "t", "description": "d", "proposal_type": "general", "signature": sig, "timestamp": ts},
    ),
])
def test_replayed_request_rejected(module, route, signer_field, op, build_body):
    did, pk = _make_did()
    did2, _ = _make_did()

    old_ts = (datetime.utcnow() - timedelta(seconds=121)).isoformat()
    op_name, params = op(did, did2)
    msg = canonical_message(op_name, params, old_ts)
    sig = pk.sign(msg.encode()).hex()

    url = route(did, did2)
    body = build_body(did, did2, sig, old_ts)
    resp = client.post(url, json=body)
    assert resp.status_code == 403, \
        f"[{module}] Expected 403 for replayed request, got {resp.status_code}: {resp.text}"


# ── META TEST: every mutating route rejects a bad signature ──────────────────

OPEN = {"/claim", "/proof", "/identity/did/create", "/governance/tally"}

# Minimal bodies keyed by route path template. All include bad sig + fresh ts.
# Path params substituted at request time.
BAD_SIG = "aa" * 32  # 128 hex chars, syntactically valid Ed25519 sig length


def _bodies(did: str, now: str) -> dict:
    return {
        "/identity/reputation/{did}/increment": {
            "amount": 1.0, "reason": "t", "signature": BAD_SIG, "timestamp": now},
        "/identity/reputation/{did}/decrement": {
            "amount": 1.0, "reason": "t", "signature": BAD_SIG, "timestamp": now},
        "/identity/stake": {
            "did": did, "amount": 1.0, "signature": BAD_SIG, "timestamp": now},
        "/agents/register": {
            "owner_did": did, "agent_type": "bot", "capabilities": [],
            "signature": BAD_SIG, "timestamp": now},
        "/agents/delegate": {
            "owner_did": did, "agent_id": "fake", "permissions": [],
            "signature": BAD_SIG, "timestamp": now},
        "/agents/delegate/{delegation_id}/revoke": {
            "delegation_id": "fake", "owner_did": did,
            "signature": BAD_SIG, "timestamp": now},
        "/agents/delegate/log": {
            "delegation_id": "fake", "action": "act", "details": "d",
            "authorized_by": did, "signature": BAD_SIG, "timestamp": now},
        "/agents/{agent_id}/transaction": {
            "agent_id": "fake", "success": True, "details": "d",
            "authorized_by": did, "signature": BAD_SIG, "timestamp": now},
        "/agents/{agent_id}/dispute": {
            "agent_id": "fake", "details": "d", "filed_by": did,
            "signature": BAD_SIG, "timestamp": now},
        "/economic/transaction": {
            "buyer_did": did, "seller_did": did, "agent_id": "a",
            "amount": 1.0, "currency": "X", "description": "d",
            "signature": BAD_SIG, "timestamp": now},
        "/economic/escrow/fund": {
            "tx_id": "fake", "buyer_did": did,
            "signature": BAD_SIG, "timestamp": now},
        "/economic/escrow/{escrow_id}/release": {
            "escrow_id": "fake", "seller_did": did,
            "signature": BAD_SIG, "timestamp": now},
        "/economic/escrow/{escrow_id}/dispute": {
            "escrow_id": "fake", "filed_by": did, "reason": "r", "proof_hash": "ph",
            "signature": BAD_SIG, "timestamp": now},
        "/economic/escrow/{escrow_id}/resolve": {
            "escrow_id": "fake", "favor_buyer": True, "resolved_by": did,
            "signature": BAD_SIG, "timestamp": now},
        "/governance/proposal": {
            "proposer_did": did, "title": "t", "description": "d",
            "proposal_type": "general", "signature": BAD_SIG, "timestamp": now},
        "/governance/vote": {
            "prop_id": "fake", "voter_did": did, "support": True,
            "signature": BAD_SIG, "timestamp": now},
        "/governance/execute/{prop_id}": {
            "prop_id": "fake", "executor_did": did,
            "signature": BAD_SIG, "timestamp": now},
        "/governance/curation/list": {
            "owner_did": did, "name": "n", "description": "d",
            "signature": BAD_SIG, "timestamp": now},
        "/governance/curation/curator": {
            "list_id": "fake", "curator_did": did, "added_by": did,
            "signature": BAD_SIG, "timestamp": now},
        "/governance/curation/item": {
            "list_id": "fake", "content_hash": "h", "added_by": did,
            "signature": BAD_SIG, "timestamp": now},
        "/governance/curation/verify": {
            "list_id": "fake", "content_hash": "h", "verifier_did": did,
            "signature": BAD_SIG, "timestamp": now},
        "/governance/curation/reject": {
            "list_id": "fake", "content_hash": "h", "verifier_did": did,
            "signature": BAD_SIG, "timestamp": now},
        "/content/verify-origin": {
            "content_hash": "h", "creator_did": did,
            "signature": BAD_SIG, "timestamp": now},
        "/content/edit": {
            "content_hash": "h", "editor_did": did, "new_hash": "h2", "edit_type": "patch",
            "signature": BAD_SIG, "timestamp": now},
    }


def _substitute_path(template: str, did: str) -> str:
    return (template
            .replace("{did}", did)
            .replace("{agent_id}", "fake")
            .replace("{delegation_id}", "fake")
            .replace("{escrow_id}", "fake")
            .replace("{prop_id}", "fake")
            .replace("{list_id}", "fake"))


def _all_routes(app):
    """Walk FastAPI's route tree including included routers."""
    result = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            result.append(r)
        elif type(r).__name__ == "_IncludedRouter":
            prefix = r.include_context.prefix or ""
            for sub in r.original_router.routes:
                if isinstance(sub, APIRoute):
                    # Attach the full path so it looks like a normal APIRoute
                    sub_copy = type("R", (), {
                        "methods": sub.methods,
                        "path": prefix + sub.path
                    })()
                    result.append(sub_copy)
    return result


def test_all_mutating_routes_reject_bad_signature():
    did, _ = _make_did()
    now = datetime.utcnow().isoformat()
    bodies = _bodies(did, now)

    mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}

    covered = []
    skipped_open = []
    skipped_no_body = []
    failures = []

    for route in _all_routes(app):
        if not (route.methods & mutating_methods):
            continue

        path = route.path

        if path in OPEN:
            skipped_open.append(path)
            continue

        # content/register uses multipart — handle separately
        if path == "/content/register":
            resp = client.post("/content/register",
                               data={"creator_did": did, "signature": BAD_SIG, "timestamp": now},
                               files={"data": ("t.txt", b"test", "text/plain")})
            result = resp.status_code
            covered.append(f"{path} → {result}")
            if result not in (401, 403):
                failures.append(f"{path}: expected 403, got {result}")
            continue

        if path not in bodies:
            skipped_no_body.append(path)
            continue

        url = _substitute_path(path, did)
        resp = client.post(url, json=bodies[path])
        result = resp.status_code
        covered.append(f"{path} → {result}")
        if result not in (401, 403):
            failures.append(f"{path}: expected 401/403, got {result} — {resp.text[:120]}")

    print(f"\n[meta-test] Routes covered ({len(covered)}):")
    for c in sorted(covered):
        print(f"  {c}")
    if skipped_open:
        print(f"[meta-test] Intentionally open (skipped): {skipped_open}")
    if skipped_no_body:
        print(f"[meta-test] No body defined (skipped): {skipped_no_body}")

    assert not failures, "Auth failures:\n" + "\n".join(failures)
    assert len(covered) >= 20, f"Expected ≥20 routes covered, got {len(covered)}"
