# 自助加入其他组织（已登录用户）

Issue：待创建
分支：`feat/self-join-org`（从 main 切，PR 待创建）
更新时间：2026-06-15

## 背景 / 目标

用户反馈：账号属于「重庆理工大学」，同时又是另一单位成员，想切换组织、否则以为得重新注册。
排查发现：组织切换器(`TenantSwitcher`)**早已存在**，列出 `status=ACTIVE` 的成员关系；但
**已登录用户无法自助申请加入第二个组织**——自助加入此前只在注册时(`mode=join`)有。本次补这个缺口。

## 已完成（TDD：先写 5 个 request_join 测试 RED → 实现 GREEN）

### 后端
- `MembershipService.request_join(user_id, tenant_id) -> MemberView`：建一条 pending 申请，
  与注册加入同源(都产 pending 成员关系)，但用户已存在、不创建个人工作区。规则：
  目标须为存在的**共享**组织(非个人工作区)→否则 `NotFoundError`；已 active→`ConflictError`(已是成员)；
  已 pending→`ConflictError`(待审批)；曾 disabled→复用原记录重新置 pending。
- 端点 `POST /members/join-requests` body `{tenant_id}`（`get_current_user`，**任意登录用户**，
  非 owner/admin）；返回 `MemberItem`。Schema `JoinOrgRequest`(tenant_id 非空)。
- 审批侧复用既有：目标组织 owner/admin 在「组织成员」待审批区 approve/reject。

### 前端
- `membershipApi.requestJoin(tenantId)` → `POST /members/join-requests`。
- 组件 `components/join-org-dialog.tsx`：搜索共享组织(防抖复用 `authApi.listOrgs`)+ 提交加入申请 + toast。
- `components/tenant-switcher.tsx`：**下拉改为始终可开**(原 `onlyOneTenant` 时禁用导致单组织用户无法进入)，
  底部加「＋ 加入其他组织」项(onSelect 用 setTimeout(0) 规避 Radix 菜单/弹窗焦点竞争)，挂 `JoinOrgDialog`。

## 接口

- `POST /members/join-requests`，body `{ "tenant_id": "..." }`，任意登录用户；返回新建/复用的 pending `MemberItem`。
- 无新表、无迁移（复用 `memberships` 表 + `MembershipStatus.PENDING`）。

## 验证

- 单测：`test_membership_service.py` 新增 5（创建 pending / 缺失或个人组织报错 / active 冲突 / pending 冲突 /
  disabled 复用），membership 全绿；全量 **79 passed**（74→79），仅 status 1 error(需真库)。
- `import app.main` OK；`/members/join-requests` 路由已注册(在 `/{membership_id}/...` 之前无冲突)。
- 前端 `tsc --noEmit` exit 0、`eslint`(改动文件) exit 0。

## 用户怎么用

1. 左下角组织名 → 下拉「＋ 加入其他组织」→ 搜索目标单位 → 申请加入。
2. 目标单位 owner/admin 在「组织成员」待审批区批准。
3. 批准后该组织出现在切换器，可直接切换。**全程不用新建账号。**

> 另一条零代码途径仍可用：目标单位 owner/admin 直接「按邮箱添加成员」把你加进去(直接 active)。

## 未完成 / 风险

- 没做「我发起的加入申请」列表(用户看不到自己 pending 状态)；MVP 暂不做，可后续加。
- 仍缺：所有权转移、最后一名 owner 保护细则(既有未完成项，未动)。
