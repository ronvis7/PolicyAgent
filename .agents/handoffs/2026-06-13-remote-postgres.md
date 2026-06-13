# 远程 PostgreSQL 部署

Issue：待创建
分支：`feat/remote-postgres-config`
负责人：Codex
更新时间：2026-06-13

## 目标

部署一套供多台开发机共享的远程 PostgreSQL + pgvector，并让本地 Docker API 可通过 SSH 隧道连接。

## 已完成

- 在远程服务器 `/opt/policy-postgres` 部署独立 Compose 项目。
- 使用 `pgvector/pgvector:pg16` 镜像、独立 `policy-postgres-data` 数据卷和 `policy_app` 应用用户。
- PostgreSQL 仅绑定服务器 `127.0.0.1:5432`，不直接暴露公网。
- 创建并验证 `vector` 扩展，版本为 `0.8.2`。
- 本地 Compose 的 `POSTGRES_HOST` 和 `POSTGRES_PORT` 支持由 `.env` 覆盖，默认本地部署行为不变。
- 新增 `docker-compose.remote-db.yml`，远程模式下禁用本地 PostgreSQL 并移除 API 对本地数据库的启动依赖。
- 新增 `scripts/dev-up.ps1`：支持 `Auto/Remote/Local`，自动建立 SSH 隧道，远程不可用时回退本地数据库。
- 新增 `scripts/dev-down.ps1`：停止 Compose，可选同时停止脚本创建的 SSH 隧道。
- 新增 `dev-up.cmd` / `dev-down.cmd`，兼容 Windows 默认禁止直接执行 PowerShell 脚本的环境。
- 新增 `.env.remote.example`，远程连接机密保存在 gitignored `.env.remote`。
- 运行手册增加 SSH 隧道连接方式。

## 验证

- 远程容器状态：healthy。
- 数据库：`policy_manus`。
- 数据库用户：`policy_app`。
- 监听地址：`127.0.0.1:5432`。
- 远程 `.env` 权限：`600`。
- Alembic：`a1b2c3d4e5f6 (head)`。
- 本机远程模式 API：HTTP 200。
- 本机 Nginx/UI：HTTP 200，页面标题 `PolicyManus`。
- 初始数据：`users=0`、`tenants=1`、`memberships=0`。
- `dev-up.cmd -Mode Remote`：自动创建密钥 SSH 隧道并启动成功。
- `dev-up.cmd -Mode Local`：API 切换到 `policy-postgres:5432`，UI/API HTTP 200。
- `dev-up.cmd` 故障模拟：远程 SSH 主机不可达时提示告警并自动回退本地数据库。

## 剩余事项

- ~~为远程数据库配置定期备份~~ ✅ 已完成（见 handoff `2026-06-13-db-backup`）。
- 在另一台电脑重复配置 SSH 隧道和本地 `.env` 后，验证跨电脑登录同一账号。

## 追加：隧道 host key 自愈 + 报错分层（2026-06-14）

### 现象与根因
`dev-up.cmd -Mode Remote` 报 "Remote server or PostgreSQL is unavailable."，但服务器、22 端口、密钥、`policy-postgres` 容器（Up 11h healthy）全正常。根因：脚本 SSH 用 `BatchMode=yes` 但**未设** `StrictHostKeyChecking`，默认 `ask` 在非交互下无法确认新主机 → 当本机 `known_hosts` 缺该服务器 host key（服务器重建换了新 key / 换开发机）时 SSH 静默失败，且与"PG 没起来"共用同一句含糊告警。

### 修复（`scripts/dev-up.ps1`）
- `$sshOptions` 增 `-o StrictHostKeyChecking=accept-new`：首次自动信任新主机（自愈）；只补新增、不覆盖变更，host key 被篡改仍拒绝。
- 探测拆分：PG 端口探测失败时再轻量探一次 SSH 连通性，分别报 "Cannot SSH to …(网络/密钥/host key)" 与 "SSH OK but remote PostgreSQL … unreachable(容器没起？)"，便于定位。

### 验证
- 复现脚本同款探测：`probe exit code: 0`；`known_hosts` 已含该服务器。
- `[Parser]::ParseFile` 语法 OK；用户真机重跑 `dev-up.cmd -Mode Remote -Build` 启动成功。

## 风险

- SSH 隧道中断时，本地 API 会失去数据库连接。
- 自动 SSH 隧道依赖每台开发机提前配置无密码 SSH 密钥；首次机器初始化仍需人工授权公钥。
- 多个开发分支不得同时对共享数据库执行不兼容迁移。
- 远程数据库凭据只保存在远程和各开发机 gitignored `.env`，不得写入 Git。
