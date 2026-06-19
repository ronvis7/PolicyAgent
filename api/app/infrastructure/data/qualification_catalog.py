"""资质申报机会目录（主线⑥ 数据源：结构化打底、不爬）。

首版由 AI 按 国家级 / 江苏省级 / 无锡市·新吴区级 / 通用体系认证 整理(种子见 handoff
2026-06-15-qualification-opportunities.md)，企业方/按官方办法逐条校对。

风险纪律(务必遵守)：
- `key_conditions` 中的比例/门槛/名额/窗口期均为**结构性概要**，逐年微调，**严禁当权威输出**；
  详情展示须连同 `Qualification.disclaimer` 与 `last_reviewed` 一并呈现。
- `match_signals` 为与企业档案做启发式匹配的软信号(子串命中)，非硬性准入条件。
- `prerequisites` 为梯度前置资质核心词(与档案已有资质子串匹配)，级别区分有限，仅作提示。
"""

from typing import List

from app.domain.models.qualification import (
    BandedCondition,
    ConditionBand,
    ConditionMetric,
    ConditionOperator,
    Qualification,
    QualificationCondition,
    QualificationLevel,
)

# 目录末次人工核对日期(数值类条件以当年官方最新办法为准)
_LAST_REVIEWED = "2026-06-15"


def _q(**kwargs) -> Qualification:
    kwargs.setdefault("last_reviewed", _LAST_REVIEWED)
    return Qualification(**kwargs)


