from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from governance.proposals import GovernanceEngine, ProposalType
from governance.curation import CurationEngine
from governance.database import save_proposal, save_arbiter, save_curated_list
from typing import Optional

governance_router = APIRouter()
gov_engine = GovernanceEngine()
curation_engine = CurationEngine()


class CreateProposalRequest(BaseModel):
    proposer_did: str
    title: str
    description: str
    proposal_type: str
    changes: Optional[dict] = None
    duration_hours: Optional[int] = None


class VoteRequest(BaseModel):
    prop_id: str
    voter_did: str
    support: bool
    voting_power: float = 1.0


class TallyRequest(BaseModel):
    prop_id: str
    total_voting_power: float


class CreateListRequest(BaseModel):
    owner_did: str
    name: str
    description: str
    criteria: Optional[dict] = None


class AddCuratorRequest(BaseModel):
    list_id: str
    curator_did: str
    added_by: str


class AddItemRequest(BaseModel):
    list_id: str
    content_hash: str
    added_by: str
    note: str = ""


class VerifyItemRequest(BaseModel):
    list_id: str
    content_hash: str
    verifier_did: str


@governance_router.post("/proposal")
async def create_proposal(req: CreateProposalRequest):
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
    success = gov_engine.vote(req.prop_id, req.voter_did, req.support, req.voting_power)
    if not success:
        raise HTTPException(status_code=400, detail="Vote failed")
    await save_proposal(gov_engine.get_proposal(req.prop_id))
    return {"prop_id": req.prop_id, "voter": req.voter_did, "support": req.support}


@governance_router.post("/tally")
async def tally(req: TallyRequest):
    result = gov_engine.tally(req.prop_id, req.total_voting_power)
    if not result:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await save_proposal(gov_engine.get_proposal(req.prop_id))
    return result


@governance_router.post("/execute/{prop_id}")
async def execute(prop_id: str):
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
    list_id = curation_engine.create_list(req.owner_did, req.name, req.description, req.criteria)
    await save_curated_list(curation_engine.get_list(list_id))
    return {"list_id": list_id}


@governance_router.post("/curation/curator")
async def add_curator(req: AddCuratorRequest):
    success = curation_engine.add_curator(req.list_id, req.curator_did, req.added_by)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot add curator")
    await save_curated_list(curation_engine.get_list(req.list_id))
    return {"list_id": req.list_id, "curator": req.curator_did}


@governance_router.post("/curation/item")
async def add_item(req: AddItemRequest):
    success = curation_engine.add_item(req.list_id, req.content_hash, req.added_by, req.note)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot add item")
    await save_curated_list(curation_engine.get_list(req.list_id))
    return {"list_id": req.list_id, "content_hash": req.content_hash}


@governance_router.post("/curation/verify")
async def verify_item(req: VerifyItemRequest):
    success = curation_engine.verify_item(req.list_id, req.content_hash, req.verifier_did)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot verify")
    await save_curated_list(curation_engine.get_list(req.list_id))
    return {"list_id": req.list_id, "content_hash": req.content_hash, "action": "verified"}


@governance_router.post("/curation/reject")
async def reject_item(req: VerifyItemRequest):
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
