"""deadline_extractor 离线单测：prompt 构造 + 结果解析 + LLM 封装的"待核对"纪律。

重点验证"绝不编造"：found 为假/日期非法/JSON 损坏/异常一律回退 unknown，绝不臆造日期。
"""

import asyncio
import json
from datetime import date

from app.domain.services.deadline_extractor import (
    build_extraction_messages,
    extract_deadline,
    parse_extraction_result,
)


def test_build_messages_includes_title_and_body() -> None:
    messages = build_extraction_messages("高企申报通知", "请于2026-07-31前提交材料")
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "高企申报通知" in messages[1]["content"]
    assert "请于2026-07-31前提交材料" in messages[1]["content"]


def test_build_messages_truncates_long_body() -> None:
    body = "头" * 5000 + "尾巴截止2026-08-01" + "中" * 5000
    content = build_extraction_messages("t", body)[1]["content"]
    # 超长正文取首尾两段拼接，整体长度远小于原文
    assert "（正文中段略）" in content
    assert len(content) < len(body)


def test_parse_extracted_valid_date() -> None:
    result = parse_extraction_result(
        json.dumps({"found": True, "deadline": "2026-07-31", "rolling": False, "window": "7月底前"})
    )
    assert result.status == "extracted"
    assert result.deadline == date(2026, 7, 31)
    assert result.window_text == "7月底前"


def test_parse_found_false_is_unknown() -> None:
    result = parse_extraction_result(
        json.dumps({"found": False, "deadline": None, "rolling": False, "window": ""})
    )
    assert result.status == "unknown"
    assert result.deadline is None


def test_parse_rolling() -> None:
    result = parse_extraction_result(
        json.dumps({"found": False, "deadline": None, "rolling": True, "window": "常年受理"})
    )
    assert result.status == "rolling"
    assert result.deadline is None
    assert result.window_text == "常年受理"


def test_parse_found_but_illegal_date_does_not_fabricate() -> None:
    # 声称 found 却给不出合法日期 → 绝不编造，回退 unknown
    result = parse_extraction_result(
        json.dumps({"found": True, "deadline": "尽快", "rolling": False, "window": ""})
    )
    assert result.status == "unknown"
    assert result.deadline is None


def test_parse_broken_json_is_unknown() -> None:
    result = parse_extraction_result("not a json { ")
    assert result.status == "unknown"
    assert result.deadline is None


def test_parse_non_dict_json_is_unknown() -> None:
    assert parse_extraction_result("[1, 2, 3]").status == "unknown"


class _FakeLLM:
    """假 LLM：按预置 content 返回，或抛错以验证异常回退。"""

    def __init__(self, content: str = "", raise_exc: bool = False) -> None:
        self._content = content
        self._raise = raise_exc
        self.called = False

    async def invoke(self, messages, tools=None, response_format=None, tool_choice=None):
        self.called = True
        if self._raise:
            raise RuntimeError("LLM down")
        return {"content": self._content}


def test_extract_none_llm_returns_unknown_without_call() -> None:
    result = asyncio.run(extract_deadline(None, "t", "正文"))
    assert result.status == "unknown"


def test_extract_empty_body_skips_llm() -> None:
    llm = _FakeLLM(content=json.dumps({"found": True, "deadline": "2026-07-31"}))
    result = asyncio.run(extract_deadline(llm, "t", "   "))
    assert result.status == "unknown"
    assert llm.called is False  # 无正文不浪费一次调用


def test_extract_happy_path() -> None:
    llm = _FakeLLM(content=json.dumps({"found": True, "deadline": "2026-07-31", "window": "7月底"}))
    result = asyncio.run(extract_deadline(llm, "高企", "请于2026-07-31前申报"))
    assert result.status == "extracted"
    assert result.deadline == date(2026, 7, 31)


def test_extract_llm_error_falls_back_to_unknown() -> None:
    llm = _FakeLLM(raise_exc=True)
    result = asyncio.run(extract_deadline(llm, "t", "正文"))
    assert result.status == "unknown"  # 异常不冒泡，安全回退
