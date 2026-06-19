"""政策匹配简报组装服务（主线尾巴：把已算出的情报组装成可导出交付物）。

不引入新数据源、不落新表，纯组装现有能力的结果：企业档案 + ③匹配政策(取自已物化的
工作台 Feed) + ⑥资质差距分析 + ⑤临期申报项。依赖以 Protocol 解耦，便于离线测试替桩。
"""

import logging
from typing import List, Optional, Protocol, Tuple

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedItemType, FeedStatus
from app.domain.models.qualification import QualificationGapReport, QualificationMatch
from app.domain.models.report import ReportData

logger = logging.getLogger(__name__)

# 简报纳入上限：政策取分数最高的前 N、资质差距取匹配度最高的前 N（避免简报过长）
TOP_POLICIES = 15
TOP_QUALIFICATIONS = 8
# 临期窗口：比 Feed 默认 14 天略宽，报告偏"近一个月需关注"
EXPIRING_WINDOW_DAYS = 30
# 先取足量 Feed 条目再在内存按分排序（Feed 列表默认按创建时间倒序，简报要的是按相关度）
_FEED_SCAN_SIZE = 200


class ProfileReader(Protocol):
    async def get_profile(self, tenant_id: str) -> EnterpriseProfile: ...


class FeedReader(Protocol):
    async def list_feed(
        self,
        tenant_id: str,
        status: Optional[FeedStatus] = ...,
        page: int = ...,
        page_size: int = ...,
    ) -> Tuple[List[FeedItem], int]: ...

    async def list_expiring(self, tenant_id: str, within_days: int) -> List[FeedItem]: ...


class QualificationReader(Protocol):
    async def match_for_tenant(
        self, tenant_id: str, top_k: int = ...,
    ) -> List[QualificationMatch]: ...

    async def analyze_gap_for_tenant(
        self, tenant_id: str, key: str,
    ) -> Optional[QualificationGapReport]: ...


class ReportService:
    """简报组装：聚合企业档案 + 匹配政策 + 资质差距 + 临期项为 ReportData。"""

    def __init__(
        self,
        profile_service: ProfileReader,
        feed_service: FeedReader,
        qualification_service: QualificationReader,
    ) -> None:
        self._profile_service = profile_service
        self._feed_service = feed_service
        self._qualification_service = qualification_service

    async def build_brief(self, tenant_id: str) -> ReportData:
        """组装当前租户的政策匹配简报（限当前租户，不触发重算）。"""
        profile = await self._profile_service.get_profile(tenant_id)
        matched_policies = await self._select_matched_policies(tenant_id)
        qualification_gaps = await self._select_qualification_gaps(tenant_id)
        expiring = await self._feed_service.list_expiring(tenant_id, EXPIRING_WINDOW_DAYS)

        logger.info(
            "简报组装完成 tenant=%s policies=%d gaps=%d expiring=%d",
            tenant_id, len(matched_policies), len(qualification_gaps), len(expiring),
        )
        return ReportData(
            tenant_id=tenant_id,
            profile=profile,
            matched_policies=matched_policies,
            qualification_gaps=qualification_gaps,
            expiring=expiring,
        )

    async def _select_matched_policies(self, tenant_id: str) -> List[FeedItem]:
        """从已物化 Feed 取政策类、剔除已忽略，按匹配分降序取前 N。"""
        items, _ = await self._feed_service.list_feed(
            tenant_id, status=None, page=1, page_size=_FEED_SCAN_SIZE,
        )
        policies = [
            item for item in items
            if item.type == FeedItemType.POLICY and item.status != FeedStatus.IGNORED
        ]
        policies.sort(key=lambda item: item.score, reverse=True)
        return policies[:TOP_POLICIES]

    async def _select_qualification_gaps(self, tenant_id: str) -> List[QualificationGapReport]:
        """取匹配度最高的前 N 条资质，逐条做差距分析（无档案/无资质则为空）。"""
        matches = await self._qualification_service.match_for_tenant(
            tenant_id, top_k=TOP_QUALIFICATIONS,
        )
        gaps: List[QualificationGapReport] = []
        for match in matches[:TOP_QUALIFICATIONS]:
            gap = await self._qualification_service.analyze_gap_for_tenant(
                tenant_id, match.qualification.key,
            )
            if gap is not None:
                gaps.append(gap)
        return gaps
