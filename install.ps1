# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — standalone installer (Windows PowerShell)
#
# Checks prerequisites, warns about disk/RAM limits before pulling models,
# installs Ollama + models, builds a venv, installs deps, prepares runtime.
#
# Usage:
#   .\install.ps1                 # default "mac_mini" profile
#   .\install.ps1 -Server         # large "server" profile
#   .\install.ps1 -SkipModels
# ─────────────────────────────────────────────────────────────────────────
param([switch]$Server, [switch]$SkipModels)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$ollamaHost = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST } else { "localhost" }
$ollamaPort = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { "11434" }
$ollamaUrl  = "http://${ollamaHost}:${ollamaPort}"

if ($Server) { $models = @("kimi-k2-thinking","gemma2:27b","qwen2.5:32b","phi4:14b","qwen3:14b"); $estGb = 160; $minRamGb = 240; $profile = "server" }
else         { $models = @("qwen3:14b","llama3.1:8b","gemma3:12b","qwen3:8b");                    $estGb = 30;  $minRamGb = 16;  $profile = "mac_mini" }

function Log($m)  { Write-Host "[install] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[install] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[warn]  $m"   -ForegroundColor Yellow }
$script:warnings = 0
function Bump { $script:warnings++ }

Log "Preflight checks (profile: $profile)…"

# Python 3.10+
$python = $null
foreach ($c in @("python3.12","python3.11","python3.10","python","py")) {
  $cmd = Get-Command $c -ErrorAction SilentlyContinue
  if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) { throw "Python 3.10+ not found. Install from https://www.python.org/downloads/ and re-run." }
$pyv = (& $python -c "import sys;print('%d.%d'%sys.version_info[:2])")
if ((& $python -c "import sys;print(1 if sys.version_info[:2]>=(3,10) else 0)") -ne "1") { throw "Python $pyv too old (need 3.10+)." }
Ok "Python $pyv at $python"

# git / curl-equivalent
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Warn "git not found — version diagnostics will read 'unknown' (non-fatal)." }

# RAM
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($ramGb -lt $minRamGb) { Warn "Detected $ramGb GB RAM; '$profile' expects ~$minRamGb GB. Models may run slowly or fail to load."; Bump }
else { Ok "RAM: $ramGb GB (meets ~$minRamGb GB target)" }

# Disk (free space on the drive holding the user profile / .ollama)
$drive = (Get-Item $env:USERPROFILE).PSDrive
$freeGb = [math]::Round($drive.Free / 1GB)
$needGb = $estGb + 5
if ($freeGb -lt $needGb) { Warn "Only $freeGb GB free on $($drive.Name): drive; '$profile' models need ~$estGb GB (recommend >=$needGb GB)."; Bump }
else { Ok "Disk: $freeGb GB free (need ~$estGb GB)" }

# Network (best-effort)
try { Invoke-WebRequest -UseBasicParsing "https://ollama.com" -TimeoutSec 6 | Out-Null }
catch { Warn "Couldn't reach ollama.com — installation/model pulls need internet." }

# Ollama
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Log "Ollama not found — installing…"
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
  } else { throw "winget unavailable. Install Ollama from https://ollama.com/download and re-run." }
} else { Ok "Ollama present: $(ollama --version 2>&1 | Select-Object -First 1)" }

# Start server if not reachable
$ollamaUp = $false
try { Invoke-WebRequest -UseBasicParsing "$ollamaUrl/api/tags" -TimeoutSec 3 | Out-Null; $ollamaUp = $true } catch {
  Log "Starting Ollama server…"
  Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve"
  for ($i=0; $i -lt 30; $i++) { Start-Sleep 1; try { Invoke-WebRequest -UseBasicParsing "$ollamaUrl/api/tags" -TimeoutSec 3 | Out-Null; $ollamaUp = $true; break } catch {} }
}
if ($ollamaUp) { Ok "Ollama reachable at $ollamaUrl" } else { Warn "Ollama not reachable at $ollamaUrl — pull models manually later."; Bump }

# Models
if ($SkipModels) { Warn "-SkipModels set; pull later: $($models -join ', ')" }
elseif ($ollamaUp) {
  Log "Pulling $($models.Count) model(s) for '$profile' (~$estGb GB total)…"
  foreach ($m in $models) { Log "  -> ollama pull $m"; try { ollama pull $m } catch { Warn "Failed to pull $m — retry: ollama pull $m"; Bump } }
} else { Warn "Skipping model pulls (Ollama unreachable)." }

# venv + deps
if (-not (Test-Path ".venv")) { Log "Creating virtualenv at .venv"; & $python -m venv .venv }
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Log "Installing Python dependencies"
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r requirements.txt

# runtime dirs + .env
foreach ($d in @("results\json","results\csv","results\jobs","results\annotations","results\research","results\atomic_pub_cache","logs")) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Ok "Created .env from .env.example" }

Write-Host ""
if ($script:warnings -gt 0) { Warn "Install finished with $($script:warnings) warning(s) above — review them." }
else { Ok "Install complete with no warnings." }
Write-Host "  Start the API:  .\run.ps1   (auto-selects a free port)"
Write-Host "  Docs / usage:   see README.md"
