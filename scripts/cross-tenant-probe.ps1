<#
.SYNOPSIS
    跨租户隔离对撞探针（走查 #7 / STATUS「已知风险」首条）。

.DESCRIPTION
    注册两个完全独立的组织 A、B（各自 owner），用 B 的令牌去访问 A 的资源，
    断言一律被隔离（404/403/数据不串），同时用「owner 自己能访问」作控制组，
    排除「资源根本没建成功导致 404」的假阴性。

    覆盖：会话 / 知识库 / 企业档案 / 成员管理(按 membership_id 横向越权) /
          参数注入(query 覆盖 tenant_id) / 无令牌 401。
    可选(数据齐才测)：工作台 Feed / 租户级 LLM key。

.PARAMETER BaseUrl
    API 根，默认走本地网关。形如 http://localhost:8888/api

.EXAMPLE
    .\scripts\cross-tenant-probe.ps1
    .\scripts\cross-tenant-probe.ps1 -BaseUrl http://localhost:8888/api -Verbose
#>
[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:8888/api"
)

$ErrorActionPreference = "Stop"
$script:Pass = 0
$script:Fail = 0

# ---------- HTTP 封装（PowerShell 5.1：非 2xx 抛异常，统一捕获状态码） ----------
function Invoke-Api {
    param(
        [string]$Method,
        [string]$Path,
        [string]$Token,
        $Body
    )
    $headers = @{}
    if ($Token) { $headers["Authorization"] = "Bearer $Token" }
    $uri = "$BaseUrl$Path"
    try {
        $params = @{ Uri = $uri; Method = $Method; Headers = $headers; ErrorAction = "Stop" }
        if ($null -ne $Body) {
            # PS 5.1 默认按 ASCII 编码请求体，中文会变 '?'；显式转 UTF-8 字节发送
            $json = ($Body | ConvertTo-Json -Depth 8)
            $params.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
            $params.ContentType = "application/json; charset=utf-8"
        }
        $resp = Invoke-RestMethod @params
        return @{ Ok = $true; Status = 200; Data = $resp.data; Code = $resp.code }
    } catch {
        $status = $null
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        return @{ Ok = $false; Status = $status; Data = $null; Code = $null }
    }
}

function Assert {
    param([string]$Name, [bool]$Condition, [string]$Detail = "")
    if ($Condition) {
        $script:Pass++
        Write-Host ("  [PASS] {0}" -f $Name) -ForegroundColor Green
    } else {
        $script:Fail++
        Write-Host ("  [FAIL] {0}  {1}" -f $Name, $Detail) -ForegroundColor Red
    }
}

function New-Org {
    param([string]$Tag)
    $stamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $email = "probe-$Tag-$stamp@example.com"
    $body = @{
        email        = $email
        password     = "Probe1234!"
        display_name = "Probe-$Tag"
        mode         = "create"
        org_name     = "对撞测试组织-$Tag-$stamp"
    }
    $r = Invoke-Api -Method POST -Path "/auth/register" -Body $body
    if (-not $r.Ok) { throw "注册 $Tag 失败 (HTTP $($r.Status))，请确认服务已起：dev-up.cmd -Mode Remote" }
    return @{
        Email    = $email
        Token    = $r.Data.access_token
        TenantId = $r.Data.active_tenant_id
        Role     = $r.Data.role
    }
}

Write-Host "`n=== 跨租户隔离对撞探针 ===" -ForegroundColor Cyan
Write-Host "BaseUrl: $BaseUrl`n"

# 0. 健康检查
$health = Invoke-Api -Method GET -Path "/status"
if (-not $health.Ok) {
    Write-Host "服务未就绪（/status 不通）。先起栈：.\dev-up.cmd -Mode Remote" -ForegroundColor Yellow
    exit 2
}

# 1. 建两个独立组织
Write-Host "[准备] 注册两个独立组织 A / B ..." -ForegroundColor Cyan
$A = New-Org -Tag "A"
$B = New-Org -Tag "B"
Write-Host ("  A tenant={0} role={1}" -f $A.TenantId, $A.Role)
Write-Host ("  B tenant={0} role={1}" -f $B.TenantId, $B.Role)
Assert "两租户 ID 不同" ($A.TenantId -ne $B.TenantId)

# ============================================================
# 会话隔离
# ============================================================
Write-Host "`n[会话] A 建会话，B 越权读取/删除" -ForegroundColor Cyan
$sa = Invoke-Api -Method POST -Path "/sessions" -Token $A.Token
$sidA = $sa.Data.session_id
Assert "控制组：A 能读自己的会话" ((Invoke-Api -Method GET -Path "/sessions/$sidA" -Token $A.Token).Ok) "前置失败则下面是假阴性"

$r = Invoke-Api -Method GET -Path "/sessions/$sidA" -Token $B.Token
Assert "B 读 A 会话 -> 404" ($r.Status -eq 404) "实得 HTTP $($r.Status)"

$r = Invoke-Api -Method POST -Path "/sessions/$sidA/delete" -Token $B.Token
Assert "B 删 A 会话 -> 404" ($r.Status -eq 404) "实得 HTTP $($r.Status)"
Assert "B 删除后 A 会话仍在" ((Invoke-Api -Method GET -Path "/sessions/$sidA" -Token $A.Token).Ok) "若不在说明被越权删除"

