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

## 风险

- SSH 隧道中断时，本地 API 会失去数据库连接。
- 自动 SSH 隧道依赖每台开发机提前配置无密码 SSH 密钥；首次机器初始化仍需人工授权公钥。
- 多个开发分支不得同时对共享数据库执行不兼容迁移。
- 远程数据库凭据只保存在远程和各开发机 gitignored `.env`，不得写入 Git。
