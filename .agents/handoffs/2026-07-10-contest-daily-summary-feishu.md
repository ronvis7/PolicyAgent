# 飞书赛事通知：新赛事即推 + 每日摘要（已部署 .222）

日期：2026-07-10  
分支：`feat/core-ui-restructure`  
代码提交：`c44e9b7 feat: add daily contest feishu summary`  
部署：已部署到 `118.196.142.222:/root/policy_manus`

## 背景

用户反馈“每天推送一次比赛信息”但当天没收到飞书。排查线上后确认：原逻辑是每天重爬，但只有
赛事首次入库时才触发“新赛事即推”；2026-07-10 凌晨重爬正常执行，但所有赛事源 `last_new_count=0`，
因此没有飞书消息。用户确认希望改成两类通知，并指定时间改为每天上午 10 点重爬后自动发。

## 已完成

1. 保留原有“新赛事首次入库即推”逻辑。
2. 新增“每日赛事摘要”：
   - 在公开政策/赛事源定时重爬全部结束后触发；
   - 即使无新增也发送心跳卡片；
   - 卡片展示：今日新增数、当前匹配可参赛赛事数、14 天内截止数、最多 10 条重点赛事；
   - 已明确截止且过期的赛事不进入摘要；
   - 有 `WEB_BASE_URL` 时带“打开工作台查看赛事”按钮。
3. 租户级摘要按企业档案 `contest_regions` 过滤；未建档/未选地区仍视为不限。
4. 部署级 `FEISHU_WEBHOOK_URL`（若配置）发送全量赛事摘要，不按租户过滤。
5. 默认公开政策重爬时间从 04:00 改为 10:00 CST：
   - `api/core/config.py`: `POLICY_RECRAWL_HOUR` 默认值 `10`；
   - `.222` `.env` 显式写入 `POLICY_RECRAWL_HOUR=10`、`POLICY_RECRAWL_MINUTE=0`。

## 关键改动

- `api/app/infrastructure/external/notify/feishu_webhook.py`
  - 新增 `build_contest_daily_summary_message`
  - 新增 `make_contest_daily_summary_hook`
  - 新增 `make_tenant_contest_daily_summary_hook`
- `api/app/infrastructure/scheduler/policy_recrawl_scheduler.py`
  - 新增 `after_run` 回调，在所有来源重爬结束后执行。
- `api/app/interfaces/service_dependencies.py`
  - 新增 `build_contest_daily_summary_hook`，组合租户级与部署级摘要回调。
- `api/app/main.py`
  - `PolicyRecrawlScheduler` 接入每日摘要后置回调。
- `api/app/domain/repositories/policy_repository.py`
  - 新增 `list_by_sources` 协议。
- `api/app/infrastructure/repositories/db_policy_repository.py`
  - 实现 `list_by_sources`。
- `api/tests/app/infrastructure/external/test_feishu_webhook.py`
  - 补每日摘要卡片、租户过滤、失败隔离、部署级摘要测试。

## 验证

本地：

- `python -m py_compile app/infrastructure/external/notify/feishu_webhook.py app/infrastructure/scheduler/policy_recrawl_scheduler.py app/interfaces/service_dependencies.py app/main.py core/config.py`
- `pytest --confcutdir=tests/app/infrastructure/external tests/app/infrastructure/external/test_feishu_webhook.py`
  - 22 passed
- `pytest --confcutdir=tests/app/application/services tests/app/application/services/test_policy_service.py tests/app/application/services/test_policy_ingest_service.py`
  - 25 passed

说明：本机根 `tests/conftest.py` 会导入 MCP Windows 扩展，当前 Python 拼接环境缺 `pywintypes`，因此针对性测试用
`--confcutdir` 绕开根 conftest；业务相关用例均通过。pytest cache 目录有权限 warning，不影响结果。

线上：

- `policy-api` / `policy-ui` healthy
- `http://118.196.142.222:8088/` 200
- `http://118.196.142.222:8088/api/status` 200
- `docker exec policy-api alembic current` → `f3a4b5c6d7e8 (head)`
- `docker exec policy-api printenv POLICY_RECRAWL_HOUR POLICY_RECRAWL_MINUTE WEB_BASE_URL`
  - `10`
  - `0`
  - `http://118.196.142.222:8088`
- 容器内计算下一次 Cron 触发：`2026-07-11 10:00:00+08:00`
- 部署备份：`/root/deploy-backups/20260710-101144`

## 未做 / 注意

- 没有手动触发生产飞书每日摘要，避免额外打扰线上群。
- 下一次自然发送时间：`2026-07-11 10:00:00+08:00` 重爬结束后。
- 若用户希望“立即看效果”，可在明确授权后手动调用摘要 hook 或临时把 cron 调近；这会真实发送飞书消息。