# ============================ 国家级 ============================
_NATIONAL: List[Qualification] = [
    _q(
        key="high-tech-enterprise",
        name="高新技术企业认定（高企）",
        level=QualificationLevel.NATIONAL,
        issuer="科技部/财政部/税务总局（省认定办公室组织）",
        category="科技创新",
        region="全国",
        key_conditions=[
            "注册成立满 1 年以上",
            "拥有核心自主知识产权",
            "产品（服务）属《国家重点支持的高新技术领域》",
            "科技人员占职工总数比例达标（概要：≥10%）",
            "研发费用占销售收入比例达标（分营收档，概要：≤5000万→≥5%、5000万~2亿→≥4%、>2亿→≥3%）",
            "高新技术产品（服务）收入占比达标（概要：≥60%）",
            "创新能力综合评分达标（概要：≥70 分）",
        ],
        materials=["知识产权证明", "研发费用专项审计报告", "高新收入专项审计报告",
                   "科技人员名单与社保证明", "研发组织管理材料", "近三年财务报表"],
        timing="通常每年多批，省统一通知（约 6~9 月）",
        policy_basis="国科发火〔2016〕32号《高新技术企业认定管理办法》及工作指引",
        benefit="企业所得税减按 15%；各级配套奖励；多数后续资质的前置条件",
        match_signals=["高新技术", "知识产权", "研发", "研发投入"],
        # 仅把口径明确、标准稳定的硬条件结构化(label 与上面 key_conditions 逐字一致，避免重复展示)；
        # 高新收入占比/创新评分无档案对应字段，留作人工/材料确认。
        structured_conditions=[
            QualificationCondition(
                metric=ConditionMetric.COMPANY_AGE_YEARS, threshold=1,
                label="注册成立满 1 年以上",
            ),
            QualificationCondition(
                metric=ConditionMetric.RD_STAFF_RATIO, threshold=10,
                label="科技人员占职工总数比例达标（概要：≥10%）",
            ),
        ],
        # 研发费用占销售收入比例按上年度营收分三档(概要数值以当年办法为准，业务方核对)。
        # label 与 key_conditions 对应文案逐字一致，从 manual_review 去重。
        banded_conditions=[
            BandedCondition(
                metric=ConditionMetric.RD_INVESTMENT_RATIO,
                band_metric=ConditionMetric.ANNUAL_REVENUE_WAN,
                label="研发费用占销售收入比例达标（分营收档，概要：≤5000万→≥5%、5000万~2亿→≥4%、>2亿→≥3%）",
                bands=[
                    ConditionBand(max_value=5000, threshold=5, label="营收≤5000万 → ≥5%"),
                    ConditionBand(max_value=20000, threshold=4, label="营收5000万~2亿 → ≥4%"),
                    ConditionBand(max_value=None, threshold=3, label="营收>2亿 → ≥3%"),
                ],
            ),
        ],
    ),
    _q(
        key="tech-sme",
        name="科技型中小企业（评价入库）",
        level=QualificationLevel.NATIONAL,
        issuer="科技部（全国科技型中小企业信息库，省科技厅组织）",
        category="科技创新",
        region="全国",
        key_conditions=[
            "在中国境内注册的居民企业",
            "职工总数不超过 500 人（科技型中小企业上限）",
            "年销售收入不超过 2 亿元（科技型中小企业上限）",
            "资产总额不超过 2 亿元（科技型中小企业上限）",
            "有研发活动并按评价指标（科技人员/研发投入/科技成果）达分",
            "或持高企/省部级研发机构等可直接评价入库",
        ],
        materials=["线上填报评价指标", "知识产权与研发活动佐证"],
        timing="全年滚动，每年起评（建议上半年）",
        policy_basis="国科发政〔2017〕115号《科技型中小企业评价办法》",
        benefit="研发费用加计扣除比例提升；高企培育前置；多项扶持入门券",
        match_signals=["研发", "科技", "中小企业"],
        # 国科发政〔2017〕115号对"科技型中小企业"设全行业统一硬性上限(非分行业划型)：
        # 职工≤500人、年销售收入≤2亿、资产总额≤2亿。前两项可由档案核验(资产无对应字段，
        # 连同综合评分≥60/持高企等留 manual_review)。上限超出即明确不符合 → LTE。
        structured_conditions=[
            QualificationCondition(
                metric=ConditionMetric.TOTAL_STAFF, threshold=500,
                op=ConditionOperator.LTE, label="职工总数不超过 500 人（科技型中小企业上限）",
            ),
            QualificationCondition(
                metric=ConditionMetric.ANNUAL_REVENUE_WAN, threshold=20000,
                op=ConditionOperator.LTE, label="年销售收入不超过 2 亿元（科技型中小企业上限）",
            ),
        ],
    ),
    _q(
        key="spec-new-little-giant",
        name="专精特新“小巨人”企业",
        level=QualificationLevel.NATIONAL,
        issuer="工业和信息化部",
        category="专精特新",
        region="全国",
        key_conditions=[
            "须先为省级专精特新中小企业",
            "专业化：主营业务收入占比高、深耕细分领域达一定年限",
            "精细化、特色化、新颖化（研发/创新指标）达标",
            "经济效益与成长性达标",
        ],
        materials=["申报书", "近年财务报表", "研发与知识产权材料", "细分市场地位佐证"],
        timing="工信部定期开展（约每年/两年一批）",
        policy_basis="《优质中小企业梯度培育管理暂行办法》（工信部企业〔2022〕126号）",
        benefit="国家级背书；专项资金；融资/采购倾斜",
        match_signals=["制造业", "专精特新", "细分领域"],
        prerequisites=["专精特新中小企业"],
    ),
    _q(
        key="national-tech-center",
        name="国家级企业技术中心",
        level=QualificationLevel.NATIONAL,
        issuer="国家发改委（会同科技/财政/海关/税务）",
        category="平台载体",
        region="全国",
        key_conditions=[
            "大中型企业",
            "研发投入与研发人员规模达门槛",
            "已为省级企业技术中心并运行良好",
            "创新机制与成果显著",
        ],
        materials=["评价材料", "研发投入与人员数据", "创新成果与机制说明"],
        timing="发改委定期组织（约每年一次认定+评价）",
        policy_basis="《国家企业技术中心认定管理办法》（发改委令）",
        benefit="进口设备免税等政策；高层级背书",
        match_signals=["研发", "技术中心", "创新"],
        prerequisites=["企业技术中心"],
    ),
    _q(
        key="manufacturing-champion",
        name="制造业单项冠军（企业/产品）",
        level=QualificationLevel.NATIONAL,
        issuer="工业和信息化部/中国工业经济联合会",
        category="专精特新",
        region="全国",
        key_conditions=[
            "长期专注于产业链特定环节",
            "单项产品市场占有率全球/全国领先",
            "持续研发投入与质量优势",
        ],
        materials=["市场占有率佐证", "财务数据", "研发与质量材料"],
        timing="工信部定期开展",
        policy_basis="工信部制造业单项冠军培育相关通知",
        benefit="国家级最高梯度背书",
        match_signals=["制造业", "细分领域"],
    ),
    _q(
        key="ipr-standard",
        name="知识产权管理体系认证（贯标）",
        level=QualificationLevel.GENERAL,
        issuer="经认可的第三方认证机构",
        category="体系认证",
        region="全国",
        key_conditions=["建立并运行符合 GB/T 29490 的知识产权管理体系满一定周期"],
        materials=["体系文件", "运行记录", "内审/管理评审记录"],
        timing="全年（机构受理）",
        policy_basis="GB/T 29490《企业知识产权管理规范》",
        benefit="多地申报加分项；对高企/专精特新申报有利",
        match_signals=["知识产权"],
    ),
    _q(
        key="two-integration",
        name="两化融合管理体系贯标",
        level=QualificationLevel.GENERAL,
        issuer="经评定的第三方评定机构",
        category="体系认证",
        region="全国",
        key_conditions=[
            "建立并运行符合 GB/T 23001 的两化融合管理体系",
            "通过评定分级（A~AAA）",
        ],
        materials=["体系文件", "运行与评定材料"],
        timing="全年",
        policy_basis="GB/T 23001 系列；两化融合管理体系贯标政策",
        benefit="制造业数字化背书；多地奖励",
        match_signals=["制造业", "信息化", "数字化"],
    ),
]


