"""企业档案上下文渲染(Agent 的"实体长期记忆"注入)。

把当前租户的结构化企业档案渲染成一段系统提示词上下文块，在会话启动时注入
Planner / ReAct 两个 Agent 的首条 system 消息。这样 Agent 每轮都"知道"自己
服务于哪家企业、其档案是什么——问资质/政策匹配/差距时直接用档案与工具分析，
而不会反过来向用户索取早已填好的企业信息。

纯函数、无副作用，便于单测。档案为空时返回引导用户去「企业档案」页填写的提示块。
"""

from typing import List, Optional

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale

# 企业规模枚举 → 人读标签(与前端 SCALE_LABEL 口径一致)
_SCALE_LABEL = {
    EnterpriseScale.UNSPECIFIED: "未填写",
    EnterpriseScale.MICRO: "微型企业",
    EnterpriseScale.SMALL: "小型企业",
    EnterpriseScale.MEDIUM: "中型企业",
    EnterpriseScale.LARGE: "大型企业",
}

# 档案为空时的上下文块：引导去档案页一键填写，而非在对话里逐项追问
_EMPTY_CONTEXT = (
    "\n\n<enterprise_profile>\n"
    "当前登录企业尚未填写企业档案。\n"
    "当用户询问'我能申报哪些资质 / 政策匹配 / 差距分析'等需要企业信息的问题时，"
    "请引导用户前往左侧「企业档案」页面一键完善（一次填写、后续自动使用），"
    "不要在对话中逐项追问企业的名称 / 行业 / 规模等基础信息。\n"
    "</enterprise_profile>"
)


def _is_empty(profile: Optional[EnterpriseProfile]) -> bool:
    """企业档案是否视为空(尚未填写企业名称即视为空档案)。"""
    return profile is None or not profile.company_name.strip()


def render_enterprise_context(profile: Optional[EnterpriseProfile]) -> str:
    """把企业档案渲染为系统提示词上下文块。

    返回值以 `\\n\\n` 开头，便于直接拼接到系统提示词尾部；档案为空时返回引导填写的提示块。
    经营与研发指标仅渲染"已填写"项(区分未填写与 0)。
    """
    if _is_empty(profile):
        return _EMPTY_CONTEXT

    lines: List[str] = [f"- 企业名称：{profile.company_name}"]

    region = " ".join(p for p in (profile.province, profile.city, profile.district) if p).strip()
    if region:
        lines.append(f"- 所在地：{region}")
    if profile.industry:
        lines.append(f"- 所属行业：{profile.industry}")
    if profile.scale != EnterpriseScale.UNSPECIFIED:
        lines.append(f"- 企业规模：{_SCALE_LABEL.get(profile.scale, '未填写')}")
    if profile.main_business:
        lines.append(f"- 主营业务：{profile.main_business}")
    if profile.qualifications:
        lines.append(f"- 已有资质：{'、'.join(profile.qualifications)}")
    if profile.tech_domains:
        lines.append(f"- 技术/产品领域：{'、'.join(profile.tech_domains)}")
    if profile.keywords:
        lines.append(f"- 关键词：{'、'.join(profile.keywords)}")
    if profile.established_date:
        lines.append(f"- 成立日期：{profile.established_date}")

    # 经营与研发指标(仅已填写项；None=未填写、不渲染，避免与"填了0"混淆)
    metrics: List[str] = []
    if profile.total_staff is not None:
        metrics.append(f"员工总数 {profile.total_staff} 人")
    if profile.rd_staff is not None:
        metrics.append(f"研发人员 {profile.rd_staff} 人")
    if profile.registered_capital_wan is not None:
        metrics.append(f"注册资本 {profile.registered_capital_wan} 万元")
    if profile.annual_revenue_wan is not None:
        metrics.append(f"上年度营收 {profile.annual_revenue_wan} 万元")
    if profile.rd_investment_wan is not None:
        metrics.append(f"上年度研发投入 {profile.rd_investment_wan} 万元")
    if profile.invention_patents is not None:
        metrics.append(f"发明专利 {profile.invention_patents} 件")
    if profile.other_ip_count is not None:
        metrics.append(f"其他知识产权 {profile.other_ip_count} 件")
    if metrics:
        lines.append(f"- 经营与研发指标：{'；'.join(metrics)}")

    body = "\n".join(lines)
    return (
        "\n\n<enterprise_profile>\n"
        "你正在服务于以下这家已登录的企业，其结构化档案如下（系统已自动加载）。\n"
        "回答政策匹配、资质申报、差距分析等问题时，直接基于此档案与相应工具"
        "（如 qualification_list / qualification_gap / knowledge_base_search）分析，"
        "无需再向用户索取这些已知信息。\n\n"
        f"{body}\n"
        "</enterprise_profile>"
    )
