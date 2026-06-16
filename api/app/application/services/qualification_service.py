"""资质申报机会服务（主线⑥ 能力①）。

在静态资质目录之上，按当前租户企业档案做启发式匹配(确定性、不走向量)，产出
"可申报 / 接近可申报(差N项)"候选，供资质浏览页与 ④ 工作台 Feed 复用；并提供按 key 取详情。

目录从外部注入(infrastructure/data 提供 load_qualification_catalog)，便于离线测试替换为桩。
"""

import logging
from typing import Callable, List, Optional

from app.domain.models.qualification import Qualification, QualificationMatch
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.qualification_matcher import match_qualifications

logger = logging.getLogger(__name__)

# 资质目录有限(数十条)，默认返回足量覆盖全部适用项
DEFAULT_TOP_K = 50


class QualificationService:
    """资质目录匹配 + 详情读取服务。"""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        catalog: List[Qualification],
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = list(catalog)
        self._by_key = {q.key: q for q in self._catalog}

    async def match_for_tenant(
        self, tenant_id: str, top_k: int = DEFAULT_TOP_K,
    ) -> List[QualificationMatch]:
        """按租户档案匹配资质目录，排除地区不适用项；无档案返回空列表。"""
        async with self._uow_factory() as uow:
            profile = await uow.enterprise_profile.get_by_tenant(tenant_id)
        if profile is None:
            return []

        matches = match_qualifications(profile, self._catalog)
        return matches[: max(1, top_k)]

    def get_by_key(self, key: str) -> Optional[Qualification]:
        """按 key 取资质详情(目录为静态数据，纯内存查找)。"""
        return self._by_key.get(key)

    def list_catalog(self) -> List[Qualification]:
        """返回完整资质目录(浏览/管理用)。"""
        return list(self._catalog)
