$ProjectDir = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $ProjectDir "docker-compose.yml"

$running = docker compose -f $ComposeFile ps --services --filter "status=running" 2>$null
if ($running) {
    docker compose -f $ComposeFile down
    Write-Host "FinAlly stopped."
} else {
    Write-Host "FinAlly is not running."
}
