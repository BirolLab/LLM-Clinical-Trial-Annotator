#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — standalone installer (macOS / Linux)
#
# Provisions everything needed to run the annotation API on a fresh host:
#   1. locates a suitable Python (3.10+)
#   2. installs Ollama (if missing) and starts its server
#   3. pulls the LLM models the pipeline calls
#   4. creates a Python virtualenv and installs dependencies
#   5. creates runtime directories and a .env
#
# Usage:
#   ./install.sh            # default "mac_mini" model profile (16–24 GB RAM)
#   ./install.sh --server   # large "server" profile models (240+ GB RAM)
#   PYTHON_BIN=/path/python3.12 ./install.sh   # force a specific interpreter
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$REPO_ROOT"

OLLAMA_HOST_URL="http://${OLLAMA_HOST:-localhost}:${OLLAMA_PORT:-11434}"

# Default model profile = "mac_mini" (matches config/default_config.yaml).
MODELS=(qwen3:14b llama3.1:8b gemma3:12b qwen3:8b)
if [ "${1:-}" = "--server" ] || [ "${1:-}" = "server" ]; then
  # "server" hardware_profile: premium reasoning model + larger verifiers.
  MODELS=(kimi-k2-thinking gemma2:27b qwen2.5:32b phi4:14b qwen3:14b)
  echo "[install] Using SERVER model profile (large models — needs lots of RAM/VRAM)."
fi

c_log()  { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }
c_warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*"; }
c_err()  { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; }

# ── 1. Python ────────────────────────────────────────────────────────────
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then PYTHON_BIN="$(command -v "$c")"; break; fi
  done
fi
if [ -z "$PYTHON_BIN" ]; then
  c_err "Python 3.10+ not found. Install Python (https://www.python.org/downloads/) and re-run."
  exit 1
fi
c_log "Using Python: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"

# ── 2. Ollama ────────────────────────────────────────────────────────────
if ! command -v ollama >/dev/null 2>&1; then
  c_log "Ollama not found — installing via official script…"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    c_err "curl is required to install Ollama. Install Ollama manually: https://ollama.com/download"
    exit 1
  fi
else
  c_log "Ollama present: $(ollama --version 2>&1 | head -1)"
fi

# ── 3. Start the Ollama server (if not already serving) ──────────────────
if ! curl -sf "${OLLAMA_HOST_URL}/api/tags" >/dev/null 2>&1; then
  c_log "Starting Ollama server in the background…"
  (ollama serve >/dev/null 2>&1 &) || true
  for _ in $(seq 1 30); do
    curl -sf "${OLLAMA_HOST_URL}/api/tags" >/dev/null 2>&1 && break
    sleep 1
  done
fi
if curl -sf "${OLLAMA_HOST_URL}/api/tags" >/dev/null 2>&1; then
  c_log "Ollama server reachable at ${OLLAMA_HOST_URL}."
else
  c_warn "Ollama not reachable at ${OLLAMA_HOST_URL}. Start it with 'ollama serve', then pull models manually."
fi

# ── 4. Pull models ───────────────────────────────────────────────────────
c_log "Pulling ${#MODELS[@]} model(s). This can take a while (several GB each)…"
for m in "${MODELS[@]}"; do
  c_log "  → ollama pull $m"
  ollama pull "$m" || c_warn "Failed to pull $m — retry later with: ollama pull $m"
done

# ── 5. Python venv + dependencies ────────────────────────────────────────
if [ ! -d ".venv" ]; then
  c_log "Creating virtualenv at .venv"
  "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
c_log "Installing Python dependencies"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

# ── 6. Runtime directories + .env ────────────────────────────────────────
c_log "Creating runtime directories"
mkdir -p results/json results/csv results/jobs results/annotations \
         results/research results/atomic_pub_cache logs
if [ ! -f .env ]; then
  cp .env.example .env
  c_log "Created .env from .env.example"
fi

c_log "✅ Install complete."
echo
echo "  Start the API:   ./run.sh"
echo "  Health check:    curl http://127.0.0.1:9005/api/health"
echo "  Docs / usage:    see README.md"
