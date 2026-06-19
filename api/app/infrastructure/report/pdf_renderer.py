"""政策匹配简报 PDF 渲染器（纯函数：ReportData -> bytes）。

用 reportlab platypus 排版，中文走 Adobe CID 字体 `STSong-Light`（reportlab 内置、无需打包
TTF、Docker 无系统原生依赖）。渲染只读 ReportData、不触任何 IO，便于离线冒烟测试。

风险纪律：资质差距与临期区块强制带免责声明 + 末次核对日期，与目录/截止口径一致。
"""

import io
from typing import List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale
from app.domain.models.feed_item import FeedItem
from app.domain.models.qualification import ConditionStatus, QualificationGapReport
from app.domain.models.report import ReportData

_CN_FONT = "STSong-Light"  # reportlab 内置 CID 中文字体
_FONT_REGISTERED = False

_SCALE_LABELS = {
    EnterpriseScale.UNSPECIFIED: "未填写",
    EnterpriseScale.MICRO: "微型企业",
    EnterpriseScale.SMALL: "小型企业",
    EnterpriseScale.MEDIUM: "中型企业",
    EnterpriseScale.LARGE: "大型企业",
}

_STATUS_LABELS = {
    ConditionStatus.MET: "达标",
    ConditionStatus.UNMET: "不达标",
    ConditionStatus.UNKNOWN: "待确认",
}


def _para(text: object, style: ParagraphStyle) -> Paragraph:
    """转义后构造段落：reportlab Paragraph 解析 mini-HTML，数据里的 & < > 不转义会抛异常。"""
    return Paragraph(escape(str(text)), style)


def _ensure_font() -> None:
    """惰性注册中文字体（重复注册无副作用，但避免导入期开销）。"""
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(UnicodeCIDFont(_CN_FONT))
        _FONT_REGISTERED = True


def _styles() -> dict:
    """构造一套中文段落样式。"""
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "CnTitle", parent=base["Title"], fontName=_CN_FONT, fontSize=20, alignment=TA_CENTER,
    )
    sub = ParagraphStyle(
        "CnSub", parent=base["Normal"], fontName=_CN_FONT, fontSize=10,
        alignment=TA_CENTER, textColor=colors.grey,
    )
    h2 = ParagraphStyle(
        "CnH2", parent=base["Heading2"], fontName=_CN_FONT, fontSize=13, spaceBefore=10,
        spaceAfter=6, textColor=colors.HexColor("#1f4e79"),
    )
    body = ParagraphStyle("CnBody", parent=base["Normal"], fontName=_CN_FONT, fontSize=9, leading=13)
    cell = ParagraphStyle("CnCell", parent=body, fontSize=8.5, leading=11)
    note = ParagraphStyle(
        "CnNote", parent=body, fontSize=7.5, leading=10, textColor=colors.grey,
    )
    return {"title": title, "sub": sub, "h2": h2, "body": body, "cell": cell, "note": note}


