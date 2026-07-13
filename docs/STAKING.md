# Staking Design — VERITAS

## Problem

Free identity creation enables Sybil attacks. Anyone can create unlimited DIDs and farm reputation through self-attestation. Identity needs a cost without reintroducing central gatekeeping.

## Design Decisions (Open)

### What is staked?

**Option A: Native protocol token**
- Pro: Aligned incentives, token utility, protocol-owned economics
- Con: Securities law exposure, speculative dynamics, requires token distribution

**Option B: Stablecoins (USDC/DAI)**
- Pro: Stable value, no securities concern, predictable slashing
- Con: Requires external dependency, no protocol-native value capture

**Current leaning:** Stablecoins for initial bootstrapping, with a path to native token via governance proposal.

### What triggers slashing?

- **Dispute resolution loss:** If an escrow dispute resolves against a party, their stake can be slashed
- **Agent misbehavior:** If an agent accumulates unresolved disputes, the owner's stake is at risk
- **Governance vote:** Arbiters can propose slashing for malicious behavior, voted by governance

### Who can slash?

Only elected arbiters, via governance proposals. No unilateral slashing. Every slash requires a passed proposal with quorum.

### Is there a cap on stake-weighted power?

Yes. Voting power = (reputation_score / 50) * (1 + sqrt(stake) / 10). Square root dampens whale dominance. A DID with 10,000 staked has ~11x power, not 100x. Reputation earned through behavior over time matters more than raw stake.

### How does staking interact with reputation?

- Staking gives an initial reputation boost (capped at +20)
- Reputation decays naturally if the DID is inactive
- Slashing reduces both stake AND reputation
- Long-term trusted behavior outweighs stake weight

### Open Questions

1. Minimum stake to create a DID with full privileges?
2. Should unstaking have a cooldown period (e.g. 7 days)?
3. Should stake be forfeitable to counterparties in escrow disputes, or only slashed to protocol?
4. Should there be a maximum reputation cap regardless of stake?

## Current Implementation

- `ReputationRegistry.stake()` — functional, adds stake + reputation boost
- `ReputationRegistry.slash_stake()` — functional, gated by arbiter authorization
- `ReputationRegistry.get_voting_power()` — functional, uses sqrt damping
- Governance integration: slashing requires arbiter check via passed proposal

## Next Steps

1. Integrate slashing into dispute resolution flow (Layer 4 -> Layer 1)
2. Add unstaking with cooldown
3. Implement minimum stake for DID creation
4. Add stake-weighted voting to governance tally function
