"""政策申报截止日期抽取器（主线⑤ 主动提醒的数据来源）。

申报截止日期只埋在政策正文自然语言里、格式多变且不是每篇都有，源站不给结构化字段。
本模块用 LLM 从正文抽取，并遵循**"待核对"纪律**：
- 只抽正文中**明确写出**的申报截止日期，无法确定一律判 unknown，**绝不猜测/编造**；
- 抽到明确日期 → extracted；常年受理/无固定截止 → rolling；未识别 → unknown；
- 一切异常(无 LLM/调用失败/解析失败/脏数据) 安全回退 unknown，绝不阻断②入库。

纯函数(消息构造 + 结果解析)与网络 I/O(extract_deadline) 分离，便于离线单测。
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, NamedTuple, Optional, Protocol

logger = logging.getLogger(__name__)

# 截止日期通常在正文开头(适用对象/申报时间段)或结尾(附则/联系方式前)，
# 故首尾各取一段拼接送审，既覆盖常见位置又控制 token 成本。
_HEAD_CHARS = 4000
_TAIL_CHARS = 2000

_VALID_STATUSES = {"extracted", "rolling", "unknown"}

_SYSTEM_PROMPT = (
    "你是政策申报信息抽取助手。只根据用户给出的政策正文，抽取『申报截止日期』。"
    "严格遵守：只抽正文中明确写出的截止日期，无法确定时一律判定为未识别，绝不猜测或编造日期。"
    "仅输出 JSON，不要任何额外解释。"
)

_USER_TEMPLATE = (
    "政策标题：{title}\n\n"
    "政策正文（可能被截断）：\n{body}\n\n"
    "请判断该政策的申报截止情况，输出如下 JSON：\n"
    "{{\n"
    '  "found": true/false,            // 是否在正文中明确写出了申报截止日期\n'
    '  "deadline": "YYYY-MM-DD"|null,  // found=true 时填明确的截止日期，否则 null\n'
    '  "rolling": true/false,          // 是否为常年受理/长期有效/无固定截止\n'
    '  "window": "原文中关于申报时间/批次的简短描述，无则空字符串"\n'
    "}}\n"
    "规则：只要无法从正文确定一个明确的截止日期，found 必须为 false、deadline 必须为 null；"
    "不要根据发文日期推算截止日期。"
)


class DeadlineResult(NamedTuple):
    """抽取结果：截止日期 + 原文窗口描述 + 状态(extracted/rolling/unknown)。"""
    deadline: Optional[date]
    window_text: str
    status: str


_UNKNOWN = DeadlineResult(deadline=None, window_text="", status="unknown")


class _LLM(Protocol):
    """抽取所需的最小 LLM 能力(由 OpenAILLM 实现)。"""

    async def invoke(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        response_format: Dict[str, Any] = None,
        tool_choice: str = None,
    ) -> Dict[str, Any]:
        ...


def _truncate_body(body_text: str) -> str:
    """正文超长时取首尾两段拼接(截止日期常见位置)，避免整篇送审的 token 成本。"""
    text = (body_text or "").strip()
    if len(text) <= _HEAD_CHARS + _TAIL_CHARS:
        return text
    return f"{text[:_HEAD_CHARS]}\n…（正文中段略）…\n{text[-_TAIL_CHARS:]}"


def build_extraction_messages(title: str, body_text: str) -> List[Dict[str, str]]:
    """构造抽取用的消息列表(系统约束 + 标题/正文)。纯函数，便于单测。"""
    user = _USER_TEMPLATE.format(title=(title or "").strip(), body=_truncate_body(body_text))
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _coerce_date(raw: Any) -> Optional[date]:
    """将 'YYYY-MM-DD'(允许带时间后缀)安全解析为 date，非法返回 None。"""
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def parse_extraction_result(content: str) -> DeadlineResult:
    """解析 LLM 返回的 JSON 字符串为 DeadlineResult。

    "待核对"纪律落点：found 为真且能解析出合法日期才记 extracted；否则看 rolling 记
    rolling，再否则 unknown。任何解析异常/脏数据一律回退 unknown，绝不编造日期。
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        logger.warning("截止日期抽取结果非合法 JSON，回退 unknown: %r", content[:200] if content else content)
        return _UNKNOWN
    if not isinstance(data, dict):
        return _UNKNOWN

    window = data.get("window")
    window_text = window.strip() if isinstance(window, str) else ""

    if data.get("found") is True:
        deadline = _coerce_date(data.get("deadline"))
        if deadline is not None:
            return DeadlineResult(deadline=deadline, window_text=window_text, status="extracted")
        # 声称找到却给不出合法日期 → 不采信，按未识别处理(绝不编造)
        logger.warning("抽取声称 found 但 deadline 非法，回退 unknown: %r", data.get("deadline"))

    if data.get("rolling") is True:
        return DeadlineResult(deadline=None, window_text=window_text or "常年受理/无固定截止", status="rolling")

    return DeadlineResult(deadline=None, window_text=window_text, status="unknown")


async def extract_deadline(llm: Optional[_LLM], title: str, body_text: str) -> DeadlineResult:
    """用 LLM 从政策正文抽取申报截止情况。无 LLM/无正文/任何异常均安全回退 unknown。"""
    if llm is None or not (body_text or "").strip():
        return _UNKNOWN
    try:
        messages = build_extraction_messages(title, body_text)
        response = await llm.invoke(messages, response_format={"type": "json_object"})
        content = (response or {}).get("content") or ""
        return parse_extraction_result(content)
    except Exception as e:  # noqa: BLE001 — 抽取为 best-effort，绝不阻断入库
        logger.warning("截止日期抽取失败，回退 unknown: %s: %s", type(e).__name__, e)
        return _UNKNOWN