def _profile_section(profile: EnterpriseProfile, st: dict) -> list:
    """企业画像区块。"""
    region = f"{profile.province}{profile.city}{profile.district}".strip()
    rows = [
        ("企业名称", profile.company_name or "—"),
        ("所在地区", region or "—"),
        ("所属行业", profile.industry or "—"),
        ("企业规模", _SCALE_LABELS.get(profile.scale, "未填写")),
        ("主营业务", profile.main_business or "—"),
        ("已有资质", "、".join(profile.qualifications) or "—"),
        ("技术领域", "、".join(profile.tech_domains) or "—"),
    ]
    data = [[_para(k, st["cell"]), _para(v, st["cell"])] for k, v in rows]
    table = Table(data, colWidths=[28 * mm, 142 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f3f6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [Paragraph("企业画像", st["h2"]), table, Spacer(1, 6)]


def _deadline_text(item: FeedItem) -> str:
    """申报截止的人读文案。"""
    if item.deadline_status == "extracted" and item.apply_deadline:
        return item.apply_deadline.isoformat()
    if item.deadline_status == "rolling":
        return "常年受理"
    return "—"


def _policies_section(policies: List[FeedItem], st: dict) -> list:
    """匹配政策区块。"""
    if not policies:
        return [Paragraph("匹配政策", st["h2"]), Paragraph("暂无匹配到的政策。", st["body"])]
    # 展示用「命中度/语义」与网页卡片口径一致；RRF 总分(score)仅用于排序、不展示
    # （RRF 分受 k=60 压制天然在 0.02 上下且名次相邻几乎同值，对用户无意义）
    header = [Paragraph(h, st["cell"]) for h in ("#", "政策标题", "发文机构", "命中度", "语义", "申报截止")]
    data = [header]
    for idx, p in enumerate(policies, 1):
        semantic = f"{p.semantic_score:.2f}" if p.semantic_score > 0 else "—"
        data.append([
            _para(idx, st["cell"]),
            _para(p.title or "—", st["cell"]),
            _para(p.issuer or "—", st["cell"]),
            _para(f"{p.structured_score * 100:.0f}%", st["cell"]),
            _para(semantic, st["cell"]),
            _para(_deadline_text(p), st["cell"]),
        ])
    table = Table(
        data, colWidths=[8 * mm, 80 * mm, 34 * mm, 16 * mm, 14 * mm, 18 * mm], repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [Paragraph("匹配政策", st["h2"]), table, Spacer(1, 6)]


def _gap_block(gap: QualificationGapReport, st: dict) -> KeepTogether:
    """单条资质差距分析（标题 + 总览 + 逐条结论 + 待确认 + 免责）。"""
    flow: list = [
        _para(gap.qualification.name, st["body"]),
        _para(
            f"达标 {gap.met_count} / 不达标 {gap.unmet_count} / 待确认 {gap.unknown_count}"
            + (f"　{gap.summary}" if gap.summary else ""),
            st["note"],
        ),
    ]
    for check in gap.checks:
        label = _STATUS_LABELS.get(check.status, "待确认")
        flow.append(_para(f"· [{label}] {check.detail or check.label}", st["cell"]))
    for item in gap.manual_review:
        flow.append(_para(f"· [待确认] {item}", st["cell"]))
    for prereq in gap.prerequisites_missing:
        flow.append(_para(f"· [缺前置] {prereq}", st["cell"]))
    review = gap.qualification.last_reviewed
    flow.append(_para(
        gap.qualification.disclaimer + (f"（末次核对：{review}）" if review else ""), st["note"],
    ))
    flow.append(Spacer(1, 6))
    return KeepTogether(flow)


def _qualifications_section(gaps: List[QualificationGapReport], st: dict) -> list:
    """资质差距区块。"""
    if not gaps:
        return [
            Paragraph("资质差距分析", st["h2"]),
            Paragraph("暂无匹配到的资质（请先完善企业档案）。", st["body"]),
        ]
    blocks: list = [Paragraph("资质差距分析", st["h2"])]
    blocks.extend(_gap_block(g, st) for g in gaps)
    return blocks


def _expiring_section(expiring: List[FeedItem], st: dict) -> list:
    """临期申报区块。"""
    if not expiring:
        return []
    header = [Paragraph(h, st["cell"]) for h in ("机会", "申报截止")]
    data = [header]
    for item in expiring:
        data.append([
            _para(item.title or "—", st["cell"]),
            _para(_deadline_text(item), st["cell"]),
        ])
    table = Table(data, colWidths=[150 * mm, 20 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b45309")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [Paragraph("临期申报提醒（30 天内）", st["h2"]), table, Spacer(1, 6)]


def render_brief(data: ReportData) -> bytes:
    """把一份 ReportData 渲染为 PDF 字节流。"""
    _ensure_font()
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title="政策匹配简报",
    )

    company = data.profile.company_name or "企业"
    flow: list = [
        Paragraph("政策匹配简报", st["title"]),
        _para(
            f"{company}　·　生成于 {data.generated_at.strftime('%Y-%m-%d %H:%M')}", st["sub"],
        ),
        Spacer(1, 10),
    ]
    flow += _profile_section(data.profile, st)
    flow += _policies_section(data.matched_policies, st)
    flow += _qualifications_section(data.qualification_gaps, st)
    flow += _expiring_section(data.expiring, st)
    flow += [Spacer(1, 8), Paragraph(data.disclaimer, st["note"])]

    doc.build(flow)
    return buf.getvalue()
