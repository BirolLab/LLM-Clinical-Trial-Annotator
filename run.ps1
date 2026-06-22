# ─────────────────────────────────────────────────────────────────────────
# Agent Annotate — start the standalone API (Windows PowerShell).
#
# Usage:
#   .\run.ps1                          # binds 127.0.0.1:9005
#   $env:HOST="0.0.0.0"; $env:PORT="8080"; .\run.ps1
# ─────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$bindHost = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$bindPort = if ($env:PORT) { $env:PORT } else { "9005" }

$activate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) { . $activate }

Write-Host "[run] Agent Annotate API -> http://${bindHost}:${bindPort}  (Ctrl-C to stop)" -ForegroundColor Cyan
uvicorn app.main:app --host $bindHost --port $bindPort
