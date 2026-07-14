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

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedItemType
from app.domain.models.policy import Policy
from app.domain.models.tenant_settings import FeishuNotifyConfig, TenantSettings
from app.infrastructure.external.notify.feishu_webhook import (
    FeishuWebhookNotifier,
    build_contest_daily_summary_message,
    build_contest_message,
    build_feed_contest_message,
    feishu_sign,
    make_contest_daily_summary_hook,
    make_contest_push_hook,
    make_tenant_contest_daily_summary_hook,
    make_tenant_contest_push_hook,
    make_tenant_feed_contest_push_hook,
    mask_webhook_url,
)
from tests.app.application.services._fakes import make_uow_factory


def _policy(
    url: str = "https://www.wnd.gov.cn/doc/1.shtml",
    title: str = "关于举办创新创业大赛的通知",
    deadline: date | None = None,
    source: str = "wnd-contest",
) -> Policy:
    return Policy(
        source=source, source_url=url, title=title, region="江苏省无锡市新吴区",
        publish_date=date(2026, 7, 1),
        apply_deadline=deadline,
        deadline_status="extracted" if deadline else "unknown",
    )


def _feed_contest(item_id: str = "feed-1") -> FeedItem:
    return FeedItem(
        id=item_id,
        tenant_id="tenant-a",
        type=FeedItemType.COMPETITION,
        policy_id="contest-1",
        title="matched contest",
        source_url="https://example.test/contest-1",
        region="Jiangsu",
        reasons=["profile match"],
        publish_date=date(2026, 7, 1),
    )


# ---------- 签名 ----------

def test_feishu_sign_matches_official_algorithm() -> None:
    secret = "test-secret"
    timestamp = "1720000000"
    expected = base64.b64encode(
        hmac.new(f"{timestamp}\n{secret}".encode("utf-8"), digestmod=hashlib.sha256).digest()
    ).decode("utf-8")

    assert feishu_sign(secret, timestamp) == expected


# ---------- 消息构造(交互卡片) ----------

def test_build_contest_message_is_interactive_card_with_link_and_countdown() -> None:
    msg = build_contest_message(
        [_policy(deadline=date(2026, 7, 31))],
        source_name="无锡新吴区·大赛通知",
        today=date(2026, 7, 1),
    )

    assert msg["msg_type"] == "interactive"
    card = msg["card"]
    assert "1" in card["header"]["title"]["content"]  # 标题含条数
    flat = json.dumps(card["elements"], ensure_ascii=False)
    assert "创新创业大赛" in flat
    assert "https://www.wnd.gov.cn/doc/1.shtml" in flat  # 标题带原文链接
    assert "07-31" in flat  # 报名截止(MM-DD)
    assert "还剩 30 天" in flat  # 倒计时 = 7/31 - 7/1
    assert "无锡新吴区·大赛通知" in flat  # 来源名(note)


def test_build_contest_message_without_deadline_shows_no_countdown() -> None:
    msg = build_contest_message([_policy()], source_name="src", today=date(2026, 7, 1))
    flat = json.dumps(msg["card"]["elements"], ensure_ascii=False)

    assert "还剩" not in flat  # 无截止不编造倒计时
    assert "报名截止" not in flat
    assert "🗓 发布 07-01" in flat  # 回落展示发布日期


def test_build_contest_message_urgent_deadline_reddens_header() -> None:
    """任一赛事临近(≤3天)截止→卡片头转红；较缓(≤14天)转橙。"""
    urgent = build_contest_message(
        [_policy(deadline=date(2026, 7, 3))], today=date(2026, 7, 1),  # 2 天
    )
    soon = build_contest_message(
        [_policy(deadline=date(2026, 7, 10))], today=date(2026, 7, 1),  # 9 天
    )
    normal = build_contest_message([_policy()], today=date(2026, 7, 1))  # 无截止

    assert urgent["card"]["header"]["template"] == "red"
    assert soon["card"]["header"]["template"] == "orange"
    assert normal["card"]["header"]["template"] == "blue"


