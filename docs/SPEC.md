# VERITAS Protocol Specification v1.2.0

## Abstract

VERITAS is a protocol for verifiable provenance, identity, and attestation. It enables cryptographic proof of who created content, when it was created, whether it has been altered, and who else attests to it. It does not determine truth — it provides verifiable evidence for human judgment.

---

## 1. Protocol vs Implementation

This document describes the VERITAS protocol — the data formats, cryptographic operations, and semantics that any conforming implementation must support. The reference implementation (github.com/balbaks/veritas) is a FastAPI server with SQLite persistence. It is one implementation, not the protocol. FastAPI, Python, SQLite, Docker, and server-based timestamping are implementation choices, not protocol requirements.

---

## 2. Identifiers

DIDs: did:veritas:{32-hex-chars} — Ed25519 keypair, SHA256(public_key)[:32]
Agents: {16-hex-chars} — SHA256(owner_did + agent_type + capabilities + timestamp)[:16]
Content: {64-hex-chars} — SHA256(content_bytes)
Transactions: {16-hex-chars} — SHA256(buyer_did + seller_did + amount + currency + timestamp)[:16]
Proposals: {16-hex-chars} — SHA256(proposer_did + title + timestamp)[:16]

---

## 3. Cryptographic Primitives

Key Generation: Ed25519 — 32-byte private key, 32-byte public key, 64-byte signatures
Signing: signature = Ed25519.sign(private_key, message.encode())
Verification: valid = Ed25519.verify(public_key, message.encode(), signature)
Content Hashing: SHA256(content_bytes)

---

## 4. Attestation Model

A claim has: id, subject, predicate, content_hash, timestamp.
A proof has: claim_id, proof_type (hash_match|signature|attestation|zk_proof), proof_data, verifier, timestamp.

Proof validation:
- hash_match: proof_data must equal claim.content_hash
- signature: proof_data ≥ 64 chars, verifier non-empty
- attestation: proof_data ≥ 16 chars, verifier non-empty
- zk_proof: proof_data starts with "zk:", >16 chars

Verdict semantics:
- WELL_ATTESTED: ≥3 valid proofs from ≥2 independent verifiers
- LIKELY_AUTHENTIC: ≥2 valid proofs
- UNVERIFIED: 0-1 valid proofs
- POORLY_ATTESTED: insufficient valid proofs
- CONTRADICTED: all submitted proofs failed validation

CRITICAL: Verdicts describe attestation evidence, not truth. A CONTRADICTED claim may still be factually true. The protocol reports disagreement among verifiers, not falsehood.

---

## 5. Reputation Model

Scores: 0.0–100.0. New identities start at 50.0 (NEUTRAL).
Standings: TRUSTED (≥80), GOOD (≥60), NEUTRAL (≥40), LOW (≥20), UNTRUSTWORTHY (<20).
All modifications recorded with timestamp and reason.

Staking: stake(did, amount) adds to balance, grants reputation bonus of min(amount/10, 20). Stakes persist across sessions. Slashing gated behind elected arbiters.

Voting Power: (reputation_score / 50.0) * (1 + sqrt(stake) / 10)
Square-root dampening prevents linear wealth dominance.

---

## 6. Content Provenance

Registration: content_bytes + mime_type + creator_did + metadata → SHA256 hash. Creator must provide valid Ed25519 signature.
Edit chain: editor_did, new_hash, edit_type, timestamp per edit. Editor must provide valid Ed25519 signature.
Origin verification: claimed creator matches registered creator. Requires creator signature.
Provenance record: hash, creator, timestamp, origin status, edit count, edit chain.
AI detection: internal only, not exposed as a feature.

---

## 7. Known Limitations

7.1 Proof Validation: Reference implementation shape-checks proofs; full cryptographic signature verification is the intended target.

7.2 Sybil Resistance: Staking raises cost but does not eliminate Sybil attacks. Narrow bootstrapping scope (AI agents) and web-of-trust weighting are recommended mitigations.

