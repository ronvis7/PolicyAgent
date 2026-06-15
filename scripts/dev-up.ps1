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
        "-o", "ConnectTimeout=8",
        # 首次连接新主机时自动信任其 host key（自愈）：服务器重建或换开发机后，
        # 缺失的 host key 在 BatchMode 下会让 SSH 静默失败，被误报成"PG 不可用"。
        # accept-new 只补新增、不覆盖变更，host key 被篡改仍会拒绝，安全。
        "-o", "StrictHostKeyChecking=accept-new"
    )
    if ($env:REMOTE_SSH_KEY) {
        $keyPath = [Environment]::ExpandEnvironmentVariables($env:REMOTE_SSH_KEY)
        $sshOptions += @("-i", $keyPath)
    }

    # 探测 SSH 上的远程 PostgreSQL 端口；失败时再单独判一次 SSH 连通性，
    # 以区分"SSH 连不上(网络/密钥/host key)"和"SSH 通但 PG 没起来"。
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
        # 用一次最轻量的命令判断 SSH 本身是否能登录，给出可定位的报错
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            & $ssh.Source @sshOptions $target "true" 2>$null
            $sshExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($sshExitCode -ne 0) {
            Write-Warning "Cannot SSH to $target (check network, key '$($env:REMOTE_SSH_KEY)', or a changed host key in ~/.ssh/known_hosts)."
        }
        else {
            Write-Warning "SSH OK, but remote PostgreSQL ${remoteDbHost}:${remoteDbPort} is unreachable (is the policy-postgres container running on the server?)."
        }
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

function Invoke-Docker {
    param(
        [Parameter(Mandatory)][string[]]$DockerArgs,
        [Parameter(Mandatory)][string]$FailureMessage
    )

    # docker/compose 把构建与拉取进度写到 stderr；在脚本级 $ErrorActionPreference='Stop' 下，
    # PowerShell 会把这些 stderr 行当成终止错误，导致 compose 实际成功也抛出。
    # 这里临时降级为 'Continue'，只按退出码判定成败，避免误报中断后续步骤。
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker @DockerArgs
    }
    finally {
        $ErrorActionPreference = $previous
    }
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
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
Invoke-Docker -DockerArgs $composeArgs -FailureMessage "docker compose up failed."

if ($useRemote) {
    Invoke-Docker -DockerArgs @("compose", "stop", "policy-postgres") `
        -FailureMessage "Unable to stop the unused local PostgreSQL container."
}

$restartArgs = @("compose")
if ($useRemote) {
    $restartArgs += @("-f", "docker-compose.yml", "-f", "docker-compose.remote-db.yml")
}
$restartArgs += @("restart", "policy-nginx")
Invoke-Docker -DockerArgs $restartArgs -FailureMessage "Nginx restart failed."

Write-Host "PolicyManus is running in $activeMode database mode."