# ============================ 江苏省级 ============================
_JIANGSU: List[Qualification] = [
    _q(
        key="js-spec-new",
        name="江苏省专精特新中小企业",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省工业和信息化厅",
        category="专精特新",
        region="江苏省",
        key_conditions=[
            "符合中小企业划型标准",
            "专业化/精细化/特色化/新颖化指标达标",
            "研发投入、营收增长、知识产权等量化指标达分",
        ],
        materials=["申报书", "财务报表", "研发与知识产权佐证"],
        timing="省工信厅每年组织",
        policy_basis="江苏省优质中小企业梯度培育实施细则",
        benefit="“小巨人”前置；省级专项与配套",
        match_signals=["制造业", "研发", "知识产权", "中小企业"],
    ),
    _q(
        key="js-tech-center",
        name="江苏省企业技术中心",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省发展和改革委员会",
        category="平台载体",
        region="江苏省",
        key_conditions=["研发投入/研发人员/设备原值达门槛", "研发组织与制度健全", "有创新成果"],
        materials=["评价材料", "研发数据", "成果材料"],
        timing="省发改委每年组织",
        policy_basis="江苏省企业技术中心认定管理办法",
        benefit="国家级技术中心前置；省市配套",
        match_signals=["研发", "技术中心", "创新"],
    ),
    _q(
        key="js-engineering-center",
        name="江苏省工程技术研究中心",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省科学技术厅",
        category="平台载体",
        region="江苏省",
        key_conditions=["有研发基础与场地/设备/团队达标", "承担研发任务"],
        materials=["建设/运行材料", "团队与设备清单", "成果材料"],
        timing="省科技厅每年组织",
        policy_basis="江苏省工程技术研究中心管理办法",
        benefit="科技平台背书；项目与人才倾斜",
        match_signals=["研发", "工程技术", "技术"],
    ),
    _q(
        key="js-gazelle",
        name="江苏省瞪羚企业",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省科学技术厅/高新区",
        category="科技创新",
        region="江苏省",
        key_conditions=["高成长性（营收/净利连续高增）", "通常须为高新技术企业", "主营高新技术"],
        materials=["财务成长性数据", "高企证书", "研发材料"],
        timing="每年组织（多由高新区报送）",
        policy_basis="江苏省/苏南国家自创区瞪羚企业培育政策",
        benefit="高成长背书；融资与扶持倾斜",
        match_signals=["高新技术", "科技", "高成长"],
        prerequisites=["高新技术企业"],
    ),
    _q(
        key="js-unicorn",
        name="江苏省独角兽/潜在独角兽企业",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省科学技术厅",
        category="科技创新",
        region="江苏省",
        key_conditions=[
            "成立年限内估值达门槛（独角兽概要≥10亿美元，潜在独角兽达相应区间）",
            "未上市",
            "高成长科技企业",
        ],
        materials=["估值/融资证明", "财务与业务材料"],
        timing="每年组织",
        policy_basis="江苏省独角兽/瞪羚培育政策",
        benefit="顶级成长背书；重点扶持",
        match_signals=["科技", "高成长", "融资"],
    ),
    _q(
        key="js-hi-tech-product",
        name="江苏省高新技术产品认定",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省科学技术厅",
        category="科技创新",
        region="江苏省",
        key_conditions=["产品属高新技术领域", "有自主知识产权", "技术与经济指标达标"],
        materials=["产品技术资料", "知识产权证明", "检测/销售证明"],
        timing="每年组织",
        policy_basis="江苏省高新技术产品认定办法",
        benefit="高企收入占比佐证；采购倾斜",
        match_signals=["高新技术", "知识产权", "产品"],
    ),
    _q(
        key="js-industrial-design",
        name="江苏省工业设计中心",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省工业和信息化厅",
        category="平台载体",
        region="江苏省",
        key_conditions=["设有独立工业设计部门", "设计投入/人员/成果达标"],
        materials=["设计中心建设材料", "团队与成果材料"],
        timing="每年组织",
        policy_basis="江苏省工业设计中心管理办法",
        benefit="设计创新背书；专项支持",
        match_signals=["制造业", "工业设计", "设计"],
    ),
    _q(
        key="js-smart-manufacturing",
        name="江苏省智能制造示范工厂/车间",
        level=QualificationLevel.PROVINCIAL,
        issuer="江苏省工业和信息化厅",
        category="平台载体",
        region="江苏省",
        key_conditions=["关键工序数字化/智能化达标", "有信息化系统集成与成效"],
        materials=["智能化改造材料", "系统与成效证明"],
        timing="每年组织",
        policy_basis="江苏省智能制造示范相关通知",
        benefit="智改数转背书；奖补",
        match_signals=["制造业", "智能制造", "数字化", "信息化"],
    ),
]