def test_build_contest_message_button_links_to_contest_center_when_base_url_set() -> None:
    with_btn = build_contest_message([_policy()], web_base_url="http://host:8088/")
    without = build_contest_message([_policy()])

    flat = json.dumps(with_btn["card"]["elements"], ensure_ascii=False)
    assert "打开赛事中心" in flat
    assert "http://host:8088/contests" in flat
    assert "打开赛事中心" not in json.dumps(without["card"]["elements"], ensure_ascii=False)


def test_build_contest_message_caps_items() -> None:
    """单条消息最多列 10 条，避免首次全量入库刷爆群。"""
    policies = [_policy(url=f"https://x/{i}.html", title=f"大赛{i}") for i in range(15)]
    msg = build_contest_message(policies, source_name="src")

    card = msg["card"]
    assert "15" in card["header"]["title"]["content"]  # 标题仍报真实总数
    flat = json.dumps(card["elements"], ensure_ascii=False)
    assert flat.count("https://x/") == 10


def test_build_feed_contest_message_has_ignore_link_and_feed_link() -> None:
    msg = build_feed_contest_message(
        [_feed_contest("feed-42")], web_base_url="http://host:8088/", today=date(2026, 7, 1),
    )

    flat = json.dumps(msg["card"]["elements"], ensure_ascii=False)
    assert "matched contest" in flat
    assert "http://host:8088/feed?ignore=feed-42" in flat
    assert "http://host:8088/feed" in flat


def test_build_daily_summary_sends_heartbeat_when_no_matches() -> None:
    msg = build_contest_daily_summary_message(
        [],
        new_count=0,
        web_base_url="http://host:8088",
        today=date(2026, 7, 10),
    )

    assert msg["msg_type"] == "interactive"
    card = msg["card"]
    assert "0 条可参赛" in card["header"]["title"]["content"]
    flat = json.dumps(card["elements"], ensure_ascii=False)
    assert "今日新增 **0** 条" in flat
    assert "今天没有发现匹配你关注地区的可参赛赛事" in flat
    assert "http://host:8088/contests" in flat


def test_build_daily_summary_counts_active_and_urgent_only() -> None:
    active = _policy(url="https://x/a", deadline=date(2026, 7, 20))
    expired = _policy(url="https://x/e", title="已过期大赛", deadline=date(2026, 7, 1))

    msg = build_contest_daily_summary_message(
        [active, expired],
        new_count=1,
        today=date(2026, 7, 10),
    )

    flat = json.dumps(msg["card"]["elements"], ensure_ascii=False)
    assert "今日新增 **1** 条" in flat
    assert "当前匹配 **1** 条可参赛赛事" in flat
    assert "14 天内截止" in flat
    assert "已过期大赛" not in flat


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

def _tenant_settings(tenant_id: str, url: str, secret: str = "") -> TenantSettings:
    return TenantSettings(
        tenant_id=tenant_id,
        feishu_config=FeishuNotifyConfig(webhook_url=url, secret=secret),
    )


def _fanout_env(handler):
    """组装两租户环境：A 关注江苏、B 关注重庆，各配独立 webhook。"""
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


def test_feed_push_hook_sends_only_new_matched_opportunities() -> None:
    sent: List[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={"code": 0})

    async def recompute(tenant_id: str) -> List[FeedItem]:
        return [_feed_contest()] if tenant_id == "tenant-a" else []

    hook = make_tenant_feed_contest_push_hook(
        make_uow_factory(
            tenant_settings={
                "tenant-a": _tenant_settings("tenant-a", "https://hook/a"),
                "tenant-b": _tenant_settings("tenant-b", "https://hook/b"),
            },
        ),
        recompute,
        transport=httpx.MockTransport(handler),
        web_base_url="http://host:8088",
    )
    policy = _policy().model_copy(update={"item_type": "competition"})

    asyncio.run(hook("wnd-contest", [policy]))

    assert [url for url, _ in sent] == ["https://hook/a"]
    flat = json.dumps(sent[0][1], ensure_ascii=False)
    assert "feed?ignore=feed-1" in flat


# ---------- 每日赛事摘要(重爬后固定心跳) ----------

