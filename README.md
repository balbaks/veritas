# VERITAS v1.2.0

A protocol for verifiable provenance, identity, and attestation — backed by Ed25519 cryptography, not platform authority.

## Running

```bash
# Docker
docker build -t veritas-node .
docker run -d -p 8000:8000 veritas-node

# Local
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn api.server:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Auth Model

All mutating endpoints (25 routes) use **canonical payload binding**. The server reconstructs the signed message from actual request parameters — no caller-supplied message string is accepted. A mismatched payload returns 403.

### How to sign a request

```python
from cryptography.hazmat.primitives.asymmetric import ed25519
from datetime import datetime, timezone

def _encode_str(s: str) -> str:
    # Encode % first, then & = |, to avoid double-encoding.
    return s.replace('%', '%25').replace('&', '%26').replace('=', '%3D').replace('|', '%7C')

def canonical_message(op: str, params: dict, timestamp: str) -> str:
    """
    Build the message string the server will reconstruct and verify against.
    op        — stable dot-separated identifier, e.g. "escrow.fund"
    params    — flat dict of the exact values the server will act on
    timestamp — ISO-8601 UTC string

    Format: op|k1=v1&k2=v2|timestamp  (keys sorted lexicographically)
    """
    def _serialize(v):
        if isinstance(v, (dict, list)):
            raise ValueError(f"Nested types not allowed: {v!r}")
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            # THE CRITICAL RULE: 10 and 10.0 both become "10", 10.5 stays "10.5".
            # If your client uses str(v) or repr(v) instead, you will get mystifying 403s.
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
```

### Example: fund an escrow

```python
import requests

BASE = "http://localhost:8000"

# Create a DID (server generates keys, private key returned once, never stored)
r = requests.post(f"{BASE}/identity/did/create").json()
did = r["did"]
private_key_hex = r["private_key"]  # store this yourself

# Fund an escrow — op is "escrow.fund", params are exactly what the server acts on
sig, ts = sign_request(private_key_hex, "escrow.fund", {"tx_id": "abc123"})

resp = requests.post(f"{BASE}/economic/escrow/fund", json={
    "tx_id": "abc123",
    "buyer_did": did,
    "signature": sig,
    "timestamp": ts,
})
```

**Replay protection:** Timestamps outside a 60-second window are rejected with 403. Generate a fresh timestamp per request.

### Intentionally open routes (no signature required)

| Route | Why |
|-------|-----|
| `POST /claim` | Open attestation — anyone can submit a claim without identity |
| `POST /proof` | Open attestation — anyone can submit a proof |
| `POST /identity/did/create` | Identity bootstrapping — you need a DID before you can sign anything |
| `POST /governance/tally` | Read-only computation — tallying votes is a public operation |

All other `POST`/`PUT`/`PATCH`/`DELETE` routes require a valid canonical signature.

## Op IDs and params

See [docs/SPEC.md](docs/SPEC.md) section 13.1 for the complete table of op IDs and the exact param dicts each endpoint signs over.

## Tech Stack

- Python 3.12
- FastAPI + aiosqlite (SQLite)
- Ed25519 (cryptography library)
- Docker

## Tests

```bash
pytest tests/ -v
```

## License

MIT
