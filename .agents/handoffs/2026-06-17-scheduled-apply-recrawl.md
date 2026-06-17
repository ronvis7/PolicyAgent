# 公开政策定时重爬（应用内调度器，保鲜 ⑤ 申报截止）

更新时间：2026-06-17
分支/PR：`feat/scheduled-apply-recrawl`（从 `feat/policy-apply-deadline`/PR #32 派生，待开 PR）。

## 背景

⑤ 临期提醒要"活"需周期性重爬 `wnd-apply`（申报窗口常只有 1-2 周）。**架构约束**：本 stack 跑在
开发机(dev-up + 共享远程库)、非常驻服务器；抓取需 网络+DB+Embedding/LLM key+应用代码 同在 api 容器内。
→ 云端 `/schedule` 到不了本地栈、.222 仅 DB 无应用代码，**唯一自洽方案是应用内调度器**。

## 实现

- **`PolicyRecrawlScheduler`（新）**：APScheduler `AsyncIOScheduler` 挂 api 进程事件循环，`CronTrigger`
  每天定时触发，逐来源 best-effort 调 `ingest`（单源失败只 warning、不冒泡；幂等可重复跑）。
- **lifespan 接线**：DB init 后 `start()`、关闭时 `shutdown(wait=False)`；`start()` 抛错会让启动失败
  (但已 healthy 验证不抛)。
- **配置**（`core/config.py`，全 env 可调）：`POLICY_RECRAWL_ENABLED`(默认 true) /
  `POLICY_RECRAWL_SOURCES`(默认 `wnd-apply`，逗号分隔) / `POLICY_RECRAWL_HOUR`(4) / `_MINUTE`(0) /
  `_MAX_PAGES`(3) / `_TIMEZONE`(默认 `Asia/Shanghai`)。
- **时区坑**：容器 TZ=UTC，CronTrigger 不指定时区时 04:00 实跑成中午 12:00 CST；故按数据源所在地
  钉 `Asia/Shanghai`，hour 才符合"凌晨错峰"直觉。
- **依赖**：pyproject 加 `apscheduler>=3.11`；其传递依赖 `tzlocal` 钉 `<5.4`——5.4.3 于 2026-06-17 当天
  发布、容器内 uv 索引尚未传播会致构建失败，回退 5.3.1。`uv lock` + `uv export` 重生 requirements.txt。

## 真机验证（连 .222，2026-06-17）

- 修 tzlocal 后镜像构建通过；栈起健康。
- 容器内以真实 settings 构造调度器：`enabled=True / sources=['wnd-apply'] / 04:00 / max_pages=3`，
  job 注册成功、`next_run=2026-06-18 04:00:00+08:00`(CST，时区修复后正确)。
- 抓取路径本身在 PR #32 已真机验证（`ingest('wnd-apply')` → extracted 23/60）。
- 新增调度器单测 4，全量 **173 passed**（1 error 为既有需真库 test_get_status）。

## 注意

- **app logger 不输出到 docker stdout**（既有坑）→ 调度器/抓取日志在容器日志文件、非 `docker logs`；
  排障看文件或临时把 hour/minute 调到近前验证 DB 变化。
- **单实例假设**（当前单 api 容器）；将来多副本需分布式锁避免并发重复抓取。
- 多区域：每新增申报来源在 `POLICY_RECRAWL_SOURCES` 追加其 key 即可，无需改调度器。
