# dev.ps1 — start backend + frontend for local development
#
# Prerequisites (one-time):
#   cd backend && pip install -e .
#   cp .env.example .env   # then set OLLAMA_BASE_URL, OLLAMA_API_KEY, etc.
#
# Usage:
#   .\dev.ps1              # start both
#   .\dev.ps1 -Backend     # backend only
#   .\dev.ps1 -Frontend    # frontend only

param(
    [switch]$Backend,
    [switch]$Frontend
)

$RunBoth = -not $Backend -and -not $Frontend

if ($RunBoth -or $Backend) {
    Write-Host "[dev] Starting backend on http://localhost:8000 ..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command",
        "cd '$PSScriptRoot'; python -m archinator.api"
}

if ($RunBoth -or $Frontend) {
    Write-Host "[dev] Starting frontend on http://localhost:5173 ..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command",
        "cd '$PSScriptRoot\frontend'; npm run dev"
}

Write-Host ""
Write-Host "  Backend:  http://localhost:8000/health"
Write-Host "  Frontend: http://localhost:5173"
Write-Host ""
Write-Host "Close the opened terminal windows to stop." -ForegroundColor Gray
