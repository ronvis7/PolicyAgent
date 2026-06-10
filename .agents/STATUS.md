# 当前状态

最后更新：2026-06-09

## 仓库状态

- 主仓库：`policy_manus`
- 当前分支：`main`
- 当前工作区存在尚未提交的 PolicyManus 品牌和 Docker 隔离改动。
- 不应在这些改动提交或暂存前执行会覆盖工作区的操作。

## 已完成

- 多租户基础表：tenants、users、memberships。
- JWT 注册、登录、刷新、退出和租户切换后端。
- sessions 租户隔离。
- files 租户隔离。
- 平台配置的 platform admin 权限保护。
- Docker 资源逐步改为 `policy-*`，数据库默认名改为 `policy_manus`。
- 前端原型已放入 `frontend-prototype/`，正式前端仍在 `ui/`。

## 未完成

- 前端登录、注册、Token 管理和租户切换。
- 成员邀请和组织成员管理。
- 多租户自动化测试。
- RAG 数据模型和向量存储。
- 文档解析、分块和 Embedding。
- 知识库页面和检索引用展示。
- 政策爬取。
- 报告生成流水线。
- GitHub Actions 和分支保护。
- 完整 Docker 构建及部署验证。

## 当前最高优先级

1. 提交现有品牌和 Docker 隔离改动。
2. 建立 `develop`、Issue、PR 和 CI 工作流。
3. 并行完成前端认证闭环与 RAG 数据模型。
4. 尽快打通一份政策文件的上传、索引、检索和引用回答。

## 已知风险

- 后端多租户测试覆盖不足，跨租户读取风险尚未系统验证。
- 前端 API 客户端当前没有自动注入 Authorization Header。
- 当前开发机的 Python 命令尚未确认可用。
- `.env` 和 `api/config.yaml` 是 Docker 启动前置条件。
- 十天范围非常紧，任何新增基础设施都必须证明能直接服务主链路。

## 更新规则

只记录最新事实。任务细节放 GitHub Issue，临时交接放 `handoffs/`，架构原因放 `decisions/`。

