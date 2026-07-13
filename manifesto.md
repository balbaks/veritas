# VERITAS — The Trust Layer of the Internet

### A Verifiable Trust Protocol for the Post-Truth Age

---

## The Problem

The internet is broken. Deepfakes, bot armies, AI-generated content, fake reviews, manipulated media. We no longer know what's real.

Platforms decide what you trust. Their algorithms. Their interests. Not yours.

Trust should not be granted by corporations. It must be **mathematically provable** and **visually undeniable**.

---

## The Solution

**VERITAS** is a trust protocol that sits beneath the internet — a new layer of reality.

It assigns every piece of digital content a **Verifiable Trust Score** backed by cryptographic proofs, not authority.

Anyone can submit a claim. Anyone can submit proof. The protocol evaluates truth independently.

No central authority. No platform dependency. Just math.

---

## How It Works

Submit Claim -> Gather Proofs -> Evaluate Trust -> Verdict

- **Claims** — statements, content, identities
- **Proofs** — cryptographic signatures, hash matches, attestations, ZK proofs
- **Trust Scores** — 0 to 100, with confidence levels
- **Verdicts** — VERIFIED, LIKELY_TRUE, UNVERIFIED, SUSPICIOUS, DISPROVEN

---

## Layers

| Layer | Name | Status |
|-------|------|--------|
| 0 | Trust Inversion Protocol (TIPC) | Live |
| 1 | Identity & Reputation | Next |
| 2 | Content Authenticity | Planned |
| 3 | Agent Trust (AI reputation) | Planned |
| 4 | Economic Trust | Planned |
| 5 | Governance & Curation | Planned |

---

## Layer 0 — Trust Inversion Protocol (Current)

Working now:
- Submit claims with subject, predicate, content
- Submit proofs from multiple verifiers
- Evaluate trust scores with confidence levels
- SQLite persistence (survives restarts)
- REST API (FastAPI + OpenAPI docs)
- Docker containerized

API Endpoints:
- GET  /                          — Protocol status
- POST /claim                     — Submit a claim
- POST /proof                     — Submit a proof
- GET  /trust?claim_id=<id>       — Evaluate trust score
- GET  /docs                      — Interactive API documentation

---

## Quick Start

git clone https://github.com/balbaks/veritas.git
cd veritas
docker build -t veritas-node .
docker run -d -p 8000:8000 veritas-node
curl http://localhost:8000/

---

## The Vision

In 5-10 years, VERITAS becomes the trust substrate of the internet.

- Every social media platform plugs into it
- Every AI agent checks it before acting
- Every news article carries a live trust badge
- Every identity carries verifiable reputation
- Every transaction knows the trustworthiness of the counterparty

This is not a product. This is infrastructure. A public good. A new layer of reality.

---

## Built By

One person. A PC. Ubuntu. AI. And the conviction that trust should be provable, not granted.

---

## Status

Layer 0: Operational. Layer 1: Coming.

This is the basement. The cathedral rises from here.
