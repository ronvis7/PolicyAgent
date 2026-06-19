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
from typing import List, Optional

from pydantic import BaseModel, Field

# 详情统一免责声明(对应 handoff 风险条：严禁当权威输出)
DEFAULT_DISCLAIMER = "以下条件为结构性概要，具体数值/比例/名额/申报窗口以当年官方最新办法为准。"


class QualificationLevel(str, Enum):
    """资质层级(决定地区适用范围与梯度前置关系)"""
    NATIONAL = "national"      # 国家级(恒适用)
    PROVINCIAL = "provincial"  # 省级(按档案省份)
    MUNICIPAL = "municipal"    # 市/区级(按档案市/区)
    GENERAL = "general"        # 通用体系认证(跨级，恒适用)


class ConditionMetric(str, Enum):
    """可由企业档案结构化字段确定性核验的条件指标(⑥ 能力② 硬条件)。

    每个指标对应档案里一个(或可推导的)数值；档案缺该字段时核验结果为"待确认(未填)"，
    而非"不达标"——未知≠不满足。带 _RATIO 的为推导比值(百分比)。
    """
    COMPANY_AGE_YEARS = "company_age_years"            # 成立年限(年，由成立日期推导)
    TOTAL_STAFF = "total_staff"                        # 员工总数(人)
    RD_STAFF = "rd_staff"                              # 研发人员数(人)
    RD_STAFF_RATIO = "rd_staff_ratio"                  # 研发(科技)人员占比(%)
    RD_INVESTMENT_RATIO = "rd_investment_ratio"        # 研发投入占营收比(%)
    INVENTION_PATENTS = "invention_patents"            # 发明专利数(件)
    IP_TOTAL = "ip_total"                              # 知识产权总数(发明+其他，件)
    REGISTERED_CAPITAL_WAN = "registered_capital_wan"  # 注册资本(万元)
    ANNUAL_REVENUE_WAN = "annual_revenue_wan"          # 上年度营收(万元)


class ConditionOperator(str, Enum):
    """硬条件比较方向(资质门槛绝大多数是下限 gte)。"""
    GTE = "gte"  # 实际值 ≥ 门槛
    LTE = "lte"  # 实际值 ≤ 门槛


class QualificationCondition(BaseModel):
    """单条可结构化核验的硬条件(目录侧维护，数值仍需逐条校对)。"""
    metric: ConditionMetric  # 核验指标
    threshold: float  # 门槛值
    op: ConditionOperator = ConditionOperator.GTE  # 比较方向
    label: str = ""  # 概要描述(对应 key_conditions 中的人读文案)


class ConditionBand(BaseModel):
    """banded 条件的单档：`band_metric` 值落入本档时适用 `threshold`。

    多档按 `max_value` 升序排列，逐档比较(实际值 ≤ max_value 即落入)；最高档用
    `max_value=None` 作开口顶档(高于前一档上限的都归它)。
    """
    max_value: Optional[float] = None  # 本档上限(含)，None=最高开口档
    threshold: float  # 本档门槛
    label: str = ""  # 本档人读描述(如"营收≤5000万 → ≥5%")


class BandedCondition(BaseModel):
    """分档硬条件：门槛随另一指标(band_metric)落档而变。

    典型例：高企"研发费用占销售收入比例"按上年度营收分三档(≤5000万→5%、5000万~2亿→4%、
    >2亿→3%)。`band_metric` 缺失则无法定档 → 待确认；定档后再比被核验指标 `metric`。
    数值仍为结构性概要，须随 disclaimer/last_reviewed 呈现、由业务方按当年办法核对。
    """
    metric: ConditionMetric  # 被核验指标(如研发投入占比)
    op: ConditionOperator = ConditionOperator.GTE  # 比较方向
    band_metric: ConditionMetric  # 决定落档的指标(如上年度营收)
    bands: List[ConditionBand]  # 各档(升序，最后一档可 max_value=None)
    label: str = ""  # 概要描述(对应 key_conditions 文案，用于从 manual_review 去重)


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
    # ---- 能力② 可结构化核验的硬条件(子集，能算的才进；其余 key_conditions 走人工/材料确认)----
    structured_conditions: List[QualificationCondition] = Field(default_factory=list)
    # ---- 能力② 分档硬条件(门槛随营收/行业等落档而变，如高企研发费用占比)----
    banded_conditions: List[BandedCondition] = Field(default_factory=list)
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


class ConditionStatus(str, Enum):
    """单条硬条件的核验状态。"""
    MET = "met"          # 达标
    UNMET = "unmet"      # 不达标(差距)
    UNKNOWN = "unknown"  # 待确认(档案缺该字段，未知≠不达标)


class ConditionCheck(BaseModel):
    """单条硬条件核验结果(能力②的最小单元)。"""
    metric: ConditionMetric
    op: ConditionOperator
    threshold: float
    label: str = ""
    actual: Optional[float] = None  # 档案推导出的实际值(未知为 None)
    status: ConditionStatus
    detail: str = ""  # 人读结论(如"研发人员占比 8.3% < 10%")


class QualificationGapReport(BaseModel):
    """企业档案 × 单条资质的差距分析结果(⑥ 能力②，混合引擎的结构化部分)。

    `checks` 为可结构化核验的硬条件逐条结论；`manual_review` 为无结构化对应、需结合材料
    人工/Agent(能力③)确认的概要条件；`prerequisites_missing` 复用能力① 的前置缺口。
    """
    qualification: Qualification
    checks: List[ConditionCheck] = Field(default_factory=list)
    manual_review: List[str] = Field(default_factory=list)  # 需人工/材料确认的概要条件
    prerequisites_missing: List[str] = Field(default_factory=list)  # 缺失前置资质
    met_count: int = 0
    unmet_count: int = 0
    unknown_count: int = 0
    summary: str = ""  # 一句话总览
