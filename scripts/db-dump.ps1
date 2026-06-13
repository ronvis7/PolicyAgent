[CmdletBinding()]
param(
    # Number of local snapshots to keep (older ones are pruned by mtime)
    [int]$Keep = 14,
    # Output directory, defaults to <repo>/backups
    [string]$OutDir
)

# Dump the remote shared PostgreSQL into a local compressed snapshot (pg_dump custom format)
# through the SSH tunnel. One-way / read-only: backup only, never written back to remote.
# Restore with pg_restore.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Import-DotEnv {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing environment file: $Path"
    }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $sep = $trimmed.IndexOf("=")
        if ($sep -lt 1) { continue }
        $name = $trimmed.Substring(0, $sep).Trim()
        $value = $trimmed.Substring($sep + 1).Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Test-TcpPort {
    param([string]$HostName = "127.0.0.1", [int]$Port, [int]$TimeoutMs = 1000)
    $client = [Net.Sockets.TcpClient]::new()
    try { $client.ConnectAsync($HostName, $Port).Wait($TimeoutMs) -and $client.Connected }
    catch { $false }
    finally { $client.Dispose() }
}

Import-DotEnv -Path (Join-Path $repoRoot ".env.remote")

foreach ($req in @("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")) {
    if (-not [Environment]::GetEnvironmentVariable($req, "Process")) {
        throw "$req is missing from .env.remote"
    }
}

$localPort = if ($env:REMOTE_DB_LOCAL_PORT) { [int]$env:REMOTE_DB_LOCAL_PORT } else { 15432 }
$remoteDbHost = if ($env:REMOTE_DB_HOST) { $env:REMOTE_DB_HOST } else { "127.0.0.1" }
$remoteDbPort = if ($env:REMOTE_DB_PORT) { $env:REMOTE_DB_PORT } else { "5432" }

# 1. Ensure the SSH tunnel is available: reuse a running one, else open a temporary one.
$tunnelProcess = $null
if (-not (Test-TcpPort -Port $localPort)) {
    Write-Host "Local port $localPort is not listening; opening a temporary SSH tunnel..."
    foreach ($req in @("REMOTE_SSH_HOST", "REMOTE_SSH_USER")) {
        if (-not [Environment]::GetEnvironmentVariable($req, "Process")) {
            throw "$req is missing from .env.remote (required to open the tunnel)"
        }
    }
    $ssh = Get-Command ssh -ErrorAction SilentlyContinue
    if (-not $ssh) { throw "OpenSSH client not found" }

    $sshPort = if ($env:REMOTE_SSH_PORT) { $env:REMOTE_SSH_PORT } else { "22" }
    $target = "$($env:REMOTE_SSH_USER)@$($env:REMOTE_SSH_HOST)"
    $sshArgs = @("-N", "-L", "${localPort}:${remoteDbHost}:${remoteDbPort}",
        "-p", $sshPort, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30")
    if ($env:REMOTE_SSH_KEY) {
        $sshArgs += @("-i", [Environment]::ExpandEnvironmentVariables($env:REMOTE_SSH_KEY))
    }
    $sshArgs += $target
    $tunnelProcess = Start-Process -FilePath $ssh.Source -ArgumentList $sshArgs -WindowStyle Hidden -PassThru

    $ok = $false
    for ($i = 0; $i -lt 16; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-TcpPort -Port $localPort) { $ok = $true; break }
        if ($tunnelProcess.HasExited) { break }
    }
    if (-not $ok) {
        if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
            Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
        }
        throw "Failed to establish SSH tunnel; aborting dump"
    }
} else {
    Write-Host "Reusing existing SSH tunnel (port $localPort)."
}

try {
    # 2. Prepare output dir and filename
    if (-not $OutDir) { $OutDir = Join-Path $repoRoot "backups" }
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $fileName = "$($env:POSTGRES_DB)_$stamp.dump"

    # 3. Run pg_dump in a postgres:16 container (matches server version), via the tunnel
    Write-Host "Dumping $($env:POSTGRES_DB) -> $fileName ..."
    & docker run --rm `
        -e PGPASSWORD="$($env:POSTGRES_PASSWORD)" `
        -v "${OutDir}:/backups" `
        --add-host=host.docker.internal:host-gateway `
        postgres:16 `
        pg_dump -h host.docker.internal -p $localPort -U $env:POSTGRES_USER `
        -d $env:POSTGRES_DB -Fc -f "/backups/$fileName"
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed (exit=$LASTEXITCODE)" }

    $full = Join-Path $OutDir $fileName
    $sizeKB = [math]::Round((Get-Item $full).Length / 1KB, 1)
    Write-Host "OK - backup written: $full ($sizeKB KB)"

    # 4. Rotation: keep only the most recent $Keep snapshots
    $dumps = Get-ChildItem -LiteralPath $OutDir -Filter "$($env:POSTGRES_DB)_*.dump" |
        Sort-Object LastWriteTime -Descending
    if ($dumps.Count -gt $Keep) {
        $dumps | Select-Object -Skip $Keep | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            Write-Host "  pruned old snapshot: $($_.Name)"
        }
    }
}
finally {
    # Only close the tunnel we opened ourselves; never touch a reused one.
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Closed temporary SSH tunnel."
    }
}
