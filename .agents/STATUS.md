# 当前状态

最后更新：2026-06-11

## 仓库状态

- 主仓库：`policy_manus`
- 当前分支：`main`，工作区干净，已与 `origin/main` 同步。
- 品牌、Docker 隔离和协作记忆改动已提交（最新 `c2c33c9`）。

## 已完成

> 细节以 `git log` 为准，本节只记里程碑。

- 多租户后端闭环：tenants/users/memberships 表 + JWT 全流程 + 租户切换。
- 租户隔离：sessions、files、平台配置（platform admin 保护）。
- Docker 资源改为 `policy-*`，默认库名 `policy_manus`。
- 前端原型入 `frontend-prototype/`，正式前端仍在 `ui/`。
- `.agents/` 协作记忆体系落地。

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

1. 建立 `develop`、Issue、PR 和 CI 工作流。
2. 并行完成前端认证闭环与 RAG 数据模型。
3. 尽快打通一份政策文件的上传、索引、检索和引用回答。

## 已知风险

- 后端多租户测试覆盖不足，跨租户读取风险尚未系统验证。
- 前端 API 客户端当前没有自动注入 Authorization Header。
- 当前开发机的 Python 命令尚未确认可用。
- `.env` 和 `api/config.yaml` 是 Docker 启动前置条件。
- 十天范围非常紧，任何新增基础设施都必须证明能直接服务主链路。

## 更新规则

只记录最新事实。任务细节放 GitHub Issue，临时交接放 `handoffs/`，架构原因放 `decisions/`。

