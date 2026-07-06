"""飞书群自定义机器人 webhook 通知单测：签名/消息构造纯函数 + 发送 best-effort。

发送用 httpx.MockTransport 注入，不触网。签名算法按飞书官方规范：
string_to_sign = f"{timestamp}\n{secret}" 作 HMAC-SHA256 的 key、消息体为空，结果 base64。
"""

import asyncio
import base64
import hashlib
import hmac
import json
from datetime import date
from typing import List

import httpx

from app.domain.models.policy import Policy
from app.infrastructure.external.notify.feishu_webhook import (
    FeishuWebhookNotifier,
    build_contest_message,
    feishu_sign,
    make_contest_push_hook,
)


def _policy(
    url: str = "https://www.wnd.gov.cn/doc/1.shtml",
    title: str = "关于举办创新创业大赛的通知",
    deadline: date | None = None,
) -> Policy:
    return Policy(
        source_url=url, title=title, region="江苏省无锡市新吴区",
        publish_date=date(2026, 7, 1),
        apply_deadline=deadline,
        deadline_status="extracted" if deadline else "unknown",
    )


# ---------- 签名 ----------

def test_feishu_sign_matches_official_algorithm() -> None:
    secret = "test-secret"
    timestamp = "1720000000"
    expected = base64.b64encode(
        hmac.new(f"{timestamp}\n{secret}".encode("utf-8"), digestmod=hashlib.sha256).digest()
    ).decode("utf-8")

    assert feishu_sign(secret, timestamp) == expected


# ---------- 消息构造 ----------

def test_build_contest_message_is_post_with_title_link_and_deadline() -> None:
    msg = build_contest_message(
        [_policy(deadline=date(2026, 7, 31))], source_name="无锡新吴区·大赛通知",
    )

    assert msg["msg_type"] == "post"
    post = msg["content"]["post"]["zh_cn"]
    assert "1" in post["title"]  # 标题含条数
    flat = json.dumps(post["content"], ensure_ascii=False)
    assert "创新创业大赛" in flat
    assert "https://www.wnd.gov.cn/doc/1.shtml" in flat
    assert "2026-07-31" in flat  # 报名截止
    assert "无锡新吴区·大赛通知" in flat  # 来源名


def test_build_contest_message_without_deadline_omits_deadline_text() -> None:
    msg = build_contest_message([_policy()], source_name="src")
    flat = json.dumps(msg["content"]["post"]["zh_cn"]["content"], ensure_ascii=False)

    assert "截止" not in flat


def test_build_contest_message_caps_items() -> None:
    """单条消息最多列 10 条，避免首次全量入库刷爆群。"""
    policies = [_policy(url=f"https://x/{i}.html", title=f"大赛{i}") for i in range(15)]
    msg = build_contest_message(policies, source_name="src")

    post = msg["content"]["post"]["zh_cn"]
    assert "15" in post["title"]  # 标题仍报真实总数
    flat = json.dumps(post["content"], ensure_ascii=False)
    assert flat.count("https://x/") == 10


# ---------- 发送 ----------

def _notifier(handler, secret: str = "") -> FeishuWebhookNotifier:
    return FeishuWebhookNotifier(
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/fake",
        secret=secret,
        transport=httpx.MockTransport(handler),
    )


def test_send_posts_payload_and_returns_true_on_code_0() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "msg": "success"})

    ok = asyncio.run(_notifier(handler).send({"msg_type": "text", "content": {"text": "hi"}}))

    assert ok is True
    assert captured["json"]["msg_type"] == "text"


def test_send_adds_timestamp_and_sign_when_secret_configured() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0})

    asyncio.run(_notifier(handler, secret="s").send({"msg_type": "text", "content": {}}))

    body = captured["json"]
    assert body["sign"] == feishu_sign("s", body["timestamp"])


def test_send_returns_false_on_feishu_error_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 19021, "msg": "sign match fail"})

    assert asyncio.run(_notifier(handler).send({"msg_type": "text"})) is False


def test_send_swallows_network_error_and_returns_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    assert asyncio.run(_notifier(handler).send({"msg_type": "text"})) is False


# ---------- 赛事推送钩子(接 on_new_policies) ----------

def test_contest_push_hook_only_pushes_contest_sources() -> None:
    sent: List[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0})

    hook = make_contest_push_hook(
        _notifier(handler),
        contest_source_names={"wnd-contest": "无锡新吴区·大赛通知"},
    )

    asyncio.run(hook("wnd", [_policy()]))  # 政策来源：不推
    assert sent == []

    asyncio.run(hook("wnd-contest", [_policy()]))  # 赛事来源：推
    assert len(sent) == 1
    flat = json.dumps(sent[0], ensure_ascii=False)
    assert "无锡新吴区·大赛通知" in flat
