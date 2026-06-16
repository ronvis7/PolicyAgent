# 共享 PostgreSQL 迁移服务器（.223 → .222）

更新时间：2026-06-16

## 背景

旧服务器 `118.196.142.223` 即将停机。其上运行着我们开发依赖的共享 `policy-postgres`（pgvector）库。需在停机前迁移到 `118.196.142.222`。

> 范围：**仅迁 `policy-postgres` 共享开发库**。旧服务器上另有一套独立部署的 `good_manus` 全栈应用（`/root/good_manus`，nginx/ui/api/sandbox + 自己的 postgres/redis 卷），本次**未迁移**，按用户决定另行处理。

## 已完成

- **新服务器接入**：本机公钥 `id_ed25519_policy_manus.pub` 装入 `.222` 的 `authorized_keys`，密钥免密登录可用（`.222` 已在 `~/.ssh/config`）。两台服务器 root 密码相同。
- **复刻部署**：`.222:/opt/policy-postgres/` 与旧服务器逐字一致——`docker-compose.yml`（`pgvector/pgvector:pg16`，绑定 `127.0.0.1:5432`，卷名 `policy-postgres-data`）+ `.env`（库 `policy_manus`/用户 `policy_app`/同密码，权限 600）。容器 `policy-postgres` healthy，pgvector `0.8.2`。`.222` 上 5432 端口此前空闲，无冲突。
- **数据迁移**：旧库新鲜 `pg_dump -Fc`（`policy_manus_20260616_105827.dump`）经本机管道流式 `.223 → .222`，`pg_restore --clean --if-exists` 落库，退出码 0 无报错。
- **一致性校验**（旧/新逐项相等）：`alembic=f7a8b9c0d1e2`、`pgvector=0.8.2`、`tenants=3`、`users=2`、`memberships=2`、`policies=60`、`files=23`、`knowledge_bases=1`、`enterprise_profiles=1`、`sessions/policy_matches/tenant_settings/document_chunks=0`。
- **备份复刻**：`backup.sh` 从旧机原样拷入，cron `30 3 * * * /opt/policy-postgres/backup.sh >> .../backup.log 2>&1` 已装，试跑生成 `220K` dump 成功。
- **本地切换**：`.env.remote` 的 `REMOTE_SSH_HOST` 改为 `118.196.142.222`（其余端口/库/密码不变）。
- **端到端验证**：按 `dev-up.ps1` 同款隧道（本机 15432 → `.222:5432`）+ 容器内 psql 实查通过：`alembic=f7a8b9c0d1e2`、`tenants=3`、`policies=60`。临时隧道已关闭。

## 剩余/注意

- **旧服务器 `.223` 仍在运行 `policy-postgres`**，本次未动它（含其 03:30 cron）。**`.222` 已经全栈 Remote 真机走查通过（见下），可由用户停机**；停机前如还有写入，可再跑一次 dump 流式覆盖同步。
- ✅ **全栈走查已做**：`dev-up.cmd -Mode Remote -Build` 起栈成功、隧道确认指向 `root@118.196.142.222`、API `/status` 200，端到端注册/存档案/差距分析全通（详见 handoff `2026-06-16-qualification-gap-analysis`）。
- 其他开发机若各自配过 `.env.remote`，需同样把 `REMOTE_SSH_HOST` 改为 `.222` 并对 `.222` 授信公钥。
- `good_manus` 全栈应用迁移（若需要）另起任务：含 `/root/good_manus` 仓库 + `.env`/`config.yaml` + 数据卷（postgres ~178MB / redis ~23MB）+ 镜像（~1.4GB，重建或导出）。
