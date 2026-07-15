from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timezone
import hashlib


def _encode_str(s: str) -> str:
    # Encode & = | % — in that order with % first to avoid double-encoding.
    return s.replace('%', '%25').replace('&', '%26').replace('=', '%3D').replace('|', '%7C')


def canonical_message(op: str, params: dict, timestamp: str) -> str:
    """
    op        — stable operation id, e.g. "escrow.fund". NOT the URL path.
    params    — flat dict of the exact values the server will act on.
    timestamp — ISO-8601 UTC, e.g. "2026-07-14T10:30:00.000000"

    Format: op + "|" + k1=v1&k2=v2 (keys sorted lexicographically) + "|" + timestamp

    Value serialization rules:
      float/int -> f"{float(v):.8f}".rstrip('0').rstrip('.')
                   10 and 10.0 both become "10"; 10.5 stays "10.5"
      bool      -> "true" or "false" (lowercase)
      None      -> "" (empty string)
      str       -> percent-encode & = | % characters only

    Raises ValueError for any value that is a dict or list (flat params only).
    """
    def _serialize(v):
        if isinstance(v, (dict, list)):
            raise ValueError(f"Nested dicts/lists not allowed in canonical params: {v!r}")
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return f"{float(v):.8f}".rstrip("0").rstrip(".")
        if v is None:
            return ""
        return _encode_str(str(v))

    pairs = "&".join(f"{k}={_serialize(params[k])}" for k in sorted(params.keys()))
    return f"{op}|{pairs}|{timestamp}"


def verify_request(did: str, op: str, params: dict, timestamp: str, signature: str, did_store: dict) -> bool:
    """
    Verify a signed request. Never accepts a caller-supplied message string.

    1. Rejects timestamps where abs(now_utc - ts) > 60 seconds.
    2. Looks up public key for did in did_store; returns False if missing.
    3. Reconstructs expected = canonical_message(op, params, timestamp).
    4. Returns DID.verify(did, expected, signature, pub_key_hex).
    """
    try:
        sig_time = datetime.fromisoformat(timestamp).replace(tzinfo=None)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if abs((now - sig_time).total_seconds()) > 60:
            return False
    except Exception:
        return False

    pub_key_hex = did_store.get(did, {}).get("public_key")
    if not pub_key_hex:
        return False

    expected = canonical_message(op, params, timestamp)
    return DID.verify(did, expected, signature, pub_key_hex)


class DID:
    def __init__(self):
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.did = self._generate_did()

    def _generate_did(self) -> str:
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        did_hash = hashlib.sha256(pub_bytes).hexdigest()[:32]
        return f"did:veritas:{did_hash}"

    def sign(self, message: str) -> str:
        signature = self.private_key.sign(message.encode())
        return signature.hex()

    def export_public_key(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

    @staticmethod
    def verify(did: str, message: str, signature: str, public_key_hex: str) -> bool:
        try:
            pub_bytes = bytes.fromhex(public_key_hex)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(bytes.fromhex(signature), message.encode())
            expected_did = hashlib.sha256(pub_bytes).hexdigest()[:32]
            return did == f"did:veritas:{expected_did}"
        except Exception:
            return False
