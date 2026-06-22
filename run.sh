#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — start the standalone API (macOS / Linux).
# Always runs from the repo root so app/, agents/, config/ import correctly.
#
# Usage:
#   ./run.sh                     # binds 127.0.0.1:9005
#   HOST=0.0.0.0 PORT=8080 ./run.sh
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$REPO_ROOT"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-9005}"

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

if ! curl -sf "http://${OLLAMA_HOST:-localhost}:${OLLAMA_PORT:-11434}/api/tags" >/dev/null 2>&1; then
  printf '\033[1;33m[run]\033[0m Ollama not reachable — the API will start but annotation jobs will fail until Ollama is running.\n'
fi

echo "[run] Agent Annotate API → http://${HOST}:${PORT}  (Ctrl-C to stop)"
exec uvicorn app.main:app --host "$HOST" --port "$PORT"