# ====================== 无锡市 / 新吴区级 ======================
_WUXI: List[Qualification] = [
    _q(
        key="wx-eagle-gazelle",
        name="无锡市雏鹰/瞪羚/准独角兽企业",
        level=QualificationLevel.MUNICIPAL,
        issuer="无锡市科学技术局",
        category="科技创新",
        region="无锡市",
        key_conditions=[
            "分层培育：雏鹰（初创高成长）/瞪羚（高企+高成长）/准独角兽（估值门槛）",
            "科技型、成长性达标",
        ],
        materials=["财务成长性数据", "高企/研发材料", "估值证明（准独角兽）"],
        timing="每年组织",
        policy_basis="无锡市雏鹰瞪羚准独角兽企业培育政策",
        benefit="市级梯度背书；专项扶持与人才政策",
        match_signals=["科技", "高新技术", "高成长"],
    ),
    _q(
        key="wx-tech-center",
        name="无锡市级企业技术中心",
        level=QualificationLevel.MUNICIPAL,
        issuer="无锡市发改委/工信局",
        category="平台载体",
        region="无锡市",
        key_conditions=["研发投入/人员/设备达市级门槛", "研发制度健全"],
        materials=["评价材料", "研发数据"],
        timing="每年组织",
        policy_basis="无锡市企业技术中心认定办法",
        benefit="省级技术中心前置；市级配套",
        match_signals=["研发", "技术中心"],
    ),
    _q(
        key="wx-engineering-center",
        name="无锡市工程技术研究中心",
        level=QualificationLevel.MUNICIPAL,
        issuer="无锡市科学技术局",
        category="平台载体",
        region="无锡市",
        key_conditions=["研发场地/团队/设备达市级门槛", "承担研发任务"],
        materials=["建设/运行材料", "团队设备清单"],
        timing="每年组织",
        policy_basis="无锡市工程技术研究中心管理办法",
        benefit="省级工程中心前置；科技平台背书",
        match_signals=["研发", "工程技术", "技术"],
    ),
    _q(
        key="wx-spec-new",
        name="无锡市专精特新中小企业",
        level=QualificationLevel.MUNICIPAL,
        issuer="无锡市工业和信息化局",
        category="专精特新",
        region="无锡市",
        key_conditions=["市级专精特新指标（专业化/创新等）达标"],
        materials=["申报书", "财务与研发材料"],
        timing="每年组织",
        policy_basis="无锡市优质中小企业培育细则",
        benefit="省级专精特新前置；市级奖补",
        match_signals=["制造业", "专精特新", "中小企业"],
    ),
    _q(
        key="xinwu-bonus",
        name="新吴区高企/科技项目配套奖励（认定类申报）",
        level=QualificationLevel.MUNICIPAL,
        issuer="无锡市新吴区科技局/相关部门",
        category="科技创新/扶持",
        region="无锡市新吴区",
        key_conditions=["注册及纳税在新吴区", "获相应上级资质或立项后申请配套"],
        materials=["上级资质证书", "立项文件", "区内经营证明"],
        timing="按区年度政策窗口",
        policy_basis="新吴区科技创新/产业扶持年度政策",
        benefit="区级配套资金奖励",
        match_signals=["科技", "高新技术"],
    ),
]


