"""飞书群自定义机器人 webhook 通知（新赛事即推）。

轻量推送通道：建群 → 添加"自定义机器人" → 得 webhook URL(可选开启签名校验得 secret)，
经 env `FEISHU_WEBHOOK_URL` / `FEISHU_WEBHOOK_SECRET` 配置，不落代码。

组成：
- `feishu_sign` / `build_contest_message`：纯函数(签名、赛事富文本消息构造)；
- `FeishuWebhookNotifier.send`：httpx POST，best-effort(任何失败只记 warning 返回 False)；
- `make_contest_push_hook`：把通知器包装成 PolicyIngestService.on_new_policies 回调，
  仅赛事来源(competition_source_keys)触发推送，政策来源入库不打扰群。
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Awaitable, Callable, Dict, List, Optional

import httpx

from app.domain.models.policy import Policy

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
