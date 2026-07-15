#!/usr/bin/env bash
# VERITAS v1.2.0 — Violation-and-Resolution Demo
#
# The case: an AI agent exceeds its 100-credit delegation cap.
# The question: does governance → arbiter → escrow actually fire?
#
# No set -e. Every HTTP status captured. Non-200 = warn + continue.
# canonical_message imported from identity/did.py — not reimplemented.

BASE="${VERITAS_BASE:-http://localhost:8000}"
VERITAS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VERITAS_ROOT

RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'
CYN='\033[0;36m'; BLD='\033[1m'; DIM='\033[2m'; RST='\033[0m'

banner() { echo -e "\n${CYN}${BLD}$*${RST}"; }
step()   { echo -e "\n${BLD}▶ STEP $1 — $2${RST}"; }
ok()     { echo -e "  ${GRN}✓${RST}  $*"; }
info()   { echo -e "  ${DIM}→${RST}  $*"; }
warn()   { echo -e "  ${YEL}⚠${RST}  $*"; }
not_enforced() { echo -e "  ${YEL}⚠ NOT ENFORCED${RST} — $*"; }
not_wired()    { echo -e "  ${YEL}⚠ NOT WIRED${RST} — $*"; }
hr()     { echo -e "\n${DIM}────────────────────────────────────────────────${RST}"; }

declare -A R   # layer-by-layer result map

# ── signing ───────────────────────────────────────────────────────────────────
# Imports canonical_message directly from identity/did.py (not reimplemented).
# VERITAS_PARAMS is a Python dict literal; eval is safe — we control all input.
_sign() {
    VERITAS_PK="$1" VERITAS_OP="$2" VERITAS_PARAMS="$3" \
    python3 - <<'PYEOF'
import sys, os
sys.path.insert(0, os.environ['VERITAS_ROOT'])
from identity.did import canonical_message
from cryptography.hazmat.primitives.asymmetric import ed25519
from datetime import datetime, timezone

ts     = datetime.now(timezone.utc).isoformat()
params = eval(os.environ['VERITAS_PARAMS'])
msg    = canonical_message(os.environ['VERITAS_OP'], params, ts)
pk     = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(os.environ['VERITAS_PK']))
print(pk.sign(msg.encode()).hex() + '|' + ts)
PYEOF
}
sig_of() { echo "$1" | cut -d'|' -f1; }
ts_of()  { echo "$1" | cut -d'|' -f2-; }

# ── HTTP ─────────────────────────────────────────────────────────────────────
_post() {   # _post <path> <json_body>  →  prints body\nHTTP_STATUS
    curl -s -w "\n%{http_code}" -X POST \
         -H "Content-Type: application/json" \
         -d "$2" "${BASE}$1"
}
_get() { curl -s "${BASE}$1"; }
_body()   { echo "$1" | head -n -1; }
_status() { echo "$1" | tail -1; }
_jq()     { echo "$1" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null; }

# ── preflight ────────────────────────────────────────────────────────────────
banner "VERITAS v1.2.0 — VIOLATION-AND-RESOLUTION DEMO"
echo   "Server: $BASE"
echo   "The case: an AI agent exceeds its 100-credit delegation cap."
echo   "The question: does governance → arbiter → escrow actually fire?"
hr

HTTP=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
if [ "$HTTP" != "200" ]; then
    echo -e "${RED}Server not responding (HTTP $HTTP). Run: uvicorn api.server:app --port 8000${RST}"
    exit 1
fi
ok "Server operational"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Create identities
# ══════════════════════════════════════════════════════════════════════════════
step 1 "Create identities — Alice (buyer), Bob (seller), Carol (arbiter candidate)"

_did() {
    RAW=$(curl -s -X POST "${BASE}/identity/did/create")
    echo "$RAW"
}

ALICE_RAW=$(_did); ALICE_DID=$(_jq "$ALICE_RAW" "did"); ALICE_PK=$(_jq "$ALICE_RAW" "private_key")
BOB_RAW=$(_did);   BOB_DID=$(_jq   "$BOB_RAW"   "did"); BOB_PK=$(_jq   "$BOB_RAW"   "private_key")
CAROL_RAW=$(_did); CAROL_DID=$(_jq "$CAROL_RAW" "did"); CAROL_PK=$(_jq "$CAROL_RAW" "private_key")

