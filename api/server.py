from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
from core.engine import TrustEngine
from core.database import init_db, save_claim, save_proof, load_claims, load_proofs
from api.identity_routes import identity_router
from api.content_routes import content_router, registry
from api.agent_routes import agent_router, agent_registry, delegation_manager
from api.economic_routes import economic_router, economic_engine
from api.governance_routes import governance_router, gov_engine, curation_engine
from identity.database import init_identity_db, load_identities, load_reputation_events, load_stakes
from content.database import init_content_db, load_contents
from agents.database import init_agent_db, load_agents, load_delegations
from economic.database import init_economic_db, load_economic_data
from governance.database import init_governance_db, load_governance_data
import api.identity_routes as identity_module
import api.agent_routes as agent_module
import api.economic_routes as economic_module
import api.governance_routes as governance_module
import api.content_routes as content_module

agent_module.did_store_ref = identity_module.did_store
economic_module.did_store_ref = identity_module.did_store
economic_module.gov_engine_ref = governance_module.gov_engine
governance_module.did_store_ref = identity_module.did_store
governance_module.reputation_ref = identity_module.reputation
content_module.did_store_ref = identity_module.did_store

engine = TrustEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_identity_db()
    await init_content_db()
    await init_agent_db()
    await init_economic_db()
    await init_governance_db()
    engine.claims = await load_claims()
    engine.proofs = await load_proofs()
    loaded_identities = await load_identities()
    for did, data in loaded_identities.items():
        identity_module.did_store[did] = data
        identity_module.reputation.new_identity(did)
    await load_reputation_events(identity_module.reputation)
    await load_stakes(identity_module.reputation)
    await load_contents(registry)
    await load_agents(agent_registry)
    await load_delegations(delegation_manager)
    await load_economic_data(economic_engine)
    await load_governance_data(gov_engine, curation_engine)
    yield


app = FastAPI(title="VERITAS", version="1.2.0", lifespan=lifespan)

app.include_router(identity_router, prefix="/identity", tags=["Identity"])
app.include_router(content_router, prefix="/content", tags=["Content"])
app.include_router(agent_router, prefix="/agents", tags=["Agents"])
app.include_router(economic_router, prefix="/economic", tags=["Economic"])
app.include_router(governance_router, prefix="/governance", tags=["Governance"])


class ClaimRequest(BaseModel):
    subject: str
    predicate: str
    content: str


class ProofRequest(BaseModel):
    claim_id: str
    proof_type: str
    proof_data: str
    verifier: str


@app.get("/")
def root():
    return {
        "protocol": "VERITAS",
        "version": "1.2.0",
        "status": "operational",
        "claims": len(engine.claims),
        "identities": len(identity_module.did_store),
        "contents": len(registry.contents),
        "agents": len(agent_registry.agents),
        "proposals": len(gov_engine.proposals),
        "arbiters": len(gov_engine.arbiters)
    }


@app.post("/claim")
async def submit_claim(req: ClaimRequest):
    claim = engine.submit_claim(req.subject, req.predicate, req.content)
    await save_claim(claim)
    return {"claim_id": claim.id, "subject": claim.subject, "predicate": claim.predicate}


@app.post("/proof")
async def submit_proof(req: ProofRequest):
    proof = engine.submit_proof(req.claim_id, req.proof_type, req.proof_data, req.verifier)
    await save_proof(proof)
    return {"claim_id": proof.claim_id, "proof_type": proof.proof_type, "verifier": proof.verifier}


@app.get("/trust")
def get_trust(claim_id: str):
    verdict = engine.evaluate(claim_id)
    return {
        "claim_id": verdict.claim_id,
        "score": verdict.score.name,
        "value": verdict.score.value,
        "confidence": verdict.confidence,
        "proof_count": verdict.proof_count,
        "source_count": verdict.source_count,
        "explanation": verdict.explanation
    }
