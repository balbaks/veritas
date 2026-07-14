from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import hashlib
from datetime import datetime, timedelta


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

    @staticmethod
    def build_message(endpoint: str, params: dict, timestamp: str) -> str:
        """Build a canonical message from endpoint + sorted params + timestamp."""
        sorted_items = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_items)
        return f"{endpoint}|{param_str}|{timestamp}"

    @staticmethod
    def verify_with_timestamp(did: str, message: str, signature: str, public_key_hex: str, timestamp: str, max_age_seconds: int = 60) -> bool:
        """Verify DID + check timestamp is within window."""
        if not DID.verify(did, message, signature, public_key_hex):
            return False
        try:
            sig_time = datetime.fromisoformat(timestamp)
            now = datetime.utcnow()
            diff = abs((now - sig_time).total_seconds())
            return diff <= max_age_seconds
        except Exception:
            return False
