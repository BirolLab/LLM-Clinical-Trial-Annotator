#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — standalone installer (macOS / Linux)
#
# Designed to be foolproof on a fresh host: it checks every prerequisite,
# warns about disk/RAM limits BEFORE pulling multi-GB models, installs and
# starts Ollama, pulls the right models for your hardware, builds a Python
# virtualenv, installs dependencies, and prepares runtime dirs + .env.
#
# Usage:
#   ./install.sh                       # default "mac_mini" profile (16–24 GB RAM)
#   ./install.sh --server              # large "server" profile (240+ GB RAM)
#   ./install.sh --skip-models         # do everything except pulling models
#   PYTHON_BIN=/path/python3.12 ./install.sh
# ─────────────────────────────────────────────────────────────────────────
set -uo pipefail   # not -e: we want to warn-and-continue, not hard-abort on soft checks

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$REPO_ROOT"

OLLAMA_HOST_VAL="${OLLAMA_HOST:-localhost}"
OLLAMA_PORT_VAL="${OLLAMA_PORT:-11434}"
OLLAMA_URL="http://${OLLAMA_HOST_VAL}:${OLLAMA_PORT_VAL}"

PROFILE="mac_mini"; SKIP_MODELS=0
for a in "$@"; do
  case "$a" in
    --server|server) PROFILE="server" ;;
    --skip-models)   SKIP_MODELS=1 ;;
    *) ;;
  esac
done

# Models per profile + a rough on-disk size estimate (GB) for the disk warning.
if [ "$PROFILE" = "server" ]; then
  MODELS=(kimi-k2-thinking gemma2:27b qwen2.5:32b phi4:14b qwen3:14b)
  EST_MODEL_GB=160; MIN_RAM_GB=240
else
  MODELS=(qwen3:14b llama3.1:8b gemma3:12b qwen3:8b)
  EST_MODEL_GB=30;  MIN_RAM_GB=16
fi

c_log()  { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }
c_ok()   { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
c_warn() { printf '\033[1;33m[warn]\033[0m  %s\n' "$*"; }
c_err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }
have()   { command -v "$1" >/dev/null 2>&1; }

OS="$(uname -s)"
WARNINGS=0

# ── PREFLIGHT ────────────────────────────────────────────────────────────
c_log "Preflight checks (OS: $OS, profile: $PROFILE)…"

# Python 3.10+
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  for c in python3.12 python3.11 python3.10 python3 python; do
    have "$c" && { PYTHON_BIN="$(command -v "$c")"; break; }
  done
fi
if [ -z "$PYTHON_BIN" ]; then
  c_err "Python 3.10+ not found. Install it (https://www.python.org/downloads/) and re-run."
  exit 1
fi
PYV="$("$PYTHON_BIN" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"
if ! "$PYTHON_BIN" -c 'import sys;sys.exit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
  c_err "Python $PYV is too old (need 3.10+). Set PYTHON_BIN to a newer interpreter."
  exit 1
fi
c_ok "Python $PYV at $PYTHON_BIN"
"$PYTHON_BIN" -m venv --help >/dev/null 2>&1 || { c_err "Python 'venv' module missing (install python3-venv)."; exit 1; }
"$PYTHON_BIN" -m ensurepip --version >/dev/null 2>&1 || c_warn "pip/ensurepip not detected; venv creation may need python3-pip."

# git / curl (curl is required to install Ollama)
have git  || c_warn "git not found — version diagnostics will read 'unknown' (non-fatal)."
have curl || { c_err "curl not found — required to install Ollama and to health-check. Install curl and re-run."; exit 1; }

# RAM check
RAM_GB=0
if [ "$OS" = "Darwin" ]; then
  RAM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 / 1024 / 1024 ))
elif [ -r /proc/meminfo ]; then
  RAM_GB=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0) / 1024 / 1024 ))
fi
if [ "$RAM_GB" -gt 0 ]; then
  if [ "$RAM_GB" -lt "$MIN_RAM_GB" ]; then
    c_warn "Detected ${RAM_GB} GB RAM; the '$PROFILE' profile expects ~${MIN_RAM_GB} GB. Models may run slowly, swap heavily, or fail to load. Consider the default profile or smaller models."
    WARNINGS=$((WARNINGS+1))
  else
    c_ok "RAM: ${RAM_GB} GB (meets ~${MIN_RAM_GB} GB target)"
  fi
else
  c_warn "Could not detect system RAM — ensure you have ~${MIN_RAM_GB} GB for the '$PROFILE' profile."
fi