# ============================================================
# 知识库隔离
# ============================================================
Write-Host "`n[知识库] A 建库，B 越权读取/删除" -ForegroundColor Cyan
$ka = Invoke-Api -Method POST -Path "/knowledge-bases" -Token $A.Token -Body @{ name = "A机密库"; description = "secret" }
$kbA = $ka.Data.id
Assert "控制组：A 能读自己的知识库" ((Invoke-Api -Method GET -Path "/knowledge-bases/$kbA" -Token $A.Token).Ok)

$r = Invoke-Api -Method GET -Path "/knowledge-bases/$kbA" -Token $B.Token
Assert "B 读 A 知识库 -> 404" ($r.Status -eq 404) "实得 HTTP $($r.Status)"

$r = Invoke-Api -Method DELETE -Path "/knowledge-bases/$kbA" -Token $B.Token
Assert "B 删 A 知识库 -> 404" ($r.Status -eq 404) "实得 HTTP $($r.Status)"
Assert "B 删除后 A 知识库仍在" ((Invoke-Api -Method GET -Path "/knowledge-bases/$kbA" -Token $A.Token).Ok)

# ============================================================
# 企业档案隔离（数据不串，而非 404）
# ============================================================
Write-Host "`n[企业档案] A 存机密档案，B 读到的必须是自己的" -ForegroundColor Cyan
# 用纯 ASCII 机密值：PS 5.1 IRM 读回中文会 mojibake（仅客户端显示，非产品问题），
# 隔离断言不依赖中文，避免假失败
$secret = "PROBE-SECRET-$([guid]::NewGuid().ToString('N').Substring(0,12))"
Invoke-Api -Method PUT -Path "/enterprise-profile" -Token $A.Token -Body @{ company_name = $secret } | Out-Null
$pa = Invoke-Api -Method GET -Path "/enterprise-profile" -Token $A.Token
Assert "控制组：A 读回自己的机密档案" ($pa.Data.company_name -eq $secret) "实得 '$($pa.Data.company_name)'"

$pb = Invoke-Api -Method GET -Path "/enterprise-profile" -Token $B.Token
Assert "B 读档案不含 A 的机密" ($pb.Data.company_name -ne $secret) "泄漏！B 读到 '$($pb.Data.company_name)'"

# ============================================================
# 成员管理：按 membership_id 横向越权
# ============================================================
Write-Host "`n[成员] B 拿 A 的 membership_id 越权改角色/移除" -ForegroundColor Cyan
$ma = Invoke-Api -Method GET -Path "/members" -Token $A.Token
$membershipA = $ma.Data.members[0].membership_id
Assert "控制组：A 能列出自己组织成员" ($null -ne $membershipA)

$mb = Invoke-Api -Method GET -Path "/members" -Token $B.Token
$bSeesA = @($mb.Data.members | Where-Object { $_.membership_id -eq $membershipA }).Count -gt 0
Assert "B 的成员列表看不到 A 的成员" (-not $bSeesA)

$r = Invoke-Api -Method POST -Path "/members/$membershipA/role" -Token $B.Token -Body @{ role = "member" }
Assert "B 改 A 成员角色 -> 403/404" ($r.Status -eq 404 -or $r.Status -eq 403) "实得 HTTP $($r.Status)"

$r = Invoke-Api -Method POST -Path "/members/$membershipA/delete" -Token $B.Token
Assert "B 移除 A 成员 -> 403/404" ($r.Status -eq 404 -or $r.Status -eq 403) "实得 HTTP $($r.Status)"
Assert "越权后 A 成员仍在" (@((Invoke-Api -Method GET -Path "/members" -Token $A.Token).Data.members | Where-Object { $_.membership_id -eq $membershipA }).Count -gt 0)

# ============================================================
# 参数注入：query 试图覆盖当前租户（ADR-002）
# ============================================================
Write-Host "`n[参数注入] B 用 query tenant_id=A 试图越权" -ForegroundColor Cyan
$r = Invoke-Api -Method GET -Path "/sessions?tenant_id=$($A.TenantId)" -Token $B.Token
$leaked = $false
if ($r.Ok -and $r.Data.sessions) {
    $leaked = @($r.Data.sessions | Where-Object { $_.session_id -eq $sidA }).Count -gt 0
}
Assert "query 覆盖 tenant_id 无效（B 看不到 A 的会话）" (-not $leaked) "注入生效=泄漏"

# ============================================================
# 无令牌
# ============================================================
Write-Host "`n[未认证] 无令牌访问受保护资源" -ForegroundColor Cyan
$r = Invoke-Api -Method GET -Path "/sessions"
Assert "无令牌 -> 401" ($r.Status -eq 401) "实得 HTTP $($r.Status)"

# ---------- 汇总 ----------
Write-Host "`n=== 结果 ===" -ForegroundColor Cyan
$summaryColor = "Green"; if ($script:Fail -gt 0) { $summaryColor = "Red" }
Write-Host ("PASS: {0}   FAIL: {1}" -f $script:Pass, $script:Fail) -ForegroundColor $summaryColor
Write-Host "注：探针用了一次性账号，未做清理；如需可在 DB 内按 email 前缀 'probe-' 事务删除。`n"
if ($script:Fail -gt 0) { exit 1 } else { exit 0 }
