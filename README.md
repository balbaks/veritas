![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-yellow)
![Status](https://img.shields.io/badge/status-active-success)
![Docker](https://img.shields.io/badge/docker-ready-blue)

# VERITAS v1.2.0

A protocol for verifiable provenance, identity, and attestation — backed by Ed25519 cryptography, not platform authority.

▶️ Demo: https://asciinema.org/a/5iq9X2ggmaVJNWDH

## Running

docker build -t veritas-node .
docker run -d -p 8000:8000 veritas-node

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn api.server:app --reload --port 8000

Interactive docs: http://localhost:8000/docs

## Auth Model

All mutating endpoints (25 routes) use canonical payload binding. The server reconstructs the signed message from actual request parameters — no caller-supplied message string is accepted. A mismatched payload returns 403.

### How to sign a request

from cryptography.hazmat.primitives.asymmetric import ed25519
from datetime import datetime, timezone

def _encode_str(s: str) -> str:
    return s.replace('%', '%25').replace('&', '%26').replace('=', '%3D').replace('|', '%7C')

def canonical_message(op: str, params: dict, timestamp: str) -> str:
    op        — stable dot-separated identifier, e.g. "escrow.fund"
    params    — flat dict of the exact values the server will act on
    timestamp — ISO-8601 UTC string
    Format: op|k1=v1&k2=v2|timestamp  (keys sorted lexicographically)
    def _serialize(v):
        if isinstance(v, (dict, list)):
            raise ValueError(f"Nested types not allowed: {v!r}")
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return f"{float(v):.8f}".rstrip("0").rstrip(".")
        if v is None:
            return ""
        return _encode_str(str(v))
    pairs = "&".join(f"{k}={_serialize(params[k])}" for k in sorted(params.keys()))
    return f"{op}|{pairs}|{timestamp}"

def sign_request(private_key_hex: str, op: str, params: dict) -> tuple[str, str]:
    """Returns (signature_hex, timestamp_iso)."""
    ts = datetime.now(timezone.utc).isoformat()
    pk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    sig = pk.sign(canonical_message(op, params, ts).encode()).hex()
    return sig, ts

### Example: fund an escrow

import requests

BASE = "http://localhost:8000"

r = requests.post(f"{BASE}/identity/did/create").json()
did = r["did"]
private_key_hex = r["private_key"]

sig, ts = sign_request(private_key_hex, "escrow.fund", {"tx_id": "abc123"})

resp = requests.post(f"{BASE}/economic/escrow/fund", json={
    "tx_id": "abc123",
    "buyer_did": did,
    "signature": sig,
    "timestamp": ts,
})

Replay protection: Timestamps outside a 60-second window are rejected with 403. Generate a fresh timestamp per request.

### Intentionally open routes (no signature required)

| Route | Why |
|-------|-----|
| POST /claim | Open attestation — anyone can submit a claim without identity |
| POST /proof | Open attestation — anyone can submit a proof |
| POST /identity/did/create | Identity bootstrapping — you need a DID before you can sign anything |
| POST /governance/tally | Read-only computation — tallying votes is a public operation |

All other POST/PUT/PATCH/DELETE routes require a valid canonical signature.

## Op IDs and params

See docs/SPEC.md section 13.1 for the complete table of op IDs and the exact param dicts each endpoint signs over.

## Tech Stack

- Python 3.12
- FastAPI + aiosqlite (SQLite)
- Ed25519 (cryptography library)
- Docker

## Tests

pytest tests/ -v

## License

MIT
