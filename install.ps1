# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — standalone installer (Windows PowerShell)
#
# Provisions Ollama + models, a Python venv, dependencies, runtime dirs, .env.
#
# Usage (from an elevated-enough PowerShell):
#   .\install.ps1            # default "mac_mini" model profile
#   .\install.ps1 -Server    # large "server" profile models
# ─────────────────────────────────────────────────────────────────────────
param([switch]$Server)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$ollamaUrl = "http://localhost:11434"

# Default model profile = "mac_mini" (matches config/default_config.yaml).
$models = @("qwen3:14b", "llama3.1:8b", "gemma3:12b", "qwen3:8b")
if ($Server) {
  $models = @("kimi-k2-thinking", "gemma2:27b", "qwen2.5:32b", "phi4:14b", "qwen3:14b")
  Write-Host "[install] Using SERVER model profile (large models)." -ForegroundColor Yellow
}

function Log($m)  { Write-Host "[install] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[install] $m" -ForegroundColor Yellow }

# ── 1. Python ──
$python = $null
foreach ($c in @("python3.12", "python3.11", "python3.10", "python", "py")) {
  $cmd = Get-Command $c -ErrorAction SilentlyContinue
  if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) { throw "Python 3.10+ not found. Install from https://www.python.org/downloads/ and re-run." }
Log "Using Python: $python ($(& $python --version 2>&1))"

# ── 2. Ollama ──
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Log "Ollama not found — installing…"
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
  } else {
    Warn "winget unavailable. Download and install Ollama from https://ollama.com/download, then re-run."
    throw "Ollama not installed."
  }
} else {
  Log "Ollama present: $(ollama --version 2>&1 | Select-Object -First 1)"
}

# ── 3. Start the Ollama server if not serving ──
try { Invoke-WebRequest -UseBasicParsing "$ollamaUrl/api/tags" -TimeoutSec 3 | Out-Null }
catch {
  Log "Starting Ollama server…"
  Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve"
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-WebRequest -UseBasicParsing "$ollamaUrl/api/tags" -TimeoutSec 3 | Out-Null; break } catch {}
  }
}

# ── 4. Pull models ──
Log "Pulling $($models.Count) model(s) — several GB each…"
foreach ($m in $models) {
  Log "  -> ollama pull $m"
  try { ollama pull $m } catch { Warn "Failed to pull $m — retry later with: ollama pull $m" }
}

# ── 5. venv + deps ──
if (-not (Test-Path ".venv")) {
  Log "Creating virtualenv at .venv"
  & $python -m venv .venv
}
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Log "Installing Python dependencies"
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r requirements.txt

# ── 6. Runtime dirs + .env ──
Log "Creating runtime directories"
foreach ($d in @("results\json","results\csv","results\jobs","results\annotations","results\research","results\atomic_pub_cache","logs")) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Log "Created .env from .env.example" }

Log "Install complete. Start the API with:  .\run.ps1"
