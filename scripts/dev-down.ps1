[CmdletBinding()]
param(
    [switch]$StopTunnel
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

docker compose down
if ($LASTEXITCODE -ne 0) {
    throw "docker compose down failed."
}

if ($StopTunnel) {
    $pidPath = Join-Path $repoRoot "tmp\remote-db-tunnel.pid"
    if (Test-Path -LiteralPath $pidPath) {
        $tunnelPid = [int](Get-Content -LiteralPath $pidPath -Raw)
        Stop-Process -Id $tunnelPid -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $pidPath -Force
    }
}
