from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from content.registry import ContentRegistry
from content.detector import AIContentDetector
from content.database import save_content, save_edit
from identity.did import DID
from datetime import datetime

content_router = APIRouter()
registry = ContentRegistry()
detector = AIContentDetector()

did_store_ref = None


def _verify_did(did: str, message: str, signature: str, timestamp: str) -> bool:
    if did_store_ref is None:
        return False
    pub_key = did_store_ref.get(did, {}).get("public_key")
    if not pub_key:
        return False
    return DID.verify_with_timestamp(did, message, signature, pub_key, timestamp)


class VerifyOriginRequest(BaseModel):
    content_hash: str
    creator_did: str
    signature: str
    timestamp: str


class EditRequest(BaseModel):
    content_hash: str
    editor_did: str
    new_hash: str
    edit_type: str
    signature: str
    timestamp: str


@content_router.post("/register")
async def register_content(
    data: UploadFile = File(...),
    creator_did: str = Form(...),
    signature: str = Form(...),
    timestamp: str = Form(...),
    title: str = Form(None)
):
    msg = DID.build_message("content_register", {"creator_did": creator_did}, timestamp)
    if not _verify_did(creator_did, msg, signature, timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired creator signature")

    content_bytes = await data.read()
    mime_type = data.content_type or "application/octet-stream"
    metadata = {"title": title, "filename": data.filename}

    content_hash = registry.register(content_bytes, mime_type, creator_did, metadata)
    analysis = detector.analyze(content_bytes, mime_type, metadata)
    registry.set_ai_score(content_hash, analysis["ai_generated_score"])

    await save_content(content_hash, len(content_bytes), mime_type, creator_did, datetime.utcnow().isoformat(), metadata, False, analysis["ai_generated_score"])

    return {
        "content_hash": content_hash,
        "size": len(content_bytes),
        "mime_type": mime_type,
        "creator_did": creator_did,
        "provenance_recorded": True
    }


@content_router.get("/provenance/{content_hash}")
def get_provenance(content_hash: str):
    provenance = registry.get_provenance(content_hash)
    if not provenance:
        raise HTTPException(status_code=404, detail="Content not found")
    return provenance


@content_router.post("/verify-origin")
def verify_origin(req: VerifyOriginRequest):
    msg = DID.build_message("content_verify_origin", {
        "content_hash": req.content_hash, "creator_did": req.creator_did
    }, req.timestamp)
    if not _verify_did(req.creator_did, msg, req.signature, req.timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired creator signature")
    result = registry.verify_origin(req.content_hash, req.creator_did)
    return {"content_hash": req.content_hash, "origin_verified": result}


@content_router.post("/edit")
async def add_edit(req: EditRequest):
    msg = DID.build_message("content_edit", {
        "content_hash": req.content_hash, "edit_type": req.edit_type,
        "editor_did": req.editor_did, "new_hash": req.new_hash
    }, req.timestamp)
    if not _verify_did(req.editor_did, msg, req.signature, req.timestamp):
        raise HTTPException(status_code=403, detail="Invalid or expired editor signature")
    registry.add_edit(req.content_hash, req.editor_did, req.new_hash, req.edit_type)
    await save_edit(req.content_hash, req.editor_did, req.new_hash, req.edit_type, datetime.utcnow().isoformat())
    return {"content_hash": req.content_hash, "edit_type": req.edit_type, "editor": req.editor_did}
