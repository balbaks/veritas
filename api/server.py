from fastapi import FastAPI
from pydantic import BaseModel
from core.engine import TrustEngine
from core.database import init_db, save_claim, save_proof, load_claims, load_proofs
from api.identity_routes import identity_router
from api.content_routes import content_router, registry
from api.agent_routes import agent_router, agent_registry, delegation_manager
from identity.database import init_identity_db, load_identities, load_reputation_events
from content.database import init_content_db, load_contents
from agents.database import init_agent_db, load_agents, load_delegations
import api.identity_routes as identity_module

app = FastAPI(title="VERITAS", version="0.8.0")
engine = TrustEngine()


@app.on_event("startup")
async def startup():
    await init_db()
    await init_identity_db()
    await init_content_db()
    await init_agent_db()
    engine.claims = await load_claims()
    engine.proofs = await load_proofs()
    loaded_identities = await load_identities()
    for did, data in loaded_identities.items():
        identity_module.did_store[did] = data
        identity_module.reputation.new_identity(did)
    await load_reputation_events(identity_module.reputation)
    await load_contents(registry)
    await load_agents(agent_registry)
    await load_delegations(delegation_manager)


app.include_router(identity_router, prefix="/identity", tags=["Identity"])
app.include_router(content_router, prefix="/content", tags=["Content"])
app.include_router(agent_router, prefix="/agents", tags=["Agents"])


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
        "status": "operational",
        "claims": len(engine.claims),
        "identities": len(identity_module.did_store),
        "contents": len(registry.contents),
        "agents": len(agent_registry.agents)
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
