"""飞书群自定义机器人 webhook 通知（新赛事即推）。

轻量推送通道：建群 → 添加"自定义机器人" → 得 webhook URL(可选开启签名校验得 secret)。
配置两级：组织级(设置页配置，存 tenant_settings.feishu_config，按租户扇出+按参赛关注
地区过滤) + 部署级(env `FEISHU_WEBHOOK_URL`/`FEISHU_WEBHOOK_SECRET`，全量不过滤，兜底)。
通知分两类：新赛事首次入库即推；每日重爬后固定推一条赛事摘要，哪怕无新增也给用户一个
"今天已盯过"的心跳。

组成：
- `feishu_sign` / `build_contest_message` / `mask_webhook_url`：纯函数(签名、赛事交互卡片
  构造[临期变色+报名倒计时+打开工作台按钮]、URL 脱敏回显)；
- `FeishuWebhookNotifier.send`：httpx POST，best-effort(任何失败只记 warning 返回 False)；
- `make_contest_push_hook`：单 webhook(部署级 env)回调，仅赛事来源触发；
- `make_tenant_contest_push_hook`：租户级扇出回调——遍历配置了 webhook 的租户，
  按各租户企业档案的参赛关注地区过滤新赛事后分别推送。
- `make_contest_daily_summary_hook` / `make_tenant_contest_daily_summary_hook`：重爬后每日摘要。
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import time
from datetime import date
from typing import Awaitable, Callable, Dict, List, Optional

import httpx

from app.domain.models.policy import Policy
from app.domain.models.tenant_settings import TenantSettings
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.policy_matcher import contest_region_matches

logger = logging.getLogger(__name__)

# 单条消息最多列出的赛事数：首次全量入库可能一次新增几十条，只推最新一批避免刷屏
_MAX_ITEMS_PER_MESSAGE = 10
_REQUEST_TIMEOUT = 10  # 秒

# 报名临期阈值(天)：任一赛事 ≤3 天卡片头转红、≤14 天转橙，与工作台 Feed 徽章口径一致
_URGENT_DAYS = 3
_SOON_DAYS = 14


def feishu_sign(secret: str, timestamp: str) -> str:
    """按飞书官方规范计算签名：以 '{timestamp}\\n{secret}' 为 HMAC-SHA256 key、
    消息体为空，摘要 base64 编码。"""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


# URL 尾段(机器人 token)脱敏时保留的明文尾部长度：够辨认是哪个机器人、不够被冒用
_MASK_KEEP_TAIL = 4


def mask_webhook_url(url: str) -> str:
    """脱敏 webhook URL 供前端回显：URL 尾段(机器人 token)只保留末 4 位。

    webhook URL 即推送凭据(拿到即可向群发消息)，不能明文回显；只留尾部便于管理员
    辨认当前配置的是哪个机器人。尾段过短(≤4位)则全遮。
    """
    base, _, token = url.rstrip("/").rpartition("/")
    if len(token) > _MASK_KEEP_TAIL:
        token = "****" + token[-_MASK_KEEP_TAIL:]
    else:
        token = "****"
    return f"{base}/{token}" if base else token


def _escape_md(text: str) -> str:
    """转义 lark_md 链接文字里的方括号，避免标题含 [] 时截断链接。"""
    return text.replace("[", "\\[").replace("]", "\\]")


def _days_left(policy: Policy, today: date) -> Optional[int]:
    """抽取到明确截止日期时返回剩余天数(可为负=已过期)，否则 None。"""
    if policy.deadline_status == "extracted" and policy.apply_deadline:
        return (policy.apply_deadline - today).days
    return None


def _deadline_hint(policy: Policy, today: date) -> str:
    """一条赛事的时间线提示：优先报名截止倒计时，否则常年受理/发布日期。"""
    days = _days_left(policy, today)
    if days is not None:
        md = policy.apply_deadline.strftime("%m-%d")
        if days < 0:
            return f"⏰ 报名已截止（{md}）"
        if days == 0:
            return f"⏰ 今天截止（{md}）"
        return f"⏰ 报名截止 {md}（还剩 {days} 天）"
    if policy.deadline_status == "rolling":
        return "⏰ 常年受理"
    if policy.publish_date:
        return f"🗓 发布 {policy.publish_date.strftime('%m-%d')}"
    return ""


def _is_active_contest(policy: Policy, today: date) -> bool:
    """赛事是否仍可作为机会展示：明确截止且已过期则排除；未知/常年保留。"""
    days = _days_left(policy, today)
    return days is None or days >= 0


def _sort_contests_for_summary(policies: List[Policy], today: date) -> List[Policy]:
    """摘要优先展示临期，其次按发布日期/创建时间新旧排序。"""
    def key(policy: Policy):
        days = _days_left(policy, today)
        deadline_rank = days if days is not None and days >= 0 else 9999
        return (
            deadline_rank,
            -(policy.publish_date.toordinal() if policy.publish_date else 0),
            -policy.created_at.timestamp(),
        )

    return sorted(policies, key=key)


def _header_template(policies: List[Policy], today: date) -> str:
    """按最紧迫的报名截止决定卡片头颜色：≤3天红、≤14天橙、否则蓝(常规新机会)。"""
    urgent = soon = False
    for p in policies:
        days = _days_left(p, today)
        if days is None or days < 0:
            continue
        if days <= _URGENT_DAYS:
            urgent = True
        elif days <= _SOON_DAYS:
            soon = True
    if urgent:
        return "red"
    if soon:
        return "orange"
    return "blue"


def _feed_url(web_base_url: str) -> str:
    """工作台赛事页地址(卡片按钮跳转)。"""
    return web_base_url.rstrip("/") + "/feed"


def build_contest_message(
    policies: List[Policy],
    source_name: str = "",
    web_base_url: str = "",
    today: Optional[date] = None,
) -> dict:
    """把一批新入库的赛事通知组装成飞书交互卡片(interactive)。

    卡片头按最紧迫的报名截止变色(临期红/橙)；每条一块：加粗可点标题 + 📍地区 +
    报名截止倒计时(⑤抽取到才有，"还剩 N 天")。配了 web_base_url 时底部加「打开工作台」
    按钮直达赛事页。超过上限只列前 N 条，标题仍报真实总数；截止以原文为准(note 声明)。
    """
    today = today or date.today()
    shown = policies[:_MAX_ITEMS_PER_MESSAGE]

    elements: List[dict] = []
    for i, p in enumerate(shown):
        title = _escape_md(p.title)
        title_line = f"**[{title}]({p.source_url})**" if p.source_url else f"**{title}**"
        meta = [part for part in (
            f"📍 {p.region}" if p.region else "",
            _deadline_hint(p, today),
        ) if part]
        content = title_line + (f"\n{'  ·  '.join(meta)}" if meta else "")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": content}})
        if i < len(shown) - 1:
            elements.append({"tag": "hr"})

    if len(policies) > _MAX_ITEMS_PER_MESSAGE:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md",
            "content": f"…共 **{len(policies)}** 条，其余请到工作台「赛事机会」查看"}})

    if web_base_url:
        elements.append({"tag": "action", "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "打开工作台查看全部"},
            "url": _feed_url(web_base_url),
            "type": "primary",
        }]})

    note_parts = ["报名信息以官方原文为准"]
    if source_name:
        note_parts.append(f"来源 {source_name}")
    note_parts.append("依你的参赛关注地区筛选")
    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": " · ".join(note_parts)}]})

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": _header_template(shown, today),
                "title": {"tag": "plain_text", "content": f"🏆 新赛事机会 · {len(policies)} 条"},
            },
            "elements": elements,
        },
    }


def build_contest_daily_summary_message(
    policies: List[Policy],
    new_count: int = 0,
    web_base_url: str = "",
    today: Optional[date] = None,
) -> dict:
    """每日赛事摘要卡片：固定心跳，展示新增数、当前可参赛数、临期数与重点条目。

    与"新赛事即推"不同，摘要即便无新增也发送，避免用户误以为定时任务没跑。policies
    应传入已按租户关注地区过滤后的候选；函数内部再排除明确已过期赛事。
    """
    today = today or date.today()
    active = [p for p in policies if _is_active_contest(p, today)]
    sorted_active = _sort_contests_for_summary(active, today)
    urgent_count = sum(
        1
        for p in active
        if (days := _days_left(p, today)) is not None and 0 <= days <= _SOON_DAYS
    )
    shown = sorted_active[:_MAX_ITEMS_PER_MESSAGE]

    elements: List[dict] = [{
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"今日新增 **{new_count}** 条；当前匹配 **{len(active)}** 条可参赛赛事；"
                f"其中 **{urgent_count}** 条 14 天内截止。"
            ),
        },
    }]

    if shown:
        elements.append({"tag": "hr"})
        for i, p in enumerate(shown):
            title = _escape_md(p.title)
            title_line = f"**[{title}]({p.source_url})**" if p.source_url else f"**{title}**"
            meta = [part for part in (
                f"📍 {p.region}" if p.region else "",
                _deadline_hint(p, today),
            ) if part]
            content = title_line + (f"\n{'  ·  '.join(meta)}" if meta else "")
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": content}})
            if i < len(shown) - 1:
                elements.append({"tag": "hr"})
        if len(active) > _MAX_ITEMS_PER_MESSAGE:
            elements.append({"tag": "hr"})
            elements.append({"tag": "div", "text": {"tag": "lark_md",
                "content": f"…还有 **{len(active) - _MAX_ITEMS_PER_MESSAGE}** 条，请到工作台查看"}})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md",
            "content": "今天没有发现匹配你关注地区的可参赛赛事，我会明天继续盯。"}})

    if web_base_url:
        elements.append({"tag": "action", "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "打开工作台查看赛事"},
            "url": _feed_url(web_base_url),
            "type": "primary",
        }]})

    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": "每日自动摘要 · 报名信息以官方原文为准 · 依你的参赛关注地区筛选"}]})

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": _header_template(active, today),
                "title": {
                    "tag": "plain_text",
                    "content": f"📬 每日赛事摘要 · {len(active)} 条可参赛",
                },
            },
            "elements": elements,
        },
    }


def build_test_message() -> dict:
    """联调用测试消息(设置页"发送测试"按钮)：验证 webhook 地址与签名配置是否正确。"""
    return {
        "msg_type": "text",
        "content": {"text": "✅ PolicyManus 飞书推送联调成功：新赛事机会将推送到本群。"},
    }


class FeishuWebhookNotifier:
    """飞书自定义机器人 webhook 发送器(best-effort，任何失败不冒泡)。"""

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        timeout: float = _REQUEST_TIMEOUT,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._secret = secret
        self._timeout = timeout
        self._transport = transport  # 测试注入 MockTransport；生产 None 走真实网络

    async def send(self, message: dict) -> bool:
        """POST 消息到 webhook；配置了 secret 时附时间戳+签名。成功(code=0)返回 True。"""
        payload = dict(message)
        if self._secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = feishu_sign(self._secret, timestamp)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport,
            ) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:  # noqa: BLE001 — 推送为增强，绝不影响调用方主流程
            logger.warning("飞书 webhook 推送失败: %s: %s", type(e).__name__, e)
            return False

        # 兼容两代返回：{"code":0,...} / {"StatusCode":0,...}
        code = data.get("code", data.get("StatusCode"))
        if code != 0:
            logger.warning("飞书 webhook 返回错误: code=%s msg=%s", code, data.get("msg"))
            return False
        return True


def make_contest_push_hook(
    notifier: FeishuWebhookNotifier,
    contest_source_names: Dict[str, str],
    web_base_url: str = "",
) -> Callable[[str, List[Policy]], Awaitable[None]]:
    """包装成 PolicyIngestService.on_new_policies 回调：仅赛事来源的新增触发推送。

    contest_source_names: 赛事来源 key → 展示名(registry 登记名，进消息尾部溯源)。
    web_base_url: 前端基地址，非空时卡片带「打开工作台」按钮。
    """

    async def push_new_contests(source: str, new_policies: List[Policy]) -> None:
        source_name = contest_source_names.get(source)
        if source_name is None:  # 非赛事来源(普通政策入库)不打扰群
            return
        message = build_contest_message(
            new_policies, source_name=source_name, web_base_url=web_base_url,
        )
        await notifier.send(message)

    return push_new_contests


def _daily_new_count(summaries: Optional[List[dict]], contest_sources: set[str]) -> int:
    """从本轮重爬 summary 中汇总赛事来源新增数。"""
    if not summaries:
        return 0
    total = 0
    for summary in summaries:
        if summary.get("source") not in contest_sources:
            continue
        try:
            total += int(summary.get("new", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def make_contest_daily_summary_hook(
    notifier: FeishuWebhookNotifier,
    uow_factory: Callable[[], IUnitOfWork],
    contest_source_names: Dict[str, str],
    web_base_url: str = "",
) -> Callable[[List[dict]], Awaitable[None]]:
    """部署级每日赛事摘要：发送全量赛事视角，不按租户地区过滤。"""
    contest_sources = set(contest_source_names)

    async def push_daily_summary(summaries: List[dict]) -> None:
        async with uow_factory() as uow:
            policies = await uow.policy.list_by_sources(list(contest_sources), limit=200)
        message = build_contest_daily_summary_message(
            policies,
            new_count=_daily_new_count(summaries, contest_sources),
            web_base_url=web_base_url,
        )
        await notifier.send(message)

    return push_daily_summary


def make_tenant_contest_push_hook(
    uow_factory: Callable[[], IUnitOfWork],
    contest_source_names: Dict[str, str],
    transport: Optional[httpx.AsyncBaseTransport] = None,
    web_base_url: str = "",
) -> Callable[[str, List[Policy]], Awaitable[None]]:
    """租户级扇出版 on_new_policies 回调：新赛事按各组织配置的 webhook 分别推送。

    每个配置了飞书 webhook 的租户各推一条，且按其企业档案的"参赛关注地区"过滤
    (contest_region_matches 层级前缀双向命中；未建档/未选地区=不限)。单租户推送失败
    (send 已 best-effort)或异常不影响其他租户。transport 供测试注入 MockTransport。
    """

    async def push_new_contests(source: str, new_policies: List[Policy]) -> None:
        source_name = contest_source_names.get(source)
        if source_name is None:  # 非赛事来源(普通政策入库)不打扰任何群
            return

        async with uow_factory() as uow:
            configured = await uow.tenant_settings.list_feishu_configured()
            profiles = {
                ts.tenant_id: await uow.enterprise_profile.get_by_tenant(ts.tenant_id)
                for ts in configured
            }

        async def push_one(ts: TenantSettings) -> None:
            config = ts.feishu_config
            if config is None or not config.webhook_url.strip():
                return
            profile = profiles.get(ts.tenant_id)
            regions = profile.contest_regions if profile else []
            matched = [p for p in new_policies if contest_region_matches(p.region, regions)]
            if not matched:
                return
            try:
                notifier = FeishuWebhookNotifier(
                    webhook_url=config.webhook_url,
                    secret=config.secret,
                    transport=transport,
                )
                await notifier.send(build_contest_message(
                    matched, source_name=source_name, web_base_url=web_base_url,
                ))
            except Exception as e:  # noqa: BLE001 — 单租户失败不拖累其他租户
                logger.warning(
                    "租户 %s 飞书推送异常: %s: %s", ts.tenant_id, type(e).__name__, e,
                )

        # 各租户 webhook 互相独立，并发发送；单个挂起(10s 超时)不阻塞整批入库任务
        await asyncio.gather(*(push_one(ts) for ts in configured))

    return push_new_contests


def make_tenant_contest_daily_summary_hook(
    uow_factory: Callable[[], IUnitOfWork],
    contest_source_names: Dict[str, str],
    transport: Optional[httpx.AsyncBaseTransport] = None,
    web_base_url: str = "",
) -> Callable[[List[dict]], Awaitable[None]]:
    """租户级每日赛事摘要：固定发送，按企业档案参赛关注地区过滤当前可参赛赛事。"""
    contest_sources = set(contest_source_names)

    async def push_daily_summary(summaries: List[dict]) -> None:
        async with uow_factory() as uow:
            configured = await uow.tenant_settings.list_feishu_configured()
            policies = await uow.policy.list_by_sources(list(contest_sources), limit=200)
            profiles = {
                ts.tenant_id: await uow.enterprise_profile.get_by_tenant(ts.tenant_id)
                for ts in configured
            }

        new_count = _daily_new_count(summaries, contest_sources)

        async def push_one(ts: TenantSettings) -> None:
            config = ts.feishu_config
            if config is None or not config.webhook_url.strip():
                return
            profile = profiles.get(ts.tenant_id)
            regions = profile.contest_regions if profile else []
            matched = [p for p in policies if contest_region_matches(p.region, regions)]
            try:
                notifier = FeishuWebhookNotifier(
                    webhook_url=config.webhook_url,
                    secret=config.secret,
                    transport=transport,
                )
                await notifier.send(build_contest_daily_summary_message(
                    matched, new_count=new_count, web_base_url=web_base_url,
                ))
            except Exception as e:  # noqa: BLE001 — 单租户失败不拖累其他租户
                logger.warning(
                    "租户 %s 飞书每日赛事摘要异常: %s: %s",
                    ts.tenant_id, type(e).__name__, e,
                )

        await asyncio.gather(*(push_one(ts) for ts in configured))

    return push_daily_summary
