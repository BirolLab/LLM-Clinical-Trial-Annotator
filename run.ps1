# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — start the standalone API (Windows PowerShell).
# Auto-selects the first free port so it never collides with another service.
#
# Usage:
#   .\run.ps1                     # auto-picks a free port starting at 9005
#   $env:PORT="8080"; .\run.ps1   # force a port (errors if busy)
#   $env:HOST="0.0.0.0"; .\run.ps1
# ─────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) { Write-Error "No virtualenv found. Run .\install.ps1 first."; exit 1 }
. .\.venv\Scripts\Activate.ps1

$bindHost = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$portBase = if ($env:PORT) { [int]$env:PORT } else { 9005 }

function Test-PortFree([int]$p) {
  try {
    $ipAny = if ($bindHost -eq "0.0.0.0") { [System.Net.IPAddress]::Any } else { [System.Net.IPAddress]::Parse($bindHost) }
    $l = New-Object System.Net.Sockets.TcpListener($ipAny, $p)
    $l.Start(); $l.Stop(); return $true
  } catch { return $false }
}

if ($env:PORT) {
  if (-not (Test-PortFree $portBase)) { Write-Error "Port $portBase is in use. Pick another or unset PORT to auto-select."; exit 1 }
  $portSel = $portBase
} else {
  $portSel = $null
  for ($p = $portBase; $p -le $portBase + 200; $p++) { if (Test-PortFree $p) { $portSel = $p; break } }
  if (-not $portSel) { Write-Error "No free port found in $portBase..$($portBase+200)."; exit 1 }
  if ($portSel -ne $portBase) { Write-Host "[run] Port $portBase busy — using $portSel instead." -ForegroundColor Yellow }
}

$ollamaUrl = "http://$(if($env:OLLAMA_HOST){$env:OLLAMA_HOST}else{'localhost'}):$(if($env:OLLAMA_PORT){$env:OLLAMA_PORT}else{'11434'})"
try { Invoke-WebRequest -UseBasicParsing "$ollamaUrl/api/tags" -TimeoutSec 3 | Out-Null }
catch { Write-Host "[run] Ollama not reachable at $ollamaUrl — API starts but jobs need Ollama running." -ForegroundColor Yellow }

Write-Host "[run] Agent Annotate API -> http://${bindHost}:${portSel}   (docs: /docs - health: /api/health - Ctrl-C to stop)" -ForegroundColor Cyan
uvicorn app.main:app --host $bindHost --port $portSel
