param(
    [switch]$Build
)

$ProjectDir = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $ProjectDir "docker-compose.yml"

# Check if already running
$running = docker compose -f $ComposeFile ps --services --filter "status=running" 2>$null
if ($running) {
    Write-Host "FinAlly is already running at http://localhost:8000"
    exit 0
}

if ($Build) {
    docker compose -f $ComposeFile up -d --build
} else {
    docker compose -f $ComposeFile up -d
}

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "FinAlly is running at http://localhost:8000"
