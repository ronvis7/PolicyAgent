[CmdletBinding()]
param(
    [ValidateSet("Auto", "Remote", "Local")]
    [string]$Mode = "Auto",
    [switch]$Build,
    [switch]$Pull
)

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
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }
        $name = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][int]$Port,
        [int]$TimeoutMilliseconds = 1000
    )

    $client = [Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        return $task.Wait($TimeoutMilliseconds) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Start-RemoteTunnel {
    $remoteEnvPath = Join-Path $repoRoot ".env.remote"
    if (-not (Test-Path -LiteralPath $remoteEnvPath)) {
        Write-Warning ".env.remote is missing; remote database mode is unavailable."
        return $false
    }

    Import-DotEnv -Path $remoteEnvPath
    $required = @(
        "REMOTE_SSH_HOST",
        "REMOTE_SSH_USER",
        "REMOTE_DB_LOCAL_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD"
    )
    foreach ($name in $required) {
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            Write-Warning "$name is missing from .env.remote."
            return $false
        }
    }

    $ssh = Get-Command ssh -ErrorAction SilentlyContinue
    if (-not $ssh) {
        Write-Warning "OpenSSH client is not installed."
        return $false
    }

    $localPort = [int]$env:REMOTE_DB_LOCAL_PORT
    $sshPort = if ($env:REMOTE_SSH_PORT) { $env:REMOTE_SSH_PORT } else { "22" }
    $remoteDbHost = if ($env:REMOTE_DB_HOST) { $env:REMOTE_DB_HOST } else { "127.0.0.1" }
    $remoteDbPort = if ($env:REMOTE_DB_PORT) { $env:REMOTE_DB_PORT } else { "5432" }
    $target = "$($env:REMOTE_SSH_USER)@$($env:REMOTE_SSH_HOST)"
    $sshOptions = @(
        "-p", $sshPort,
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=8"
    )
    if ($env:REMOTE_SSH_KEY) {
        $keyPath = [Environment]::ExpandEnvironmentVariables($env:REMOTE_SSH_KEY)
        $sshOptions += @("-i", $keyPath)
    }

    $probeCommand = "timeout 3 bash -c '</dev/tcp/${remoteDbHost}/${remoteDbPort}'"
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & $ssh.Source @sshOptions $target $probeCommand 2>$null
        $probeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($probeExitCode -ne 0) {
        Write-Warning "Remote server or PostgreSQL is unavailable."
        return $false
    }

    if (Test-TcpPort -HostName "127.0.0.1" -Port $localPort) {
        $env:POSTGRES_HOST = "host.docker.internal"
        $env:POSTGRES_PORT = [string]$localPort
        return $true
    }

    $arguments = @(
        "-N",
        "-L", "${localPort}:${remoteDbHost}:${remoteDbPort}"
    )
    $arguments += $sshOptions
    $arguments += @(
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3"
    )
    $arguments += $target

    try {
        $process = Start-Process `
            -FilePath $ssh.Source `
            -ArgumentList $arguments `
            -WindowStyle Hidden `
            -PassThru
    }
    catch {
        Write-Warning "Unable to start SSH tunnel: $($_.Exception.Message)"
        return $false
    }

    for ($attempt = 0; $attempt -lt 16; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-TcpPort -HostName "127.0.0.1" -Port $localPort) {
            $pidPath = Join-Path $repoRoot "tmp\remote-db-tunnel.pid"
            New-Item -ItemType Directory -Force -Path (Split-Path $pidPath) | Out-Null
            Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii
            $env:POSTGRES_HOST = "host.docker.internal"
            $env:POSTGRES_PORT = [string]$localPort
            return $true
        }
        if ($process.HasExited) {
            break
        }
    }

    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Warning "Remote database tunnel could not be established."
    return $false
}

function Set-LocalDatabaseEnvironment {
    Import-DotEnv -Path (Join-Path $repoRoot ".env")
    $env:POSTGRES_HOST = "policy-postgres"
    $env:POSTGRES_PORT = "5432"
}

if ($Pull) {
    if ((git status --porcelain)) {
        throw "Working tree is not clean; refusing to pull."
    }
    git pull
    if ($LASTEXITCODE -ne 0) {
        throw "git pull failed."
    }
}

$useRemote = $false
if ($Mode -ne "Local") {
    $useRemote = Start-RemoteTunnel
}
if ($Mode -eq "Remote" -and -not $useRemote) {
    throw "Remote mode was requested, but the SSH tunnel is unavailable."
}

$composeArgs = @("compose")
if ($useRemote) {
    $composeArgs += @("-f", "docker-compose.yml", "-f", "docker-compose.remote-db.yml")
    $activeMode = "remote"
}
else {
    Set-LocalDatabaseEnvironment
    $activeMode = "local"
}
$composeArgs += @("up", "-d")
if ($Build) {
    $composeArgs += "--build"
}

Write-Host "Starting PolicyManus with $activeMode PostgreSQL..."
& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed."
}

if ($useRemote) {
    docker compose stop policy-postgres
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to stop the unused local PostgreSQL container."
    }
}

$restartArgs = @("compose")
if ($useRemote) {
    $restartArgs += @("-f", "docker-compose.yml", "-f", "docker-compose.remote-db.yml")
}
$restartArgs += @("restart", "policy-nginx")
& docker @restartArgs
if ($LASTEXITCODE -ne 0) {
    throw "Nginx restart failed."
}

Write-Host "PolicyManus is running in $activeMode database mode."
