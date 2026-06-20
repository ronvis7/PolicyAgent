"""主动情报简报组装器（主动情报 Agent 的推理内核）。

把已聚合的 `ReportData`（③匹配政策 / ⑥资质差距 / ⑤临期申报）压成紧凑的事实清单送 LLM，
让其归纳出"本期最值得关注的机会 + 为什么 + 建议下一步"的优先级简报；并提供一份**确定性兜底**
简报（无 LLM / 调用失败 / 解析失败时使用），保证主动情报始终有产出。

纯函数（提示构造 + 结果解析 + 兜底）与网络 I/O 分离，便于离线单测。
遵循 best-effort 与"待核对"纪律：LLM 只在给定事实上归纳，不得编造机会；异常一律回退兜底。
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.domain.models.intel_briefing import (
    BriefingItem,
    BriefingUrgency,
    IntelBriefing,
)
from app.domain.models.report import ReportData

logger = logging.getLogger(__name__)

# 送审上限（控制 token；兜底也按此截断，避免简报过长）
_MAX_POLICIES = 8
_MAX_GAPS = 5
_MAX_EXPIRING = 5
# 临期高紧迫阈值：截止 ≤ 7 天判 high
_URGENT_DAYS = 7

_SYSTEM_PROMPT = (
    "你是企业政策情报助手。基于系统给出的、已匹配好的机会事实，"
    "为这家企业归纳一份简短的『主动情报简报』：挑出最值得关注的若干机会，"
    "说明为什么现在值得关注，并给出一句可执行的下一步建议。"
    "严格只使用给定事实，不要编造任何机会、数字或截止日期。仅输出 JSON，不要额外解释。"
)


def _days_left(deadline: Optional[date], today: date) -> Optional[int]:
    """剩余天数（无截止返回 None）。"""
    return (deadline - today).days if deadline is not None else None


def build_facts(data: ReportData, today: date) -> Dict[str, Any]:
    """把 ReportData 压成送 LLM 的紧凑事实字典（也供兜底复用）。"""
    profile = data.profile
    region = " ".join(p for p in (profile.province, profile.city, profile.district) if p).strip()

    policies = [
        {
            "title": item.title,
            "issuer": item.issuer,
            "reasons": list(item.reasons)[:3],
        }
        for item in data.matched_policies[:_MAX_POLICIES]
    ]
    gaps = [
        {
            "name": gap.qualification.name,
            "summary": gap.summary,
            "missing": list(gap.prerequisites_missing)[:3],
        }
        for gap in data.qualification_gaps[:_MAX_GAPS]
    ]
    expiring = [
        {
            "title": item.title,
            "days_left": _days_left(item.apply_deadline, today),
        }
        for item in data.expiring[:_MAX_EXPIRING]
    ]
    return {
        "company": profile.company_name,
        "region": region,
        "industry": profile.industry,
        "matched_policies": policies,
        "qualification_gaps": gaps,
        "expiring": expiring,
    }


def build_messages(facts: Dict[str, Any]) -> List[Dict[str, str]]:
    """构造 LLM 消息（系统纪律 + 事实 + 输出 schema 约束）。"""
    user = (
        "以下是这家企业已匹配到的机会事实（JSON）：\n"
        f"{json.dumps(facts, ensure_ascii=False)}\n\n"
        "请输出如下 JSON：\n"
        "{\n"
        '  "headline": "一句话总览，如：本期有 N 个机会值得关注",\n'
        '  "items": [\n'
        '    {\n'
        '      "title": "机会标题（取自给定事实）",\n'
        '      "category": "政策机会|资质机会|临期申报",\n'
        '      "reason": "为什么现在值得关注（基于命中理由/差距/临期，简洁一句）",\n'
        '      "action": "建议的下一步（如：查看政策原文 / 补齐研发人员占比 / 尽快准备申报材料）",\n'
        '      "urgency": "high|normal|low"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：items 最多 6 条，按重要性排序；临期申报项 urgency 设为 high；"
        "只使用给定事实中的机会，标题必须来自事实；无任何机会时 items 返回空数组。"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _coerce_urgency(value: Any) -> BriefingUrgency:
    """把 LLM 给的 urgency 文本安全转枚举（无法识别回 normal）。"""
    try:
        return BriefingUrgency(str(value).strip().lower())
    except (ValueError, AttributeError):
        return BriefingUrgency.NORMAL


def parse_briefing(tenant_id: str, content: str) -> Optional[IntelBriefing]:
    """解析 LLM 返回的 JSON 为 IntelBriefing；解析失败返回 None（交由调用方走兜底）。"""
    try:
        # 容忍模型偶发的 ```json 包裹
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):]
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError, AttributeError) as e:
        logger.warning("情报简报解析失败，将走兜底: %s", e)
        return None

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return None

    items: List[BriefingItem] = []
    for raw in raw_items[:6]:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        items.append(BriefingItem(
            title=title,
            category=str(raw.get("category", "")).strip(),
            reason=str(raw.get("reason", "")).strip(),
            action=str(raw.get("action", "")).strip(),
            urgency=_coerce_urgency(raw.get("urgency")),
        ))

    headline = str(payload.get("headline", "")).strip() or _default_headline(len(items))
    return IntelBriefing(
        tenant_id=tenant_id, headline=headline, items=items, generated_by="llm",
    )


def _default_headline(count: int) -> str:
    return f"本期为你筛选出 {count} 个值得关注的机会" if count else "本期暂无与你高度匹配的新机会"


def fallback_briefing(tenant_id: str, data: ReportData, today: date) -> IntelBriefing:
    """确定性兜底简报：无 LLM/解析失败时，直接从事实拼出可读简报。"""
    facts = build_facts(data, today)
    items: List[BriefingItem] = []

    for exp in facts["expiring"]:
        days = exp["days_left"]
        when = f"仅剩 {days} 天截止" if isinstance(days, int) else "已进入申报窗口"
        items.append(BriefingItem(
            title=exp["title"], category="临期申报",
            reason=f"申报{when}，需尽快处理。",
            action="尽快查看申报通知原文并准备材料。",
            urgency=BriefingUrgency.HIGH
            if isinstance(days, int) and days <= _URGENT_DAYS else BriefingUrgency.NORMAL,
        ))

    for pol in facts["matched_policies"]:
        if len(items) >= 6:
            break
        reason = "；".join(pol["reasons"]) if pol["reasons"] else "与企业画像相关。"
        items.append(BriefingItem(
            title=pol["title"], category="政策机会",
            reason=reason, action="查看政策详情，判断是否申报。",
            urgency=BriefingUrgency.NORMAL,
        ))

    for gap in facts["qualification_gaps"]:
        if len(items) >= 6:
            break
        items.append(BriefingItem(
            title=gap["name"], category="资质机会",
            reason=gap["summary"] or "可评估申报条件差距。",
            action="查看资质差距分析，补齐缺口。",
            urgency=BriefingUrgency.NORMAL,
        ))

    return IntelBriefing(
        tenant_id=tenant_id, headline=_default_headline(len(items)),
        items=items[:6], generated_by="fallback",
    )