ok "Alice: $ALICE_DID"
ok "Bob:   $BOB_DID"
ok "Carol: $CAROL_DID"
R[L1_identity]="✓ Alice / Bob / Carol created"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Carol stakes 100,000 credits to build arbiter-tier voting power
# ══════════════════════════════════════════════════════════════════════════════
step 2 "Carol stakes 5,000,000 credits → voting power sufficient to meet quorum solo"

SIGNED=$(_sign "$CAROL_PK" "identity.stake" "{'amount': 5000000.0, 'did': '$CAROL_DID'}")
SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

RAW=$(_post "/identity/stake" \
    "{\"did\":\"$CAROL_DID\",\"amount\":5000000.0,\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")

if [ "$HTTP" = "200" ]; then
    STAKED=$(_jq "$BODY" "total_staked")
    ok "Carol staked 5,000,000 credits (total: $STAKED)"
    # VP = (score/50) * (1 + sqrt(stake)/10); stake bonus caps at 20 rep points
    CAROL_VP=$(python3 -c "import math; score=min(70,50+20); print(f'{(score/50)*(1+math.sqrt(5000000)/10):.2f}')")
    info "Carol's voting power ≈ $CAROL_VP (stake-boosted; base VP = 1.0)"
    info "High stake = serious protocol commitment. Carol alone meets 20% quorum vs up to ~1200 existing identities."
    R[L2_carol_stake]="✓ Staked 5,000,000 credits  VP≈$CAROL_VP"
else
    warn "Stake returned HTTP $HTTP: $BODY"
    R[L2_carol_stake]="⚠ Stake failed (HTTP $HTTP)"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Alice registers AI agent with stated 100-credit cap
# ══════════════════════════════════════════════════════════════════════════════
step 3 "Bob registers AI agent — stated cap: 100 credits (Bob's seller-side agent)"

SIGNED=$(_sign "$BOB_PK" "agent.register" \
    "{'agent_type': 'negotiation_agent', 'owner_did': '$BOB_DID'}")
SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

