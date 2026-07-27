# PolicyAgent 前端品牌同步

日期：2026-07-27

## 完成内容

- 将前端页面元数据、登录/注册、导航、聊天、设置和工具预览中的用户可见品牌名由 `PolicyManus` 统一为 `PolicyAgent`。
- 更新 `ui/README.md` 的前端名称。
- 保留内部 npm package、Compose project、容器、数据库和目录中的 `policy-manus` 标识，避免破坏现有构建与部署兼容性。
- 排除四张未被代码引用的试验 PNG 素材，不纳入版本库或部署。
- 收口上一轮租户百度赛事搜索配置的 RUNBOOK、STATUS 和交接部署记录。

## 接口与数据变化

- 无 API 变化。
- 无数据库或 Alembic 迁移。
- 无租户隔离、密钥或运行时配置变化。

## 验证

- `npm ci`：通过。
- `npm run lint`：0 errors，30 条既有 warnings。
- `npm run build`：通过。
- `git diff --check`：通过。

## 部署边界

- 合并后从 `main` 归档完整代码树到 `.222`，保留服务器 `.env` 与 `api/config.yaml`。
- 仅需重建 `policy-ui`；后端代码、数据库与迁移均未变化。
- 部署后检查 `policy-ui` healthy、首页和 `/api/status` 返回 200，并确认页面标题及登录页显示 `PolicyAgent`。
- `.deployed_commit` 必须写入合并后的完整 40 位提交哈希和真实换行，修正旧标记末尾误写的字面量 `n`。