# ================== 通用体系认证（跨级，常作加分/前置） ==================
_GENERAL: List[Qualification] = [
    _q(
        key="iso9001",
        name="ISO 9001 质量管理体系认证",
        level=QualificationLevel.GENERAL,
        issuer="第三方认证机构",
        category="体系认证",
        region="全国",
        key_conditions=["建立并运行质量管理体系满一定周期"],
        materials=["体系文件", "运行/内审记录"],
        timing="全年",
        policy_basis="GB/T 19001 / ISO 9001",
        benefit="投标/资质广泛加分项",
        match_signals=[],  # 通用，几乎所有企业适用
    ),
    _q(
        key="iso14001",
        name="ISO 14001 环境管理体系认证",
        level=QualificationLevel.GENERAL,
        issuer="第三方认证机构",
        category="体系认证",
        region="全国",
        key_conditions=["建立并运行环境管理体系"],
        materials=["体系文件", "环境因素与运行记录"],
        timing="全年",
        policy_basis="GB/T 24001 / ISO 14001",
        benefit="绿色/投标加分",
        match_signals=["制造业", "生产"],
    ),
    _q(
        key="iso45001",
        name="ISO 45001 职业健康安全管理体系认证",
        level=QualificationLevel.GENERAL,
        issuer="第三方认证机构",
        category="体系认证",
        region="全国",
        key_conditions=["建立并运行职业健康安全管理体系"],
        materials=["体系文件", "运行记录"],
        timing="全年",
        policy_basis="GB/T 45001 / ISO 45001",
        benefit="投标加分；合规",
        match_signals=["制造业", "生产"],
    ),
    _q(
        key="iso27001",
        name="ISO/IEC 27001 信息安全管理体系认证",
        level=QualificationLevel.GENERAL,
        issuer="第三方认证机构",
        category="体系认证",
        region="全国",
        key_conditions=["建立并运行信息安全管理体系"],
        materials=["体系文件", "风险评估与运行记录"],
        timing="全年",
        policy_basis="ISO/IEC 27001",
        benefit="软件/数据类投标硬指标",
        match_signals=["软件", "信息技术", "数据", "信息安全"],
    ),
    _q(
        key="cmmi",
        name="CMMI 能力成熟度集成模型评估",
        level=QualificationLevel.GENERAL,
        issuer="经授权评估机构",
        category="体系认证",
        region="全国",
        key_conditions=["软件研发过程达对应成熟度等级（2~5 级）"],
        materials=["过程文档", "项目证据", "评估材料"],
        timing="全年",
        policy_basis="CMMI 模型",
        benefit="软件企业资信/投标关键",
        match_signals=["软件", "信息技术", "研发"],
    ),
]


# ============================ 结构化条件 triage（2026-06-16） ============================
# 能力② 差距分析只对 `structured_conditions` 做确定性核验，而结构化的前提是：条件能映射到企业档案
# 的 9 个数值指标(成立年限/总人数/研发人数/研发占比/研发投入占比/发明专利/知识产权总数/注册资本/营收)，
# 且门槛**口径稳定、全适用人群一致**。逐条核过 25 条后，实际可结构化的极少，按风险纪律宁缺毋滥：
#
# 已结构化(2 条)：
# - high-tech-enterprise：成立满 1 年(GTE)、科技人员占比≥10%(GTE)。
# - tech-sme：职工≤500 人、营收≤2 亿(均 LTE，115 号全行业统一硬上限)。
#
# 刻意不结构化(其余 23 条，留 manual_review / 由 A2 能力③ Agent 结合政策原文深化)，原因分类：
# - 软/文本条件：体系类(iso9001/14001/45001/27001/cmmi、ipr-standard、two-integration、
#   js-industrial-design、js-smart-manufacturing)"建立并运行体系"；单项冠军/瞪羚/独角兽的
#   "市场占有率领先/高成长/估值"——档案无对应字段或无法量化。
# - 分档/分行业阈值：专精特新各级(spec-new-little-giant、js-spec-new、wx-spec-new)按行业划型、
#   研发费用/营收分档；技术中心/工程中心各级(national-tech-center、js/wx-tech-center、
#   js/wx-engineering-center)研发投入/人员/设备按层级分档——单一 GTE/LTE 表达不准，错填比不填更糟。
# - 前置/地区类：xinwu-bonus(获上级资质 + 新吴区注册纳税)、js-gazelle(高企前置)——已由
#   prerequisites + 地区匹配覆盖，无需再结构化。
# - 历史/趋势类：高成长(营收净利连续增长)需历史多年数据，单时点档案无法核验。
#
# 复核纪律：上述两条的数值取自对应《办法》的稳定硬条件；逐年微调的分档门槛(如高企研发费用占比)
# 仍走 manual_review，待 banded 条件建模后再结构化(见 STATUS 后续项)。
_CATALOG: List[Qualification] = _NATIONAL + _JIANGSU + _WUXI + _GENERAL


def load_qualification_catalog() -> List[Qualification]:
    """加载资质目录（静态数据，返回副本避免外部修改影响共享列表）。"""
    return list(_CATALOG)
