from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from governance.proposals import GovernanceEngine, ProposalType
from governance.curation import CurationEngine
from governance.database import save_proposal, save_arbiter, save_curated_list
from identity.did import DID
from typing import Optional

governance_router = APIRouter()
gov_engine = GovernanceEngine()
curation_engine = CurationEngine()

did_store_ref = None


def _verify_did(did: str, message: str, signature: str) -> bool:
    if did_store_ref is None:
        return False
    pub_key = did_store_ref.get(did, {}).get("public_key")
    if not pub_key:
        return False
    return DID.verify(did, message, signature, pub_key)


class CreateProposalRequest(BaseModel):
    proposer_did: str
    title: str
    description: str
    proposal_type: str
    changes: Optional[dict] = None
    duration_hours: Optional[int] = None
    signature: str
    message: str


class VoteRequest(BaseModel):
    prop_id: str
    voter_did: str
    support: bool
    signature: str
    message: str


class TallyRequest(BaseModel):
    prop_id: str


class ExecuteRequest(BaseModel):
    prop_id: str
    executor_did: str
    signature: str
    message: str


class CreateListRequest(BaseModel):
    owner_did: str
    name: str
    description: str
    criteria: Optional[dict] = None
    signature: str
    message: str


class AddCuratorRequest(BaseModel):
    list_id: str
    curator_did: str
    added_by: str
    signature: str
    message: str


class AddItemRequest(BaseModel):
    list_id: str
    content_hash: str
    added_by: str
    note: str = ""
    signature: str
    message: str


class VerifyItemRequest(BaseModel):
    list_id: str
    content_hash: str
    verifier_did: str
    signature: str
    message: str


@governance_router.post("/proposal")
async def create_proposal(req: CreateProposalRequest):
    if not _verify_did(req.proposer_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid proposer signature")
    try:
        prop_type = ProposalType(req.proposal_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal type")
    prop_id = gov_engine.create_proposal(
        req.proposer_did, req.title, req.description, prop_type, req.changes, req.duration_hours
    )
    await save_proposal(gov_engine.get_proposal(prop_id))
    return {"prop_id": prop_id, "status": "active"}


@governance_router.post("/vote")
async def vote(req: VoteRequest):
    if not _verify_did(req.voter_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid voter signature")
    from api.identity_routes import reputation
    voting_power = reputation.get_voting_power(req.voter_did)
    success = gov_engine.vote(req.prop_id, req.voter_did, req.support, voting_power)
    if not success:
        raise HTTPException(status_code=400, detail="Vote failed")
    await save_proposal(gov_engine.get_proposal(req.prop_id))
    return {"prop_id": req.prop_id, "voter": req.voter_did, "support": req.support, "voting_power": voting_power}


@governance_router.post("/tally")
async def tally(req: TallyRequest):
    from api.identity_routes import reputation
    total_vp = sum(reputation.get_voting_power(did) for did in reputation.scores.keys())
    if total_vp == 0:
        total_vp = 100
    result = gov_engine.tally(req.prop_id, total_vp)
    if not result:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await save_proposal(gov_engine.get_proposal(req.prop_id))
    return result


@governance_router.post("/execute/{prop_id}")
async def execute(prop_id: str, req: ExecuteRequest):
    if not _verify_did(req.executor_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid executor signature")
    success = gov_engine.execute(prop_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot execute")
    await save_proposal(gov_engine.get_proposal(prop_id))
    prop = gov_engine.get_proposal(prop_id)
    if prop["proposal_type"] == ProposalType.ARBITER_ELECTION:
        arbiter_did = prop["changes"].get("arbiter_did")
        if arbiter_did and arbiter_did in gov_engine.arbiters:
            await save_arbiter(arbiter_did, gov_engine.arbiters[arbiter_did])
    return {"prop_id": prop_id, "status": "executed"}


@governance_router.get("/proposal/{prop_id}")
def get_proposal(prop_id: str):
    prop = gov_engine.get_proposal(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return prop


@governance_router.get("/parameters")
def get_parameters():
    return gov_engine.get_parameters()


@governance_router.get("/arbiters")
def get_arbiters():
    return gov_engine.get_arbiters()


@governance_router.post("/curation/list")
async def create_list(req: CreateListRequest):
    if not _verify_did(req.owner_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid owner signature")
    list_id = curation_engine.create_list(req.owner_did, req.name, req.description, req.criteria)
    await save_curated_list(curation_engine.get_list(list_id))
    return {"list_id": list_id}


@governance_router.post("/curation/curator")
async def add_curator(req: AddCuratorRequest):
    if not _verify_did(req.added_by, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    success = curation_engine.add_curator(req.list_id, req.curator_did, req.added_by)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot add curator")
    await save_curated_list(curation_engine.get_list(req.list_id))
    return {"list_id": req.list_id, "curator": req.curator_did}


@governance_router.post("/curation/item")
async def add_item(req: AddItemRequest):
    if not _verify_did(req.added_by, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    lst = curation_engine.get_list(req.list_id)
    if not lst or req.added_by not in lst["curators"]:
        raise HTTPException(status_code=403, detail="Only curators can add items")
    success = curation_engine.add_item(req.list_id, req.content_hash, req.added_by, req.note)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot add item")
    await save_curated_list(curation_engine.get_list(req.list_id))
    return {"list_id": req.list_id, "content_hash": req.content_hash}


@governance_router.post("/curation/verify")
async def verify_item(req: VerifyItemRequest):
    if not _verify_did(req.verifier_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    lst = curation_engine.get_list(req.list_id)
    if not lst or req.verifier_did not in lst["curators"]:
        raise HTTPException(status_code=403, detail="Only curators can verify items")
    success = curation_engine.verify_item(req.list_id, req.content_hash, req.verifier_did)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot verify")
    await save_curated_list(curation_engine.get_list(req.list_id))
    return {"list_id": req.list_id, "content_hash": req.content_hash, "action": "verified"}


@governance_router.post("/curation/reject")
async def reject_item(req: VerifyItemRequest):
    if not _verify_did(req.verifier_did, req.message, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    lst = curation_engine.get_list(req.list_id)
    if not lst or req.verifier_did not in lst["curators"]:
        raise HTTPException(status_code=403, detail="Only curators can reject items")
    success = curation_engine.reject_item(req.list_id, req.content_hash, req.verifier_did)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot reject")
    await save_curated_list(curation_engine.get_list(req.list_id))
    return {"list_id": req.list_id, "content_hash": req.content_hash, "action": "rejected"}


@governance_router.get("/curation/list/{list_id}")
def get_list(list_id: str):
    lst = curation_engine.get_list(list_id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    return lst


@governance_router.get("/curation/score/{list_id}/{content_hash}")
def get_curation_score(list_id: str, content_hash: str):
    score = curation_engine.get_curation_score(list_id, content_hash)
    if score is None:
        raise HTTPException(status_code=404, detail="Content not found in list")
    return {"list_id": list_id, "content_hash": content_hash, "score": score}
