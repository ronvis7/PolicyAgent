"""主动情报简报领域模型（主动情报 Agent）。

Agent 在企业"离线"时自主扫描已物化的机会（③匹配政策 / ⑥资质差距 / ⑤临期申报），
推理出"本期最值得关注的机会 + 为什么 + 建议下一步"，沉淀为一份**带理由的优先级简报**，
主动呈现给用户——这是"以企业为主体的主动情报服务"的临门一脚。

每租户保存最新一份（覆盖式）。简报由 LLM 生成；无 LLM/解析失败时回退确定性兜底简报。
风险纪律：门槛/截止均为结构性概要，`disclaimer` 必须随简报一并呈现。
"""

from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field

# 简报统一免责声明（与报告/资质口径一致）
BRIEFING_DISCLAIMER = (
    "本情报简报由系统依据企业档案与公开政策自动匹配、由 AI 归纳生成，"
    "所列机会、门槛与截止均为结构性概要，具体以各官方主管部门当年最新办法与原文为准，"
    "不构成申报建议。"
)


class BriefingUrgency(str, Enum):
    """情报项紧迫度（驱动前端徽章与排序）。"""
    HIGH = "high"      # 临期/强相关，建议尽快处理
    NORMAL = "normal"  # 值得关注
    LOW = "low"        # 可了解


class BriefingItem(BaseModel):
    """一条情报要点：是什么机会 + 为什么现在值得关注 + 建议下一步。"""
    title: str = ""                                  # 机会标题（政策名/资质名）
    category: str = ""                               # 类别（政策机会/资质机会/临期申报）
    reason: str = ""                                 # 为什么值得关注（命中点/差距/临期）
    action: str = ""                                 # 建议的下一步动作
    urgency: BriefingUrgency = BriefingUrgency.NORMAL # 紧迫度


class IntelBriefing(BaseModel):
    """一份主动情报简报（每租户最新一份，覆盖式保存）。"""
    tenant_id: str = ""
    headline: str = ""                               # 一句话总览（如：本期有 3 个机会值得关注）
    items: List[BriefingItem] = Field(default_factory=list)
    generated_by: str = "fallback"                   # 生成方式：llm / fallback（兜底）
    disclaimer: str = BRIEFING_DISCLAIMER
    generated_at: datetime = Field(default_factory=datetime.now)