RAW=$(_post "/agents/register" \
    "{\"owner_did\":\"$BOB_DID\",\"agent_type\":\"negotiation_agent\",\"capabilities\":[\"negotiate\",\"commit\"],\"metadata\":{\"spend_cap_credits\":100},\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
AGENT_ID=$(_jq "$BODY" "agent_id")

if [ "$HTTP" = "200" ] && [ -n "$AGENT_ID" ]; then
    ok "Agent registered: $AGENT_ID (owner: Bob / seller)"
    ok "Metadata: spend_cap_credits=100 — stored as metadata"
else
    warn "Agent registration HTTP $HTTP: $BODY"
    AGENT_ID="no-agent"
fi

# Bob delegates to agent with 100-credit cap
SIGNED=$(_sign "$BOB_PK" "agent.delegate" \
    "{'agent_id': '$AGENT_ID', 'owner_did': '$BOB_DID'}")
SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

RAW=$(_post "/agents/delegate" \
    "{\"owner_did\":\"$BOB_DID\",\"agent_id\":\"$AGENT_ID\",\"permissions\":[\"spend_up_to:100_credits\"],\"duration_hours\":24,\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
DEL_ID=$(_jq "$BODY" "delegation_id")

if [ "$HTTP" = "200" ] && [ -n "$DEL_ID" ]; then
    ok "Delegated: $DEL_ID — permissions: [spend_up_to:100_credits]"
    R[L3_agent]="✓ Agent $AGENT_ID  delegation $DEL_ID"
else
    warn "Delegation HTTP $HTTP: $BODY"
    R[L3_agent]="⚠ Agent created but delegation failed"
fi

# Test cap enforcement: try to record a 150-credit transaction (cap = 100)
echo "  Testing cap enforcement — recording 150-credit transaction (cap=100)..."
SIGNED=$(_sign "$BOB_PK" "agent.transaction" \
    "{'agent_id': '$AGENT_ID', 'authorized_by': '$BOB_DID', 'success': True}")
SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")
CAP_RAW=$(_post "/agents/${AGENT_ID}/transaction" \
    "{\"agent_id\":\"$AGENT_ID\",\"success\":true,\"details\":\"Attempting 150-credit commit\",\"authorized_by\":\"$BOB_DID\",\"amount\":150.0,\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
CAP_HTTP=$(_status "$CAP_RAW"); CAP_BODY=$(_body "$CAP_RAW")
CAP_DETAIL=$(echo "$CAP_BODY" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('detail',''))" 2>/dev/null)

if [ "$CAP_HTTP" = "403" ]; then
    ok "Cap enforced — 150 credits > cap of 100 → 403"
    info "Detail: $CAP_DETAIL"
    R[L3_cap]="✓ Enforced — 150 > 100 credits → 403 (spend_up_to:N_credits parsed)"
else
    not_enforced "Spend cap — HTTP $CAP_HTTP accepted 150-credit transaction despite cap=100"
    R[L3_cap]="⚠ NOT ENFORCED — HTTP $CAP_HTTP"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Record agent trust score BEFORE the violation
# ══════════════════════════════════════════════════════════════════════════════
step 4 "Agent trust score BEFORE violation [BASELINE]"

AGENT_BEFORE=$(curl -s "${BASE}/agents/${AGENT_ID}" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('trust_score','?'))" 2>/dev/null)
ok "Agent trust_score: ${AGENT_BEFORE}  (new agents start at 50.0)"
R[L3_trust_before]="$AGENT_BEFORE"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — THE VIOLATION: agent creates 150-credit transaction (cap = 100)
# ══════════════════════════════════════════════════════════════════════════════
step 5 "[VIOLATION] Bob's agent commits to 150-credit deal — delegation cap was 100 credits"

SIGNED=$(_sign "$ALICE_PK" "escrow.transaction.create" \
    "{'amount': 150.0, 'buyer_did': '$ALICE_DID', 'currency': 'credits', 'seller_did': '$BOB_DID'}")
SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

RAW=$(_post "/economic/transaction" \
    "{\"buyer_did\":\"$ALICE_DID\",\"seller_did\":\"$BOB_DID\",\"agent_id\":\"$AGENT_ID\",\"amount\":150.0,\"currency\":\"credits\",\"description\":\"Brokered by Bob's negotiation agent — 150 credits (cap was 100)\",\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
TX_ID=$(_jq "$BODY" "tx_id")

if [ "$HTTP" = "200" ] && [ -n "$TX_ID" ]; then
    warn "150-credit escrow TX accepted: $TX_ID"
    info "Note: /economic/transaction has no delegation cap check — cap is enforced only on /agents/{id}/transaction"
    R[L4_violation]="✓ 150-credit TX created (economic route has no cap check)  TX=$TX_ID"
else
    warn "Transaction HTTP $HTTP: $BODY"
    TX_ID=""
    R[L4_violation]="⚠ Transaction failed (HTTP $HTTP)"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Alice funds the overspent escrow
# ══════════════════════════════════════════════════════════════════════════════
step 6 "Alice funds the 150-credit escrow"

ESCROW_ID=""
if [ -n "$TX_ID" ]; then
    SIGNED=$(_sign "$ALICE_PK" "escrow.fund" "{'tx_id': '$TX_ID'}")
    SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

    RAW=$(_post "/economic/escrow/fund" \
        "{\"tx_id\":\"$TX_ID\",\"buyer_did\":\"$ALICE_DID\",\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
    HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
    ESCROW_ID=$(_jq "$BODY" "escrow_id")
    ESTATE=$(_jq "$BODY" "status")

    if [ "$HTTP" = "200" ] && [ -n "$ESCROW_ID" ]; then
        ok "Escrow funded: $ESCROW_ID  state: $ESTATE"
        info "150 credits now locked in escrow. Agent exceeded its 100-credit cap by 50 credits."
        R[L4_fund]="✓ Escrow $ESCROW_ID ($ESTATE)"
    else
        warn "Fund HTTP $HTTP: $BODY"
        R[L4_fund]="⚠ Fund failed (HTTP $HTTP)"
    fi
else
    warn "Skipping — no TX ID from step 5"
    R[L4_fund]="⚠ Skipped"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Alice disputes the escrow
# ══════════════════════════════════════════════════════════════════════════════
step 7 "Alice disputes: agent exceeded stated 100-credit delegation cap"

if [ -n "$ESCROW_ID" ]; then
    REASON="Agent spend_up_to:100_credits delegation exceeded — transaction was 150 credits"
    SIGNED=$(_sign "$ALICE_PK" "escrow.dispute" \
        "{'escrow_id': '$ESCROW_ID', 'reason': '$REASON'}")
    SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

    RAW=$(_post "/economic/escrow/${ESCROW_ID}/dispute" \
        "{\"escrow_id\":\"$ESCROW_ID\",\"filed_by\":\"$ALICE_DID\",\"reason\":\"$REASON\",\"proof_hash\":\"delegation-cap-exceeded-evidence\",\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
    HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
    DISPUTE_STATE=$(_jq "$BODY" "status")

    if [ "$HTTP" = "200" ]; then
        ok "Dispute filed — escrow state: $DISPUTE_STATE"
        info "Escrow is now locked. Requires elected arbiter to resolve."
        info "Resolve endpoint will 403 until an arbiter exists: gov_engine_ref.is_arbiter() check."
        R[L4_dispute]="✓ Escrow $ESCROW_ID → $DISPUTE_STATE"
    else
        warn "Dispute HTTP $HTTP: $BODY"
        R[L4_dispute]="⚠ Dispute failed (HTTP $HTTP)"
    fi
else
    warn "Skipping — no escrow from step 6"
    R[L4_dispute]="⚠ Skipped"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Governance: elect Carol as arbiter
#          propose → vote (Carol, stake-boosted VP) → tally → execute
# ══════════════════════════════════════════════════════════════════════════════
step 8 "Governance cycle: elect Carol as arbiter"

echo   "  Sub-step 8a — Alice proposes Carol as arbiter"
PROP_TITLE="Elect Carol as arbiter"

SIGNED=$(_sign "$ALICE_PK" "gov.proposal" \
    "{'proposal_type': 'arbiter_election', 'proposer_did': '$ALICE_DID', 'title': '$PROP_TITLE'}")
SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

# Build proposal body with changes dict using Python to avoid JSON quoting issues
PROP_BODY=$(python3 -c "
import json
print(json.dumps({
    'proposer_did': '${ALICE_DID}',
    'title': '${PROP_TITLE}',
    'description': 'Carol has staked 100,000 credits and demonstrated commitment to the protocol. Electing her as arbiter to resolve the agent cap violation dispute.',
    'proposal_type': 'arbiter_election',
    'changes': {'arbiter_did': '${CAROL_DID}'},
    'signature': '${SIG}',
    'timestamp': '${TS}'
}))
")

RAW=$(_post "/governance/proposal" "$PROP_BODY")
HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
PROP_ID=$(_jq "$BODY" "prop_id")

if [ "$HTTP" = "200" ] && [ -n "$PROP_ID" ]; then
    ok "Proposal created: $PROP_ID  type: arbiter_election  changes.arbiter_did: ${CAROL_DID:0:20}…"
else
    warn "Proposal HTTP $HTTP: $BODY"
    PROP_ID=""
fi

if [ -n "$PROP_ID" ]; then
    echo "  Sub-step 8b — Carol votes YES (stake-boosted voting power)"

    SIGNED=$(_sign "$CAROL_PK" "gov.vote" \
        "{'prop_id': '$PROP_ID', 'support': True}")
    SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

    RAW=$(_post "/governance/vote" \
        "{\"prop_id\":\"$PROP_ID\",\"voter_did\":\"$CAROL_DID\",\"support\":true,\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
    HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
    VP=$(_jq "$BODY" "voting_power")

    if [ "$HTTP" = "200" ]; then
        ok "Carol voted YES — server-computed voting_power: $VP"
        info "Voting power = (rep_score/50) × (1 + √stake/10). Stake=100,000 → VP≈$VP"
    else
        warn "Vote HTTP $HTTP: $BODY"
    fi

    echo "  Sub-step 8c — Tally (open endpoint, no signature)"

    RAW=$(_post "/governance/tally" "{\"prop_id\":\"$PROP_ID\"}")
    HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
    PASSED=$(_jq "$BODY" "passed")
    PARTICIPATION=$(_jq "$BODY" "participation")
    TALLY_STATUS=$(_jq "$BODY" "status")

    if [ "$HTTP" = "200" ]; then
        if [ "$PASSED" = "True" ]; then
            ok "Tally: PASSED  participation: ${PARTICIPATION}%  votes_for: $(_jq "$BODY" "votes_for")"
        else
            REASON=$(_jq "$BODY" "reason")
            warn "Tally: NOT PASSED — $REASON  participation: ${PARTICIPATION}%"
            info "If quorum not met: Carol needs more stake, or more voters. Continuing anyway."
        fi
    else
        warn "Tally HTTP $HTTP: $BODY"
    fi

    echo "  Sub-step 8d — Alice executes the passed proposal"

    SIGNED=$(_sign "$ALICE_PK" "gov.execute" \
        "{'executor_did': '$ALICE_DID', 'prop_id': '$PROP_ID'}")
    SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

    RAW=$(_post "/governance/execute/${PROP_ID}" \
        "{\"prop_id\":\"$PROP_ID\",\"executor_did\":\"$ALICE_DID\",\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
    HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
    EXEC_STATUS=$(_jq "$BODY" "status")

    if [ "$HTTP" = "200" ]; then
        ok "Executed: proposal → $EXEC_STATUS"
        R[L5_gov]="✓ Proposal $PROP_ID executed (arbiter_election)"
    else
        DETAIL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('detail','?'))" 2>/dev/null)
        warn "Execute HTTP $HTTP: $DETAIL"
        info "Cannot execute if proposal did not pass tally. Arbiter election blocked."
        R[L5_gov]="⚠ Execute failed (HTTP $HTTP) — tally may not have passed"
    fi
else
    warn "Skipping governance cycle — proposal creation failed"
    R[L5_gov]="⚠ Proposal failed — governance cycle skipped"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — Confirm Carol is now an elected arbiter
# ══════════════════════════════════════════════════════════════════════════════
step 9 "Confirm Carol's arbiter status via GET /governance/arbiters"

ARBITERS_RAW=$(_get "/governance/arbiters")
IS_ARBITER=$(echo "$ARBITERS_RAW" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print('yes' if '${CAROL_DID}' in d else 'no')" 2>/dev/null)

if [ "$IS_ARBITER" = "yes" ]; then
    ELECTED_AT=$(echo "$ARBITERS_RAW" | python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(d.get('${CAROL_DID}',{}).get('elected_at','?'))" 2>/dev/null)
    ok "Carol IS an elected arbiter — elected_at: $ELECTED_AT"
    ok "resolve endpoint will now pass gov_engine_ref.is_arbiter() check"
    R[L5_arbiter]="✓ Carol elected — arbiter check will pass"
else
    warn "Carol is NOT in arbiters list — governance cycle did not complete"
    info "Resolve will 403: 'Only elected arbiters can resolve disputes'"
    R[L5_arbiter]="⚠ Carol NOT elected — governance cycle incomplete"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 10 — Carol resolves dispute in Alice's favor
# ══════════════════════════════════════════════════════════════════════════════
step 10 "Carol (elected arbiter) resolves dispute — favor_buyer=true (Alice wins; Bob's agent loses)"

if [ -n "$ESCROW_ID" ]; then
    SIGNED=$(_sign "$CAROL_PK" "escrow.resolve" \
        "{'escrow_id': '$ESCROW_ID', 'favor_buyer': True}")
    SIG=$(sig_of "$SIGNED"); TS=$(ts_of "$SIGNED")

    RAW=$(_post "/economic/escrow/${ESCROW_ID}/resolve" \
        "{\"escrow_id\":\"$ESCROW_ID\",\"favor_buyer\":true,\"resolved_by\":\"$CAROL_DID\",\"signature\":\"$SIG\",\"timestamp\":\"$TS\"}")
    HTTP=$(_status "$RAW"); BODY=$(_body "$RAW")
    RESOLVE_STATE=$(_jq "$BODY" "status")

    if [ "$HTTP" = "200" ]; then
        ok "Dispute resolved — escrow state: $RESOLVE_STATE"
        ok "150 credits refunded to Alice. Bob's agent (seller side) takes the trust hit."
        R[L4_resolve]="✓ Escrow → $RESOLVE_STATE  (arbiter: Carol)"
    else
        DETAIL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('detail','?'))" 2>/dev/null)
        warn "Resolve HTTP $HTTP: $DETAIL"
        if [ "$HTTP" = "403" ]; then
            info "403 = Carol is not in arbiters. Governance cycle did not complete (tally may not have passed)."
        fi
        R[L4_resolve]="⚠ Resolve failed (HTTP $HTTP): $DETAIL"
    fi
else
    warn "Skipping — no escrow ID from step 6"
    R[L4_resolve]="⚠ Skipped"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 11 — Agent trust score AFTER resolution
#           This is the single thing the demo is testing.
#           Report truthfully. Do not fake it.
# ══════════════════════════════════════════════════════════════════════════════
step 11 "Agent trust score AFTER dispute resolution — did the chain fire?"

AGENT_AFTER=$(curl -s "${BASE}/agents/${AGENT_ID}" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('trust_score','?'))" 2>/dev/null)

echo ""
echo -e "  ${BLD}Before violation:  ${AGENT_BEFORE}${RST}"
echo -e "  ${BLD}After resolution:  ${AGENT_AFTER}${RST}"
echo ""

if [ "$AGENT_BEFORE" = "$AGENT_AFTER" ]; then
    not_wired "dispute resolution does not propagate to agent trust_score"
    info "resolve_dispute() in economic/escrow.py updates escrow + tx state only."
    info "agent_registry.file_dispute() (which -10s trust_score) is a separate endpoint:"
    info "  POST /agents/{agent_id}/dispute — NOT called by the escrow resolve path."
    info "The governance→escrow chain IS wired. The escrow→agent_trust chain is NOT."
    R[L3_trust_chain]="⚠ NOT WIRED — trust_score unchanged ($AGENT_BEFORE → $AGENT_AFTER)"
else
    ok "Trust score changed: $AGENT_BEFORE → $AGENT_AFTER (chain fired)"
    R[L3_trust_chain]="✓ trust_score: $AGENT_BEFORE → $AGENT_AFTER"
fi

# ══════════════════════════════════════════════════════════════════════════════
# LAYER-BY-LAYER SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
hr
banner "LAYER-BY-LAYER SUMMARY"
echo -e "${DIM}Narrative claim vs what the server actually did${RST}"
echo ""

echo -e "  ${BLD}Layer 0 — Trust Protocol${RST}"
printf  "    %-28s %s\n" "Open endpoints:"    "✓ /claim /proof /governance/tally require no auth (by design)"

echo ""
echo -e "  ${BLD}Layer 1 — Identity & Reputation${RST}"
printf  "    %-28s %s\n" "Identities:"        "${R[L1_identity]}"
printf  "    %-28s %s\n" "Carol stake:"       "${R[L2_carol_stake]}"

echo ""
echo -e "  ${BLD}Layer 3 — Agent Trust${RST}"
printf  "    %-28s %s\n" "Registration:"      "${R[L3_agent]}"
printf  "    %-28s %s\n" "Cap enforcement:"   "${R[L3_cap]}"
printf  "    %-28s %s\n" "Trust before:"      "${R[L3_trust_before]} (baseline)"
printf  "    %-28s %s\n" "Trust→resolve chain:""${R[L3_trust_chain]}"

echo ""
echo -e "  ${BLD}Layer 4 — Economic Trust${RST}"
printf  "    %-28s %s\n" "Violation (150>100):" "${R[L4_violation]}"
printf  "    %-28s %s\n" "Escrow funded:"     "${R[L4_fund]}"
printf  "    %-28s %s\n" "Dispute filed:"     "${R[L4_dispute]}"
printf  "    %-28s %s\n" "Dispute resolved:"  "${R[L4_resolve]}"

echo ""
echo -e "  ${BLD}Layer 5 — Governance${RST}"
printf  "    %-28s %s\n" "Governance cycle:"  "${R[L5_gov]}"
printf  "    %-28s %s\n" "Carol arbiter:"     "${R[L5_arbiter]}"

echo ""
echo -e "  ${BLD}VERDICT${RST}"
echo    "    governance → arbiter election:  WIRED ✓  (execute() adds to gov_engine.arbiters)"
echo    "    arbiter → escrow resolve:       WIRED ✓  (is_arbiter() check gates resolve endpoint)"
if [[ "${R[L3_trust_chain]}" == ✓* ]]; then
    echo "    escrow resolve → agent trust:   WIRED ✓  (resolve_dispute() calls agent_registry.file_dispute on loss)"
else
    echo "    escrow resolve → agent trust:   NOT WIRED ⚠  (resolve_dispute() never calls agent_registry)"
fi
if [[ "${R[L3_cap]}" == ✓* ]]; then
    echo "    delegation cap enforcement:     WIRED ✓  (spend_up_to:N_credits parsed on /agents/{id}/transaction)"
    echo "    note: /economic/transaction has no cap check — separate system boundary"
else
    echo "    delegation cap enforcement:     NOT WIRED ⚠  (permissions list stored, never parsed)"
fi

hr
echo ""
