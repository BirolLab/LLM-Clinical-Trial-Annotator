#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — start the standalone API (macOS / Linux).
#
# Foolproof startup: runs from the repo root, checks the venv + Ollama, and
# AUTO-SELECTS the first free port (so it never collides with another service).
#
# Usage:
#   ./run.sh                  # auto-picks a free port starting at 9005
#   PORT=8080 ./run.sh        # force a port (errors if it's busy)
#   HOST=0.0.0.0 ./run.sh     # bind all interfaces
# ─────────────────────────────────────────────────────────────────────────
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$REPO_ROOT"

c_warn() { printf '\033[1;33m[run]\033[0m %s\n' "$*"; }
c_err()  { printf '\033[1;31m[run]\033[0m %s\n' "$*" >&2; }

# Need the venv (created by install.sh).
if [ ! -x .venv/bin/python ]; then
  c_err "No virtualenv found. Run ./install.sh first."
  exit 1
fi
# shellcheck disable=SC1091
. .venv/bin/activate
PYBIN="$REPO_ROOT/.venv/bin/python"

HOST="${HOST:-127.0.0.1}"
PORT_BASE="${PORT:-9005}"

# Is a TCP port free to bind? (portable: uses the venv Python, no lsof/nc needed)
port_free() { "$PYBIN" - "$HOST" "$1" <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((host, port)); s.close(); sys.exit(0)
except OSError:
    sys.exit(1)
PY
}

if [ -n "${PORT:-}" ]; then
  # User pinned a port — require it to be free.
  if ! port_free "$PORT"; then c_err "Port $PORT is already in use. Pick another or unset PORT to auto-select."; exit 1; fi
  PORT_SEL="$PORT"
else
  # Auto-select: scan upward from the base for the first free port.
  PORT_SEL=""
  for p in $(seq "$PORT_BASE" $((PORT_BASE+200))); do
    if port_free "$p"; then PORT_SEL="$p"; break; fi
  done
  if [ -z "$PORT_SEL" ]; then c_err "No free port found in ${PORT_BASE}–$((PORT_BASE+200))."; exit 1; fi
  [ "$PORT_SEL" != "$PORT_BASE" ] && c_warn "Port $PORT_BASE busy — using $PORT_SEL instead."
fi

# Soft check: Ollama up? (API still boots without it; jobs need it.)
OLLAMA_URL="http://${OLLAMA_HOST:-localhost}:${OLLAMA_PORT:-11434}"
if command -v curl >/dev/null 2>&1 && ! curl -sf --max-time 3 "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  c_warn "Ollama not reachable at ${OLLAMA_URL} — the API will start but annotation jobs will fail until Ollama is running (\`ollama serve\`)."
fi

echo "[run] Agent Annotate API → http://${HOST}:${PORT_SEL}   (docs: /docs · health: /api/health · Ctrl-C to stop)"
exec uvicorn app.main:app --host "$HOST" --port "$PORT_SEL"
