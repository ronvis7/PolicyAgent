"""政策匹配简报路由（主线尾巴）：把已算出的匹配/差距/临期组装成 PDF 一键导出。

所有登录用户，限当前租户：简报只取 current_user.tenant_id 的档案与已物化机会，不跨租户。
不触发重算，纯读取已有结果渲染，故无副作用。
"""

import logging
import urllib.parse

from fastapi import APIRouter, Depends
from starlette.responses import Response as RawResponse

from app.application.services.report_service import ReportService
from app.infrastructure.report.pdf_renderer import render_brief
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.service_dependencies import get_report_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["政策匹配简报"])


@router.get(
    path="/policy-brief",
    summary="导出政策匹配简报（PDF）",
    description=(
        "把当前租户的企业画像 + 匹配政策 + 资质差距分析 + 临期申报提醒组装为一份 PDF 简报。"
        "纯组装已有匹配结果、不触发重算、不引入新数据源；差距/截止均附免责声明。"
    ),
)
async def export_policy_brief(
        current_user: CurrentUser = Depends(get_current_user),
        service: ReportService = Depends(get_report_service),
) -> RawResponse:
    """生成并下载政策匹配简报 PDF。"""
    data = await service.build_brief(current_user.tenant_id)
    pdf = render_brief(data)

    company = data.profile.company_name or "企业"
    filename = f"{company}-政策匹配简报-{data.generated_at:%Y%m%d}.pdf"
    encoded = urllib.parse.quote(filename)
    return RawResponse(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded}",
            "Content-Length": str(len(pdf)),
        },
    )
