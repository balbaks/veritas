#!/usr/bin/env bash
# scripts/record_demo.sh — Non-interactive asciinema recording of the VERITAS demo.
#
# Usage: bash scripts/record_demo.sh
# Output: veritas-demo.cast (replay or upload with asciinema)
#
# Runs demo.sh non-interactively via asciinema -c so no manual exit is needed.

VERITAS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CAST_FILE="$VERITAS_ROOT/veritas-demo.cast"
UVICORN="$VERITAS_ROOT/venv/bin/uvicorn"
[ ! -x "$UVICORN" ] && UVICORN="uvicorn"

# ── check asciinema ───────────────────────────────────────────────────────────
if ! command -v asciinema &>/dev/null; then
    echo ""
    echo "asciinema is not installed. Install it with one of:"
    echo "  sudo apt install asciinema"
    echo "  pipx install asciinema"
    echo ""
    echo "Falling back to plain log capture (text only, no replay)..."
    bash "$VERITAS_ROOT/scripts/demo.sh" 2>&1 | tee "$VERITAS_ROOT/veritas-demo.log"
    echo ""
    echo "Log saved to: $VERITAS_ROOT/veritas-demo.log"
    echo "Paste its contents anywhere — install asciinema for a shareable recording."
    exit 0
fi

# ── step 1: clear port ────────────────────────────────────────────────────────
echo "→ Killing anything on :8000..."
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

# ── step 2: clean database ────────────────────────────────────────────────────
echo "→ Removing existing veritas.db..."
rm -f "$VERITAS_ROOT/veritas.db"

# ── step 3: start fresh server ────────────────────────────────────────────────
echo "→ Starting server..."
cd "$VERITAS_ROOT"
"$UVICORN" api.server:app --port 8000 --log-level warning &
SERVER_PID=$!
sleep 2
echo "  Server PID: $SERVER_PID"

# ── step 4: record ────────────────────────────────────────────────────────────
# demo.sh manages its own server lifecycle (preflight kills :8000 and restarts).
# $SERVER_PID is intentionally stale after demo.sh's preflight — cleanup uses
# fuser rather than kill $SERVER_PID to target whatever demo.sh left running.
echo ""
echo "→ Recording (exits automatically when demo.sh finishes)..."
asciinema rec \
    --overwrite \
    --quiet \
    -c "bash $VERITAS_ROOT/scripts/demo.sh" \
    --title "VERITAS v1.2.0 — Violation-and-Resolution Demo" \
    --cols 120 \
    --rows 40 \
    --env "" \
    "$CAST_FILE"

# ── step 5: stop server ───────────────────────────────────────────────────────
echo ""
echo "→ Stopping server..."
fuser -k 8000/tcp 2>/dev/null || true

# ── report ────────────────────────────────────────────────────────────────────
if [ ! -f "$CAST_FILE" ]; then
    echo "ERROR: $CAST_FILE not found — recording may have failed."
    exit 1
fi

SIZE=$(du -h "$CAST_FILE" | cut -f1)

echo ""
echo "Recording complete."
echo ""
echo "  File:  $CAST_FILE"
echo "  Size:  $SIZE"
echo ""
echo "Replay locally:"
echo "  asciinema play $CAST_FILE"
echo ""
echo "Upload for a shareable link:"
echo "  asciinema upload $CAST_FILE"
