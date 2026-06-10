# 开发与部署手册

## 首次准备

```powershell
Copy-Item .env.example .env
Copy-Item api/config.yaml.example api/config.yaml
```

填写 `.env` 中数据库、JWT 和 COS 配置，并填写 `api/config.yaml` 中模型配置。禁止提交真实密钥。

## 常用检查

```powershell
git status --short --branch
docker compose config --no-env-resolution -q
```

## Docker 启动

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

