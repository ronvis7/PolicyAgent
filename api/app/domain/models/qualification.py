"""资质申报机会领域模型（主线⑥）。

资质 = ④ 工作台 Feed 的第二类机会(opportunity)。与政策最大区别：资质有限、相对稳定、
由政策文件定义，故以**结构化目录打底、不爬**(目录数据见 infrastructure/data)。

本模型承载单条资质的展示与匹配信息：`match_signals`/`prerequisites` 供与企业档案做
启发式匹配(能力①)；`key_conditions`/`materials`/`timing`/`policy_basis` 供详情展示与
后续差距分析(能力②)、材料指引(能力③)。

风险纪律：数值类条件逐年微调，目录里的比例/门槛/窗口期均为**结构性概要**，
`disclaimer` + `last_reviewed` 必须随详情一并呈现，严禁当权威输出。
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field

# 详情统一免责声明(对应 handoff 风险条：严禁当权威输出)
DEFAULT_DISCLAIMER = "以下条件为结构性概要，具体数值/比例/名额/申报窗口以当年官方最新办法为准。"


class QualificationLevel(str, Enum):
    """资质层级(决定地区适用范围与梯度前置关系)"""
    NATIONAL = "national"      # 国家级(恒适用)
    PROVINCIAL = "provincial"  # 省级(按档案省份)
    MUNICIPAL = "municipal"    # 市/区级(按档案市/区)
    GENERAL = "general"        # 通用体系认证(跨级，恒适用)


class Qualification(BaseModel):
    """单条资质申报机会(目录条目，人工维护、不爬)。"""
    key: str  # 自然主键(slug，作为 Feed 条目关联键)
    name: str  # 资质名称
    level: QualificationLevel  # 层级
    issuer: str = ""  # 认定机构
    category: str = ""  # 类型(科技创新/专精特新/平台载体/体系认证…)
    region: str = ""  # 适用地区(国家级=全国；省级=江苏省；市/区级=无锡市/新吴区)
    key_conditions: List[str] = Field(default_factory=list)  # 核心条件(概要，需校对)
    materials: List[str] = Field(default_factory=list)  # 主要材料(概要)
    timing: str = ""  # 申报时间
    policy_basis: str = ""  # 政策依据(认定办法名称/文号)
    benefit: str = ""  # 主要价值
    # ---- 匹配用信号 ----
    match_signals: List[str] = Field(default_factory=list)  # 与档案匹配的软信号(行业/技术域等)
    prerequisites: List[str] = Field(default_factory=list)  # 前置资质(梯度，如小巨人需省专精特新)
    # ---- 风险纪律 ----
    last_reviewed: str = ""  # 末次核对日期(YYYY-MM-DD)
    disclaimer: str = DEFAULT_DISCLAIMER  # 免责声明(详情强制展示)


class QualificationMatch(BaseModel):
    """企业档案 × 单条资质的匹配结果(⑥ 能力①)。

    `eligible` 表示"启发式判定可申报"(信号覆盖足够且无前置缺失)，否则为"接近可申报"，
    `missing_*` 给出差距清单的雏形(能力②差距分析在此之上由 Agent 深化)。
    """
    qualification: Qualification
    score: float = 0.0  # 匹配总分∈[0,1](信号+前置覆盖率)
    matched_signals: List[str] = Field(default_factory=list)  # 命中的信号
    missing_signals: List[str] = Field(default_factory=list)  # 未命中的信号
    missing_prerequisites: List[str] = Field(default_factory=list)  # 缺失的前置资质
    eligible: bool = False  # 可申报(True)/接近可申报(False)
    reasons: List[str] = Field(default_factory=list)  # 可读理由
