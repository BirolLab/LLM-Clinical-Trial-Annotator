"""
Application configuration - loads from .env and environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the repo root. All keys are optional / free-tier.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# --- Server ---
AGENT_ANNOTATE_PORT = int(os.getenv("AGENT_ANNOTATE_PORT", "9005"))

# --- Ollama ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "600"))

# --- External API keys (optional, all free-tier) ---
# NCBI E-utilities key (free registration at ncbi.nlm.nih.gov) — raises rate limit from 3/sec to 10/sec
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
# v31: OpenAlex polite pool (email only, no key needed) — 10 req/sec
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "")
# v31: CrossRef polite pool (email in User-Agent) — faster than anonymous
CROSSREF_EMAIL = os.getenv("CROSSREF_EMAIL", "")

# --- CORS ---
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:9005"
).split(",")

# --- Paths ---
CONFIG_DIR = _PROJECT_ROOT / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "default_config.yaml"
RESULTS_DIR = _PROJECT_ROOT / "results"
LOGS_DIR = _PROJECT_ROOT / "logs"
FRONTEND_DIR = _PROJECT_ROOT / "app" / "static" / "spa"

# Ensure output directories exist
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
