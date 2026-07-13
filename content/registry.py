import hashlib
from datetime import datetime
from typing import Optional


class ContentRegistry:
    def __init__(self):
        self.contents: dict = {}

    def register(self, data: bytes, mime_type: str, creator_did: str, metadata: dict = None) -> str:
        content_hash = hashlib.sha256(data).hexdigest()
        self.contents[content_hash] = {
            "hash": content_hash,
            "size": len(data),
            "mime_type": mime_type,
            "creator_did": creator_did,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "edit_chain": [],
            "origin_verified": False,
            "ai_generated_score": None
        }
        return content_hash

    def get(self, content_hash: str) -> Optional[dict]:
        return self.contents.get(content_hash)

    def add_edit(self, content_hash: str, editor_did: str, new_hash: str, edit_type: str):
        if content_hash in self.contents:
            self.contents[content_hash]["edit_chain"].append({
                "editor_did": editor_did,
                "new_hash": new_hash,
                "edit_type": edit_type,
                "timestamp": datetime.utcnow().isoformat()
            })

    def verify_origin(self, content_hash: str, creator_did: str) -> bool:
        content = self.contents.get(content_hash)
        if content and content["creator_did"] == creator_did:
            content["origin_verified"] = True
            return True
        return False

    def set_ai_score(self, content_hash: str, score: float):
        if content_hash in self.contents:
            self.contents[content_hash]["ai_generated_score"] = score

    def get_provenance(self, content_hash: str) -> Optional[dict]:
        content = self.contents.get(content_hash)
        if not content:
            return None
        return {
            "hash": content["hash"],
            "creator": content["creator_did"],
            "created_at": content["timestamp"],
            "origin_verified": content["origin_verified"],
            "ai_generated_score": content["ai_generated_score"],
            "edit_count": len(content["edit_chain"]),
            "edit_chain": content["edit_chain"]
        }
