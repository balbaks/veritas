from datetime import datetime, timezone
from typing import Optional


class CurationEngine:
    def __init__(self):
        self.curated_lists: dict = {}
        self.curator_trust: dict = {}

    def create_list(self, owner_did: str, name: str, description: str, criteria: dict = None) -> str:
        list_id = f"curated:{owner_did}:{name}:{datetime.now(timezone.utc).timestamp()}"
        self.curated_lists[list_id] = {
            "list_id": list_id,
            "owner_did": owner_did,
            "name": name,
            "description": description,
            "criteria": criteria or {},
            "items": [],
            "curators": [owner_did],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        return list_id

    def add_curator(self, list_id: str, curator_did: str, added_by: str) -> bool:
        lst = self.curated_lists.get(list_id)
        if not lst or added_by != lst["owner_did"]:
            return False
        if curator_did not in lst["curators"]:
            lst["curators"].append(curator_did)
        return True

    def add_item(self, list_id: str, content_hash: str, added_by: str, note: str = "") -> bool:
        lst = self.curated_lists.get(list_id)
        if not lst or added_by not in lst["curators"]:
            return False
        lst["items"].append({
            "content_hash": content_hash,
            "added_by": added_by,
            "note": note,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "verified_count": 0,
            "rejected_count": 0
        })
        lst["updated_at"] = datetime.now(timezone.utc).isoformat()
        return True

    def verify_item(self, list_id: str, content_hash: str, verifier_did: str) -> bool:
        lst = self.curated_lists.get(list_id)
        if not lst:
            return False
        for item in lst["items"]:
            if item["content_hash"] == content_hash:
                item["verified_count"] += 1
                return True
        return False

    def reject_item(self, list_id: str, content_hash: str, rejector_did: str) -> bool:
        lst = self.curated_lists.get(list_id)
        if not lst:
            return False
        for item in lst["items"]:
            if item["content_hash"] == content_hash:
                item["rejected_count"] += 1
                return True
        return False

    def get_curation_score(self, list_id: str, content_hash: str) -> Optional[float]:
        lst = self.curated_lists.get(list_id)
        if not lst:
            return None
        for item in lst["items"]:
            if item["content_hash"] == content_hash:
                total = item["verified_count"] + item["rejected_count"]
                if total == 0:
                    return 0.5
                return item["verified_count"] / total
        return None

    def get_list(self, list_id: str) -> Optional[dict]:
        return self.curated_lists.get(list_id)

    def get_lists_by_owner(self, owner_did: str) -> list:
        return [l for l in self.curated_lists.values() if l["owner_did"] == owner_did]
