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


# ---------- 租户级扇出推送(前端配 webhook + 按参赛关注地区过滤) ----------

def _tenant_settings(tenant_id: str, url: str, secret: str = "") -> "TenantSettings":
    from app.domain.models.tenant_settings import FeishuNotifyConfig, TenantSettings

    return TenantSettings(
        tenant_id=tenant_id,
        feishu_config=FeishuNotifyConfig(webhook_url=url, secret=secret),
    )


def _fanout_env(handler):
    """组装两租户环境：A 关注江苏、B 关注重庆，各配独立 webhook。"""
    from app.domain.models.enterprise_profile import EnterpriseProfile
    from tests.app.application.services._fakes import make_uow_factory

    uow_factory = make_uow_factory(
        tenant_settings={
            "tenant-a": _tenant_settings("tenant-a", "https://hook/a"),
            "tenant-b": _tenant_settings("tenant-b", "https://hook/b"),
        },
        enterprise_profiles={
            "tenant-a": EnterpriseProfile(tenant_id="tenant-a", contest_regions=["江苏省"]),
            "tenant-b": EnterpriseProfile(tenant_id="tenant-b", contest_regions=["重庆市"]),
        },
    )
    from app.infrastructure.external.notify.feishu_webhook import (
        make_tenant_contest_push_hook,
    )

    return make_tenant_contest_push_hook(
        uow_factory,
        contest_source_names={"wnd-contest": "无锡新吴区·大赛通知"},
        transport=httpx.MockTransport(handler),
    )


def test_tenant_fanout_filters_by_contest_regions() -> None:
    """江苏赛事只推给关注江苏的租户，关注重庆的租户不被打扰。"""
    sent: List[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={"code": 0})

    hook = _fanout_env(handler)
    asyncio.run(hook("wnd-contest", [_policy()]))  # region=江苏省无锡市新吴区

    assert [url for url, _ in sent] == ["https://hook/a"]


def test_tenant_fanout_without_profile_pushes_all() -> None:
    """配了 webhook 但没建档案(未选关注地区)=不限，全部推送。"""
    from tests.app.application.services._fakes import make_uow_factory
    from app.infrastructure.external.notify.feishu_webhook import (
        make_tenant_contest_push_hook,
    )

    sent: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(200, json={"code": 0})

    hook = make_tenant_contest_push_hook(
        make_uow_factory(
            tenant_settings={"tenant-c": _tenant_settings("tenant-c", "https://hook/c")},
        ),
        contest_source_names={"wnd-contest": "无锡新吴区·大赛通知"},
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(hook("wnd-contest", [_policy()]))

    assert sent == ["https://hook/c"]


def test_tenant_fanout_skips_non_contest_source() -> None:
    """普通政策来源入库不触发任何租户推送。"""
    sent: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(200, json={"code": 0})

    hook = _fanout_env(handler)
    asyncio.run(hook("wnd", [_policy()]))

    assert sent == []


def test_tenant_fanout_one_failure_does_not_block_others() -> None:
    """某租户 webhook 挂了(网络错误)不影响其他租户收到推送。"""
    sent: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "hook" and request.url.path == "/a":
            raise httpx.ConnectError("boom")
        sent.append(str(request.url))
        return httpx.Response(200, json={"code": 0})

    hook = _fanout_env(handler)
    # 两租户地区都命中：江苏赛事 + 重庆赛事各一条
    policies = [
        _policy(),
        _policy(url="https://cq/1.html", title="重庆创新创业大赛"),
    ]
    policies[1] = policies[1].model_copy(update={"region": "重庆市"})
    asyncio.run(hook("wnd-contest", policies))

    assert sent == ["https://hook/b"]


# ---------- webhook URL 脱敏 ----------

def test_mask_webhook_url_hides_token() -> None:
    from app.infrastructure.external.notify.feishu_webhook import mask_webhook_url

    masked = mask_webhook_url("https://open.feishu.cn/open-apis/bot/v2/hook/abcd1234-ef56-7890-abcd")

    assert "abcd1234-ef56-7890-abcd" not in masked
    assert masked.endswith("abcd")  # 保留尾部便于辨认
    assert masked.startswith("https://open.feishu.cn/")


def test_mask_webhook_url_short_token_fully_masked() -> None:
    from app.infrastructure.external.notify.feishu_webhook import mask_webhook_url

    masked = mask_webhook_url("https://hook/ab")

    assert "ab" not in masked.rsplit("/", 1)[-1].replace("****", "")