7.3 Timestamp Authority: Server provides timestamps — a centralization point. Decentralized timestamping (blockchain anchoring) is a future upgrade.

7.4 The Oracle Problem: Cryptography proves provenance, not truth. Verdicts describe evidence. Applications must make this distinction clear.

7.5 Server Trust Model: Reference implementation is a trustworthy server, not a trustless protocol. DIDs created server-side (keys never stored). Trustless deployment is future architecture.

---

## 8. Governance

Proposals: parameter_change, arbiter_election, protocol_upgrade, dispute_resolution, general. Voting period default 48h. Quorum default 20%.

Voting: cryptographically signed, server-side voting power computation, one vote per DID per proposal.

Tally: total voting power from all registered identities. Passes if votes_for > votes_against AND participation ≥ quorum. Open endpoint — anyone can trigger.

Arbiter Election & Slashing: elected via governance proposals. Only elected arbiters can trigger slash_stake().

Governable parameters: trust_threshold, dispute_timeout_hours, arbiter_count, voting_period_hours, quorum_percent.

---

## 9. Agent Model

Registration: owner_did + agent_type + capabilities + metadata. Owner must provide valid Ed25519 signature.
Trust score: starts 50.0. (successful/total)*100 - (unresolved_disputes*5).
Delegation: time-bound (default 24h), permission-scoped, revocable, action-logged.
Transaction authorization: only owner or entity with active delegation can record agent transactions.

---

## 10. Economic Model

Escrow state machine: PENDING → FUNDED → RELEASED (completed) or DISPUTED → RESOLVED_BUYER (refunded) or RESOLVED_SELLER (completed).

Party binding: only buyer can fund, only seller can release, only buyer/seller can dispute or resolve.

Trust-Weighted Transactions (Future): The economic layer currently handles escrow state transitions with party binding. Trust-weighted risk scoring based on buyer, seller, and agent reputation scores is specified but not yet implemented in the reference implementation. See economic/trust_weight.py for the planned interface.

---

## 11. Curation

Curated lists: owner + multiple curators + items with content hashes.
Curation score: verified_count / (verified_count + rejected_count). No votes = 0.5.
Permissions: only curators can add, verify, or reject items.

---

## 12. Persistence Requirements

The protocol requires survival across restarts for: claims, proofs, identities (public keys only — never private keys), reputation, stakes, content registry, edit chains, agents, disputes, delegations, transactions, escrows, proposals, votes, arbiters, curated lists.

---

## 13. API Conventions

### 13.1 Authenticated Endpoints — Canonical Signature Scheme (v1.2.0)

All mutating endpoints require an Ed25519 signature over a deterministically serialized canonical message. The server reconstructs the message from actual request parameters — no caller-supplied message string is accepted.

**Canonical message format:**
```
op|k1=v1&k2=v2&...|timestamp
```
- `op` — stable dot-separated operation identifier (e.g. `"escrow.fund"`)
- Key-value pairs sorted lexicographically by key, joined with `&`
- `timestamp` — ISO-8601 UTC string (e.g. `"2026-07-14T10:30:00.000000"`)

**Value serialization rules:**
- `float`/`int` → `f"{float(v):.8f}".rstrip('0').rstrip('.')` — `10` and `10.0` both become `"10"`, `10.5` stays `"10.5"`. **This is the rule most likely to produce 403s** if your client uses a different float format.
- `bool` → `"true"` or `"false"` (lowercase)
- `None` → `""` (empty string)
- `str` → percent-encode `%→%25`, `&→%26`, `=→%3D`, `|→%7C` (in that order, `%` first)
- `dict` / `list` → raises ValueError — params must be flat

**Replay protection:** Timestamps outside a 60-second window are rejected with 403.

**Per-endpoint op IDs and params:**