# Disk check (free space where models live: ~/.ollama, falls back to repo dir)
MODEL_STORE="${OLLAMA_MODELS:-$HOME/.ollama}"
[ -d "$MODEL_STORE" ] || MODEL_STORE="$HOME"
FREE_GB=$(df -Pg "$MODEL_STORE" 2>/dev/null | awk 'NR==2{print $4+0}')
[ -z "$FREE_GB" ] && FREE_GB=$(( $(df -Pk "$MODEL_STORE" 2>/dev/null | awk 'NR==2{print $4+0}') / 1024 / 1024 ))
if [ "${FREE_GB:-0}" -gt 0 ]; then
  NEED_GB=$(( EST_MODEL_GB + 5 ))
  if [ "$FREE_GB" -lt "$NEED_GB" ]; then
    c_warn "Only ${FREE_GB} GB free on $MODEL_STORE; the '$PROFILE' models need ~${EST_MODEL_GB} GB (recommend ≥${NEED_GB} GB free). Pulls may fail. Free space, or set OLLAMA_MODELS to a larger volume."
    WARNINGS=$((WARNINGS+1))
  else
    c_ok "Disk: ${FREE_GB} GB free on $MODEL_STORE (need ~${EST_MODEL_GB} GB)"
  fi
else
  c_warn "Could not measure free disk space on $MODEL_STORE — ensure ~${EST_MODEL_GB} GB is available."
fi

# Network reachability (best-effort; only warns)
if ! curl -sf --max-time 6 https://ollama.com >/dev/null 2>&1; then
  c_warn "Couldn't reach ollama.com — if Ollama isn't already installed, installation/model pulls will fail without internet."
fi

# ── OLLAMA ───────────────────────────────────────────────────────────────
if ! have ollama; then
  c_log "Ollama not found — installing via official script…"
  if curl -fsSL https://ollama.com/install.sh | sh; then c_ok "Ollama installed."
  else c_err "Ollama install failed. Install manually from https://ollama.com/download and re-run."; exit 1; fi
else
  c_ok "Ollama present: $(ollama --version 2>&1 | head -1)"
fi

# Start server if not reachable
if ! curl -sf --max-time 4 "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  c_log "Starting Ollama server…"
  (ollama serve >/dev/null 2>&1 &) || true
  for _ in $(seq 1 30); do curl -sf --max-time 3 "${OLLAMA_URL}/api/tags" >/dev/null 2>&1 && break; sleep 1; done
fi
if curl -sf --max-time 4 "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  c_ok "Ollama server reachable at ${OLLAMA_URL}"
else
  c_warn "Ollama not reachable at ${OLLAMA_URL}. Start it (\`ollama serve\`) and pull models manually; the API still installs."
  WARNINGS=$((WARNINGS+1))
fi

# ── MODELS ───────────────────────────────────────────────────────────────
if [ "$SKIP_MODELS" -eq 1 ]; then
  c_warn "--skip-models set; not pulling models. Pull later: ${MODELS[*]}"
elif curl -sf --max-time 4 "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  c_log "Pulling ${#MODELS[@]} model(s) for '$PROFILE' (~${EST_MODEL_GB} GB total). Cached models verify instantly…"
  for m in "${MODELS[@]}"; do
    c_log "  → ollama pull $m"
    ollama pull "$m" || { c_warn "Failed to pull $m — retry later: ollama pull $m"; WARNINGS=$((WARNINGS+1)); }
  done
else
  c_warn "Skipping model pulls (Ollama unreachable). Pull later: ${MODELS[*]}"
fi

# ── PYTHON ENV + DEPS ────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  c_log "Creating virtualenv at .venv"
  "$PYTHON_BIN" -m venv .venv || { c_err "venv creation failed."; exit 1; }
fi
# shellcheck disable=SC1091
. .venv/bin/activate
c_log "Installing Python dependencies"
python -m pip install --upgrade pip >/dev/null 2>&1 || c_warn "pip upgrade failed (continuing)."
if ! python -m pip install -r requirements.txt; then
  c_err "Dependency install failed. If you're on Python 3.13/3.14, try Python 3.11/3.12: PYTHON_BIN=\$(command -v python3.12) ./install.sh"
  exit 1
fi
c_ok "Dependencies installed."

# ── RUNTIME DIRS + .env ──────────────────────────────────────────────────
c_log "Creating runtime directories"
mkdir -p results/json results/csv results/jobs results/annotations \
         results/research results/atomic_pub_cache logs
[ -f .env ] || { cp .env.example .env; c_ok "Created .env from .env.example"; }

# ── DONE ─────────────────────────────────────────────────────────────────
echo
if [ "$WARNINGS" -gt 0 ]; then
  c_warn "Install finished with ${WARNINGS} warning(s) above — review them; the API may still run."
else
  c_ok "✅ Install complete with no warnings."
fi
echo
echo "  Start the API:   ./run.sh         (auto-selects a free port and prints the URL)"
echo "  Docs / usage:    see README.md"
