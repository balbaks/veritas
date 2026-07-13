from fastapi import FastAPI
from pydantic import BaseModel
from core.engine import TrustEngine

app = FastAPI(title="VERITAS TIPC", version="0.1.0")
engine = TrustEngine()


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
    return {"protocol": "VERITAS", "layer": "TIPC", "status": "operational"}


@app.post("/claim")
def submit_claim(req: ClaimRequest):
    claim = engine.submit_claim(req.subject, req.predicate, req.content)
    return {"claim_id": claim.id, "subject": claim.subject, "predicate": claim.predicate}


@app.post("/proof")
def submit_proof(req: ProofRequest):
    proof = engine.submit_proof(req.claim_id, req.proof_type, req.proof_data, req.verifier)
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
