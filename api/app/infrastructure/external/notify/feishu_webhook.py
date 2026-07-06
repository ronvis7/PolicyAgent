"""飞书群自定义机器人 webhook 通知（新赛事即推）。

轻量推送通道：建群 → 添加"自定义机器人" → 得 webhook URL(可选开启签名校验得 secret)。
配置两级：组织级(设置页配置，存 tenant_settings.feishu_config，按租户扇出+按参赛关注
地区过滤) + 部署级(env `FEISHU_WEBHOOK_URL`/`FEISHU_WEBHOOK_SECRET`，全量不过滤，兜底)。

组成：
- `feishu_sign` / `build_contest_message` / `mask_webhook_url`：纯函数(签名、赛事富文本
  消息构造、URL 脱敏回显)；
- `FeishuWebhookNotifier.send`：httpx POST，best-effort(任何失败只记 warning 返回 False)；
- `make_contest_push_hook`：单 webhook(部署级 env)回调，仅赛事来源触发；
- `make_tenant_contest_push_hook`：租户级扇出回调——遍历配置了 webhook 的租户，
  按各租户企业档案的参赛关注地区过滤新赛事后分别推送。
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import time
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


def build_contest_message(policies: List[Policy], source_name: str = "") -> dict:
    """把一批新入库的赛事通知组装成飞书富文本(post)消息。

    每条一行：标题(带原文链接) + 地区/发布日期/报名截止(⑤抽取到才带，以原文为准)。
    超过上限只列前 N 条，标题仍报真实总数。
    """
    lines: List[List[dict]] = []
    for p in policies[:_MAX_ITEMS_PER_MESSAGE]:
        meta_parts = [part for part in (
            p.region,
            f"发布 {p.publish_date}" if p.publish_date else "",
            f"报名截止 {p.apply_deadline}(以原文为准)"
            if p.deadline_status == "extracted" and p.apply_deadline else "",
        ) if part]
        line: List[dict] = [{"tag": "a", "text": p.title, "href": p.source_url}]
        if meta_parts:
            line.append({"tag": "text", "text": f"（{' | '.join(meta_parts)}）"})
        lines.append(line)

    if len(policies) > _MAX_ITEMS_PER_MESSAGE:
        lines.append([{
            "tag": "text",
            "text": f"…共 {len(policies)} 条，其余请到工作台「赛事机会」查看",
        }])
    if source_name:
        lines.append([{"tag": "text", "text": f"来源：{source_name}"}])

    return {
        "msg_type": "post",
        "content": {"post": {"zh_cn": {
            "title": f"🏆 新赛事机会 {len(policies)} 条",
            "content": lines,
        }}},
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
) -> Callable[[str, List[Policy]], Awaitable[None]]:
    """包装成 PolicyIngestService.on_new_policies 回调：仅赛事来源的新增触发推送。

    contest_source_names: 赛事来源 key → 展示名(registry 登记名，进消息尾部溯源)。
    """

    async def push_new_contests(source: str, new_policies: List[Policy]) -> None:
        source_name = contest_source_names.get(source)
        if source_name is None:  # 非赛事来源(普通政策入库)不打扰群
            return
        message = build_contest_message(new_policies, source_name=source_name)
        await notifier.send(message)

    return push_new_contests


def make_tenant_contest_push_hook(
    uow_factory: Callable[[], IUnitOfWork],
    contest_source_names: Dict[str, str],
    transport: Optional[httpx.AsyncBaseTransport] = None,
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
                await notifier.send(build_contest_message(matched, source_name=source_name))
            except Exception as e:  # noqa: BLE001 — 单租户失败不拖累其他租户
                logger.warning(
                    "租户 %s 飞书推送异常: %s: %s", ts.tenant_id, type(e).__name__, e,
                )

        # 各租户 webhook 互相独立，并发发送；单个挂起(10s 超时)不阻塞整批入库任务
        await asyncio.gather(*(push_one(ts) for ts in configured))

    return push_new_contests
