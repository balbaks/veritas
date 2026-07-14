from fastapi.testclient import TestClient
from api.server import app
from identity.did import DID
from datetime import datetime, timedelta
import time

client = TestClient(app)


def test_reputation_increment_requires_valid_signature():
    # Create a DID
    resp = client.post("/identity/did/create")
    assert resp.status_code == 200
    data = resp.json()
    did = data["did"]
    public_key = data["public_key"]
    private_key_hex = data["private_key"]

    from cryptography.hazmat.primitives.asymmetric import ed25519
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))

    # Valid signed request
    now = datetime.utcnow().isoformat()
    message = f"reputation|amount=10.0&reason=test|{now}"
    signature = private_key.sign(message.encode()).hex()

    resp = client.post(f"/identity/reputation/{did}/increment", json={
        "amount": 10.0,
        "reason": "test",
        "signature": signature,
        "message": message,
        "timestamp": now
    })
    assert resp.status_code == 200

    # Wrong signature
    resp = client.post(f"/identity/reputation/{did}/increment", json={
        "amount": 10.0,
        "reason": "test",
        "signature": "bad",
        "message": "bad",
        "timestamp": now
    })
    assert resp.status_code == 403


def test_replay_attack_blocked():
    # Create DID
    resp = client.post("/identity/did/create")
    data = resp.json()
    did = data["did"]
    private_key_hex = data["private_key"]

    from cryptography.hazmat.primitives.asymmetric import ed25519
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))

    # Sign with a timestamp from 2 minutes ago
    old_time = (datetime.utcnow() - timedelta(seconds=121)).isoformat()
    message = f"reputation|amount=10.0&reason=test|{old_time}"
    signature = private_key.sign(message.encode()).hex()

    resp = client.post(f"/identity/reputation/{did}/increment", json={
        "amount": 10.0,
        "reason": "test",
        "signature": signature,
        "message": message,
        "timestamp": old_time
    })
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"].lower()


def test_dispute_resolution_requires_arbiter():
    # Create DIDs
    buyer = client.post("/identity/did/create").json()
    seller = client.post("/identity/did/create").json()

    from cryptography.hazmat.primitives.asymmetric import ed25519

    # Create transaction
    buyer_pk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(buyer["private_key"]))
    now = datetime.utcnow().isoformat()
    msg = f"economic_transaction|amount=100.0&currency=USDC&description=test|{now}"
    sig = buyer_pk.sign(msg.encode()).hex()

    tx_resp = client.post("/economic/transaction", json={
        "buyer_did": buyer["did"],
        "seller_did": seller["did"],
        "agent_id": "test_agent",
        "amount": 100.0,
        "currency": "USDC",
        "description": "test",
        "signature": sig,
        "message": msg,
        "timestamp": now
    })
    assert tx_resp.status_code == 200
    tx_id = tx_resp.json()["tx_id"]

    # Fund escrow
    now = datetime.utcnow().isoformat()
    msg = f"economic_fund|tx_id={tx_id}|{now}"
    sig = buyer_pk.sign(msg.encode()).hex()
    fund_resp = client.post("/economic/escrow/fund", json={
        "tx_id": tx_id,
        "buyer_did": buyer["did"],
        "signature": sig,
        "message": msg,
        "timestamp": now
    })
    assert fund_resp.status_code == 200
    escrow_id = fund_resp.json()["escrow_id"]

    # Dispute as buyer
    now = datetime.utcnow().isoformat()
    msg = f"economic_dispute|escrow_id={escrow_id}&reason=test|{now}"
    sig = buyer_pk.sign(msg.encode()).hex()
    dispute_resp = client.post(f"/economic/escrow/{escrow_id}/dispute", json={
        "escrow_id": escrow_id,
        "filed_by": buyer["did"],
        "reason": "test",
        "proof_hash": "proof123",
        "signature": sig,
        "message": msg,
        "timestamp": now
    })
    assert dispute_resp.status_code == 200

    # Seller tries to self-resolve — should fail (not an arbiter)
    seller_pk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seller["private_key"]))
    now = datetime.utcnow().isoformat()
    msg = f"economic_resolve|escrow_id={escrow_id}&favor_buyer=False|{now}"
    sig = seller_pk.sign(msg.encode()).hex()
    resolve_resp = client.post(f"/economic/escrow/{escrow_id}/resolve", json={
        "escrow_id": escrow_id,
        "favor_buyer": False,
        "resolved_by": seller["did"],
        "signature": sig,
        "message": msg,
        "timestamp": now
    })
    assert resolve_resp.status_code == 403
