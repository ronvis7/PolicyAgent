# 租户自助配置百度赛事搜索 Key

日期：2026-07-21
分支：`feat/tenant-baidu-search-config`
状态：本地实现和验证完成，未提交、未部署

## 完成内容

- 设置页新增“赛事搜索”，组织 owner/admin 可填写或轮换百度千帆 API Key。
- 新增 `GET/POST /api/app-config/contest-search`；读取只返回提供方、是否已配置、是否为组织自定义和是否启用 Bing 回退，不返回密钥明文。
- 新增 `tenant_settings.contest_search_config` JSONB 字段，迁移 `d2e3f4a5b6c7`，密钥严格按 `tenant_id` 隔离。
- 手动全网发现、每日定时发现和地区来源建议都会实时解析当前租户密钥。
- 组织未配置时沿用部署级 `BAIDU_SEARCH_API_KEY`；百度没有有效密钥或调用失败时继续按原策略回落 Bing。
- 租户自有 Key 会强制启用百度作为主搜索提供方，即使部署级 provider 被设为 Bing。
- 相同关键词的候选缓存不再跨租户共享，避免使用甲组织 Key 搜出的结果或额度服务乙组织。

## 验证

- `python -m compileall -q app core alembic/versions`：通过。
- 定向后端测试：33 passed。
- CI 等价后端套件：405 passed / 7 skipped。
- `python -m alembic heads`：`d2e3f4a5b6c7 (head)`，单 head。
- 前端 `yarn lint`：0 errors，30 条存量 warnings。
- 前端 `yarn build`：通过。
- `git diff --check`：通过。

## 部署步骤

1. 部署代码后运行 `alembic upgrade head`。
2. 重建 `policy-api` 与 `policy-ui`。
3. 使用组织 owner/admin 打开“设置 → 赛事搜索”，填入百度千帆 API Key 并保存。
4. 重新打开设置，确认只显示“已配置（百度）（组织自定义）”，输入框不回显密钥。
5. 对该组织手动运行一个赛事关键词订阅，确认 run 的 `searched_count > 0`。

## 边界与风险

- 密钥与现有租户 LLM/Embedding 凭据一样以 JSONB 保存，API 和日志不回显；数据库管理员仍可读取数据库中的凭据。
- 本次未部署 `.222`，也未执行真实租户写入或真实百度计费调用。
- 当前空字符串语义与模型 API 一致：保留已有密钥；尚未提供“清除组织密钥并回落平台”的按钮。