| Endpoint | Op ID | Params |
|----------|-------|--------|
| POST /content/register | `content.register` | `{creator_did}` |
| POST /content/edit | `content.edit` | `{content_hash, edit_type, editor_did, new_hash}` |
| POST /content/verify-origin | `content.verify_origin` | `{content_hash, creator_did}` |
| POST /identity/reputation/{did}/increment | `identity.reputation.increment` | `{amount, did, reason}` |
| POST /identity/reputation/{did}/decrement | `identity.reputation.decrement` | `{amount, did, reason}` |
| POST /identity/stake | `identity.stake` | `{amount, did}` |
| POST /agents/register | `agent.register` | `{agent_type, owner_did}` |
| POST /agents/{id}/transaction | `agent.transaction` | `{agent_id, authorized_by, success}` |
| POST /agents/{id}/dispute | `agent.dispute` | `{agent_id, filed_by}` |
| POST /agents/delegate | `agent.delegate` | `{agent_id, owner_did}` |
| POST /agents/delegate/{id}/revoke | `agent.delegate.revoke` | `{delegation_id, owner_did}` |
| POST /agents/delegate/log | `agent.delegate.log` | `{action, authorized_by, delegation_id}` |
| POST /economic/transaction | `escrow.transaction.create` | `{amount, buyer_did, currency, seller_did}` |
| POST /economic/escrow/fund | `escrow.fund` | `{tx_id}` |
| POST /economic/escrow/{id}/release | `escrow.release` | `{escrow_id}` |
| POST /economic/escrow/{id}/dispute | `escrow.dispute` | `{escrow_id, reason}` |
| POST /economic/escrow/{id}/resolve | `escrow.resolve` | `{escrow_id, favor_buyer}` |
| POST /governance/proposal | `gov.proposal` | `{proposal_type, proposer_did, title}` |
| POST /governance/vote | `gov.vote` | `{prop_id, support}` |
| POST /governance/execute/{id} | `gov.execute` | `{executor_did, prop_id}` |
| POST /governance/curation/list | `gov.curation.create` | `{name, owner_did}` |
| POST /governance/curation/curator | `gov.curation.curator.add` | `{added_by, curator_did, list_id}` |
| POST /governance/curation/item | `gov.curation.add` | `{added_by, content_hash, list_id}` |
| POST /governance/curation/verify | `gov.curation.verify` | `{content_hash, list_id, verifier_did}` |
| POST /governance/curation/reject | `gov.curation.remove` | `{content_hash, list_id, verifier_did}` |

### 13.2 Open Endpoints (no auth by design)

| Endpoint | Reason |
|----------|--------|
| POST /claim | Open attestation — anyone can submit a claim |
| POST /proof | Open attestation — anyone can submit a proof |
| POST /identity/did/create | Identity creation — keys returned once, never stored |
| POST /governance/tally | Read-only computation — anyone can trigger a tally |

### 13.3 Read Endpoints

All GET endpoints are open. No authentication required.

### 13.4 Error Responses

- `403`: Invalid signature or unauthorized
- `404`: Resource not found
- `400`: Invalid request or state transition

---

## 14. Threat Model

Attacker goals: forge attestations, farm reputation via Sybil, grief escrow, capture arbiter elections, tamper with provenance.
Defenses: Ed25519 on all mutations, staking cost, party binding, server-side voting power, arbiter-gated slashing, content hashing.
Open vectors: timestamp manipulation, proof validation depth, Sybil below economic threshold, arbiter collusion.

---

## 15. Version History

v1.0.0: Initial 5-layer protocol
v1.1.0: Honest labels, Sybil staking, AI detection removed from API
v1.1.1: Governance auth, server-side voting power, sqrt damping
v1.1.2: Execute auth, tally cleanup
v1.1.3: Content auth (register/edit/verify-origin), SPEC accuracy
v1.2.0: Canonical signature auth — deterministic payload binding, 60s replay window, message field eliminated, verify_request as single shared function, all 25 mutating routes covered

Reference implementation: github.com/balbaks/veritas — Python 3.12, FastAPI, SQLite, Docker, MIT license.
