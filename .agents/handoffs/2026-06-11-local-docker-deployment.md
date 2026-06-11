# 本地 Docker 部署验证

Issue：待创建
分支：`main`
负责人：Codex
更新时间：2026-06-11

## 目标

从干净 Docker 环境构建并启动 PolicyManus，验证网关、前端、API、数据库、Redis 和 Sandbox。

## 已完成

- 清理原有 Docker 容器、镜像、数据卷、自定义网络和构建缓存。
- 构建并启动全部六个 Compose 服务。
- 修复 Sandbox 中文字体安装时 ARM64 镜像下载不稳定的问题。
- 修复 Alembic 使用硬编码数据库密码、无法适配 `.env` 的问题。
- 增加平台管理员“模型 API 配置”侧边栏入口和安全配置状态展示。
- 修复应用异常丢失错误文本的问题，缺少模型密钥时返回明确提示。
- 浏览器确认 `http://127.0.0.1:8888/` 可加载 PolicyManus 首页。

## 接口与迁移

- `/api/auth/me` 用户对象增加 `is_platform_admin`。
- LLM 配置读取响应增加 `api_key_configured`，且不再返回 `api_key` 字段。
- `api/alembic/env.py` 现在从 `Settings` 获取数据库 URL，并为 Alembic 使用同步 psycopg2 驱动。
- `sandbox/Dockerfile` 在安装中文字体前切换到 Ubuntu Ports 官方源并启用下载重试。

## 验证

- `docker compose up -d --build`：全部镜像构建成功。
- `docker compose ps -a`：API、UI、PostgreSQL、Redis 健康，Nginx 和 Sandbox 正常运行。
- `docker compose exec -T policy-api alembic current`：`e5f6a7b8c9d0 (head)`。
- Nginx 内部请求 `/api/status`：PostgreSQL、Redis 均为 `ok`。
- Nginx 内部请求 `/`：HTTP 200。
- 应用浏览器访问 `http://127.0.0.1:8888/`：标题为 `PolicyManus`，首页输入框可见。
- API/UI 生产镜像构建和 TypeScript 检查通过。
- 本次涉及的前端文件 ESLint 通过。
- 管理员令牌访问 `/api/app-config/llm` 成功，响应不含密钥。
- `git diff --check`：通过。

## 未完成

- `.env` 的 COS 参数和 `api/config.yaml` 的模型密钥仍为本地占位值。
- 尚未验证真实文件上传、模型问答和动态 Sandbox 任务链路。

## 风险

- 没有有效 COS/LLM 凭据时，基础服务可运行，但上传和 Agent 调用会失败。
- 当前修复仍在 `main` 工作区，尚未提交。

## 下一步

1. 配置有效的 COS 与模型凭据后，执行一条上传文件到 Agent 回答的端到端验证。
