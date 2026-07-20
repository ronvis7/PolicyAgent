# 开发与部署手册

## 首次准备

```powershell
Copy-Item .env.example .env
Copy-Item api/config.yaml.example api/config.yaml
```

填写 `.env` 中数据库、JWT 和 COS 配置，并填写 `api/config.yaml` 中模型配置。禁止提交真实密钥。

赛事全网发现默认 `CONTEST_SEARCH_PROVIDER=auto`：配置 `BAIDU_SEARCH_API_KEY` 后优先调用百度千帆 v2，
否则记录告警并回落 Bing。`CONTEST_SEARCH_TOP_K` 默认 20、最大 50；
`CONTEST_SEARCH_FALLBACK_ENABLED=true` 时百度失败或空结果会自动回落。密钥只写部署 `.env`，不得入库。

## 常用检查

```powershell
git status --short --branch
docker compose config --no-env-resolution -q
```

## Docker 启动

推荐使用统一开发启动脚本。默认 `Auto` 模式优先连接远程共享数据库，远程服务器或 SSH 隧道不可用时自动回退到本地 PostgreSQL：

```powershell
.\dev-up.cmd -Build
```

可显式选择数据库模式：

```powershell
.\dev-up.cmd -Mode Remote -Build
.\dev-up.cmd -Mode Local -Build
```

拉取当前分支后启动（仅在工作区干净时执行）：

```powershell
.\dev-up.cmd -Pull -Build
```

停止服务：

```powershell
.\dev-down.cmd
.\dev-down.cmd -StopTunnel
```

仍可直接使用标准 Compose 启动本地数据库模式：

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f policy-api
```

服务入口默认由 Nginx 暴露，端口读取 `NGINX_PORT`。

## 数据库迁移

API 启动时会执行 Alembic upgrade。需要手工执行时：

```powershell
docker compose exec policy-api alembic upgrade head
```

新增迁移：

```powershell
docker compose exec policy-api alembic revision --autogenerate -m "change description"
```

必须人工检查自动生成的迁移内容。

## 通过 SSH 隧道连接远程 PostgreSQL

远程 PostgreSQL 应只绑定服务器回环地址，不直接暴露公网 `5432`。每台开发机首次使用时：

```powershell
Copy-Item .env.remote.example .env.remote
```

填写 `.env.remote` 中的服务器、SSH 私钥和数据库凭据。SSH 公钥必须提前加入服务器的 `authorized_keys`；自动模式使用 `BatchMode=yes`，不会保存或交互输入 SSH 密码。

```powershell
.\dev-up.cmd -Build
```

脚本会复用现有 `15432` 隧道；没有隧道时在后台自动创建。远程模式会停止未使用的本地 `policy-postgres`，自动回退或 `Local` 模式会重新启动它并使用 `.env` 中的本地数据库配置。

多台开发机共享数据库时必须保持 Alembic 版本一致，禁止让不同迁移分支同时修改共享数据库。

## 后端验证

优先在 Docker 内运行，避免宿主机 Python 差异：

```powershell
docker compose exec policy-api pytest
```

租户相关 PR 至少验证：

- 同租户访问成功。
- 跨租户读取返回 404 或 403。
- 无 Token 返回 401。
- 普通成员访问平台配置返回 403。

## 前端验证

```powershell
Set-Location ui
npm.cmd ci
npm.cmd run lint
npm.cmd run build
```

## Compose 隔离标识

- Compose project：`policy-manus`
- PostgreSQL：`policy-postgres`
- Redis：`policy-redis`
- API：`policy-api`
- UI：`policy-ui`
- Sandbox：`policy-sandbox`
- Network：`policy-network`
- Database：`policy_manus`

## 故障交接

不要把完整日志写入共享记忆。交接文件只保留：

- 失败命令。
- 最关键错误。
- 已排除原因。
- 下一步复现命令。
