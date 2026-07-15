# VERITAS — Verifiable Trust Infrastructure

### Provenance, Identity, and Accountability for the Internet

---

## STATUS (v1.2.0, July 2026) · full spec: docs/SPEC.md

### Built
- All 6 layers (0–5): Trust Protocol, Identity & Reputation, Content Provenance, Agent Trust, Economic Trust, Governance
- 25 authenticated endpoints with canonical payload binding and 60-second replay protection
- 13 tests including a route-enumerating meta-test that verifies every mutating endpoint rejects bad signatures
- Public protocol specification (docs/SPEC.md)
- Honest labeling: WELL_ATTESTED / LIKELY_AUTHENTIC / UNVERIFIED / POORLY_ATTESTED / CONTRADICTED — these describe evidence, not truth

### Deliberately Rejected
- AI/deepfake detection — this is an arms race detectors are losing. VERITAS does positive provenance instead: signed-at-creation, verified creator, unaltered content
- Truth verdicts — cryptography verifies provenance, not truth. The protocol reports what evidence exists and who attested to it. Human judgment decides what's true

### Aspirational (not built)
- Zero-knowledge proofs
- Tokenized incentives
- Cross-chain support

---

## The Problem

The internet doesn't know what's real. Deepfakes, bot armies, AI-generated content, fake identities. Platforms decide what you trust — their algorithms, their interests.

But here's what cryptography can actually do: prove who said something, prove it wasn't altered, prove when it was created. That's provenance, identity, and accountability.

What it cannot do: prove a claim is true. Truth requires human judgment. VERITAS doesn't replace judgment — it gives judgment verifiable evidence to work with.

---

## What VERITAS Does

**VERITAS is a trust protocol that makes provenance, identity, and attestation cryptographically verifiable.**

- **Who** made this claim? (Identity)
- **When** was it made? (Timestamping)
- **Has it been altered?** (Content hashing)
- **Who else attests to it?** (Proof aggregation)
- **What's their reputation?** (Verifiable history)

The system doesn't tell you what's true. It tells you what's proven, what's attested, and by whom — so you can decide.

---

## How It Works

Create Identity -> Register Content -> Gather Attestations -> Evaluate Evidence

- **DIDs** — Self-sovereign identity with Ed25519 keys
- **Content Registry** — Hash content, track provenance, edit chains
- **Proof Engine** — Cryptographic verification of attestations
- **Reputation** — Verifiable history with Sybil-resistant staking
- **Agents** — AI agents with delegated authority and track records
- **Escrow** — Trust-weighted transactions with dispute resolution
- **Governance** — Community voting, arbiter election, parameter control

---

## Layers

| Layer | Name | Status |
|-------|------|--------|
| 0 | Trust Protocol Core | Live |
| 1 | Identity & Reputation | Live |
| 2 | Content Provenance | Live |
| 3 | Agent Trust | Live |
| 4 | Economic Trust | Live |
| 5 | Governance & Curation | Live |

---

## What VERITAS Does NOT Do

- **It does not determine truth.** "Well-attested" means many independent sources verified the provenance — not that the claim is factually correct.
- **It does not detect AI content.** Detection is an arms race the detectors are losing. VERITAS focuses on positive provenance: signed-at-creation, verified creator, unaltered content.
- **It does not eliminate human judgment.** Disputes require arbiters. Governance requires votes. The protocol makes these processes transparent and auditable, not automatic.

---

## Known Challenges

**Sybil attacks:** Free identity creation enables reputation farming. Our approach: bootstrapping with a narrow scope (AI agents first), combined with reputation staking and web-of-trust weighting. Not solved — being built in the open.

**The oracle problem:** Cryptography verifies provenance, not truth. We're explicit about this. The system provides verifiable evidence; humans provide judgment.

**Cold start:** Trust scores need users, users need trust scores. Our wedge: AI agent ecosystems being born right now without incumbent trust infrastructure.

**Governance is the product:** Who resolves disputes? Who elects arbiters? These aren't Layer 5 add-ons — they're the core. Built in from day one.

---

## Quick Start

git clone https://github.com/balbaks/veritas.git
cd veritas
pip install -r requirements.txt
uvicorn api.server:app --reload --port 8000

Interactive docs: http://localhost:8000/docs

---

## Built By

One person. A PC. Ubuntu. AI collaboration. And the conviction that trust should be verifiable, not granted.

---

## Status

**v1.2.0 — Canonical payload binding auth on all 25 mutating routes. Building in the open.**
