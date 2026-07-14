from fastapi.testclient import TestClient
from api.server import app
from identity.did import DID
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519

client = TestClient(app)


def _make_did():
    resp = client.post("/identity/did/create")
    assert resp.status_code == 200
    data = resp.json()
    pk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(data["private_key"]))
    return data["did"], pk


def _sign(pk, endpoint, params, timestamp):
    msg = DID.build_message(endpoint, params, timestamp)
    return msg, pk.sign(msg.encode()).hex()


def test_reputation_increment_requires_valid_signature():
    did, pk = _make_did()
    now = datetime.utcnow().isoformat()
    msg, sig = _sign(pk, "reputation_increment", {"amount": "10.0", "did": did, "reason": "test"}, now)

    resp = client.post(f"/identity/reputation/{did}/increment", json={
        "amount": 10.0, "reason": "test", "signature": sig, "timestamp": now
    })
    assert resp.status_code == 200

    resp = client.post(f"/identity/reputation/{did}/increment", json={
        "amount": 10.0, "reason": "test", "signature": "bad", "timestamp": now
    })
    assert resp.status_code == 403


def test_replay_attack_blocked():
    did, pk = _make_did()
    old_time = (datetime.utcnow() - timedelta(seconds=121)).isoformat()
    msg, sig = _sign(pk, "reputation_increment", {"amount": "10.0", "did": did, "reason": "test"}, old_time)

    resp = client.post(f"/identity/reputation/{did}/increment", json={
        "amount": 10.0, "reason": "test", "signature": sig, "timestamp": old_time
    })
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"].lower()


def test_payload_binding_enforced():
    did, pk = _make_did()
    now = datetime.utcnow().isoformat()
    # Sign a message authorizing amount=10.0
    msg, sig = _sign(pk, "reputation_increment", {"amount": "10.0", "did": did, "reason": "test"}, now)

    # Send amount=9999.0 — server rebuilds message with actual amount, signature mismatch
    resp = client.post(f"/identity/reputation/{did}/increment", json={
        "amount": 9999.0, "reason": "test", "signature": sig, "timestamp": now
    })
    assert resp.status_code == 403


def test_replay_blocked_on_economic_routes():
    buyer_did, buyer_pk = _make_did()
    seller_did, _ = _make_did()

    old_time = (datetime.utcnow() - timedelta(seconds=121)).isoformat()
    msg, sig = _sign(buyer_pk, "economic_transaction", {
        "amount": "100.0", "buyer_did": buyer_did, "currency": "USDC", "seller_did": seller_did
    }, old_time)

    resp = client.post("/economic/transaction", json={
        "buyer_did": buyer_did, "seller_did": seller_did, "agent_id": "test",
        "amount": 100.0, "currency": "USDC", "description": "test",
        "signature": sig, "timestamp": old_time
    })
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"].lower()


def test_dispute_resolution_requires_arbiter():
    buyer_did, buyer_pk = _make_did()
    seller_did, seller_pk = _make_did()

    # Create transaction
    now = datetime.utcnow().isoformat()
    msg, sig = _sign(buyer_pk, "economic_transaction", {
        "amount": "100.0", "buyer_did": buyer_did, "currency": "USDC", "seller_did": seller_did
    }, now)
    tx_resp = client.post("/economic/transaction", json={
        "buyer_did": buyer_did, "seller_did": seller_did, "agent_id": "test",
        "amount": 100.0, "currency": "USDC", "description": "test",
        "signature": sig, "timestamp": now
    })
    assert tx_resp.status_code == 200
    tx_id = tx_resp.json()["tx_id"]

    # Fund escrow
    now = datetime.utcnow().isoformat()
    msg, sig = _sign(buyer_pk, "economic_fund", {"buyer_did": buyer_did, "tx_id": tx_id}, now)
    fund_resp = client.post("/economic/escrow/fund", json={
        "tx_id": tx_id, "buyer_did": buyer_did, "signature": sig, "timestamp": now
    })
    assert fund_resp.status_code == 200
    escrow_id = fund_resp.json()["escrow_id"]

    # Dispute as buyer
    now = datetime.utcnow().isoformat()
    msg, sig = _sign(buyer_pk, "economic_dispute", {
        "escrow_id": escrow_id, "filed_by": buyer_did, "reason": "test"
    }, now)
    dispute_resp = client.post(f"/economic/escrow/{escrow_id}/dispute", json={
        "escrow_id": escrow_id, "filed_by": buyer_did, "reason": "test",
        "proof_hash": "proof123", "signature": sig, "timestamp": now
    })
    assert dispute_resp.status_code == 200

    # Seller tries to self-resolve — should fail (not an arbiter)
    now = datetime.utcnow().isoformat()
    msg, sig = _sign(seller_pk, "economic_resolve", {
        "escrow_id": escrow_id, "favor_buyer": "False", "resolved_by": seller_did
    }, now)
    resolve_resp = client.post(f"/economic/escrow/{escrow_id}/resolve", json={
        "escrow_id": escrow_id, "favor_buyer": False,
        "resolved_by": seller_did, "signature": sig, "timestamp": now
    })
    assert resolve_resp.status_code == 403