def test_tenant_daily_summary_pushes_even_when_region_has_no_matches() -> None:
    """每日摘要是心跳：关注地区无赛事的租户也会收到"0条"摘要。"""
    sent: List[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={"code": 0})

    uow_factory = make_uow_factory(
        tenant_settings={
            "tenant-a": _tenant_settings("tenant-a", "https://hook/a"),
            "tenant-b": _tenant_settings("tenant-b", "https://hook/b"),
        },
        enterprise_profiles={
            "tenant-a": EnterpriseProfile(tenant_id="tenant-a", contest_regions=["江苏省"]),
            "tenant-b": EnterpriseProfile(tenant_id="tenant-b", contest_regions=["重庆市"]),
        },
        policies={
            "https://js/1": _policy(url="https://js/1", title="江苏创新创业大赛"),
        },
    )
    hook = make_tenant_contest_daily_summary_hook(
        uow_factory,
        contest_source_names={"wnd-contest": "无锡新吴区·大赛通知"},
        transport=httpx.MockTransport(handler),
        web_base_url="http://host:8088",
    )

    asyncio.run(hook([{"source": "wnd-contest", "new": 0}]))

    assert [url for url, _ in sent] == ["https://hook/a", "https://hook/b"]
    flat_a = json.dumps(sent[0][1], ensure_ascii=False)
    flat_b = json.dumps(sent[1][1], ensure_ascii=False)
    assert "江苏创新创业大赛" in flat_a
    assert "1 条可参赛" in flat_a
    assert "0 条可参赛" in flat_b
    assert "今天没有发现匹配你关注地区的可参赛赛事" in flat_b


def test_tenant_daily_summary_one_failure_does_not_block_others() -> None:
    sent: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://hook/a":
            raise httpx.ConnectError("boom")
        sent.append(str(request.url))
        return httpx.Response(200, json={"code": 0})

    uow_factory = make_uow_factory(
        tenant_settings={
            "tenant-a": _tenant_settings("tenant-a", "https://hook/a"),
            "tenant-b": _tenant_settings("tenant-b", "https://hook/b"),
        },
        policies={
            "https://js/1": _policy(url="https://js/1", title="江苏创新创业大赛"),
        },
    )
    hook = make_tenant_contest_daily_summary_hook(
        uow_factory,
        contest_source_names={"wnd-contest": "无锡新吴区·大赛通知"},
        transport=httpx.MockTransport(handler),
    )

    asyncio.run(hook([{"source": "wnd-contest", "new": 2}]))

    assert sent == ["https://hook/b"]


def test_deploy_level_daily_summary_uses_all_contests() -> None:
    sent: List[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0})

    uow_factory = make_uow_factory(
        policies={
            "https://js/1": _policy(url="https://js/1", title="江苏创新创业大赛"),
            "https://normal/1": _policy(
                url="https://normal/1", title="普通政策", source="wnd",
            ),
        },
    )
    hook = make_contest_daily_summary_hook(
        _notifier(handler),
        uow_factory,
        contest_source_names={"wnd-contest": "无锡新吴区·大赛通知"},
    )

    asyncio.run(hook([{"source": "wnd-contest", "new": 1}, {"source": "wnd", "new": 9}]))

    assert len(sent) == 1
    flat = json.dumps(sent[0], ensure_ascii=False)
    assert "今日新增 **1** 条" in flat
    assert "江苏创新创业大赛" in flat
    assert "普通政策" not in flat


# ---------- webhook URL 脱敏 ----------

def test_mask_webhook_url_hides_token() -> None:
    masked = mask_webhook_url("https://open.feishu.cn/open-apis/bot/v2/hook/abcd1234-ef56-7890-abcd")

    assert "abcd1234-ef56-7890-abcd" not in masked
    assert masked.endswith("abcd")  # 保留尾部便于辨认
    assert masked.startswith("https://open.feishu.cn/")


def test_mask_webhook_url_short_token_fully_masked() -> None:
    masked = mask_webhook_url("https://hook/ab")

    assert "ab" not in masked.rsplit("/", 1)[-1].replace("****", "")
