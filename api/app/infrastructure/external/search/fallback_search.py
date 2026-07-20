import logging
from typing import Optional

from app.domain.external.search import SearchEngine
from app.domain.models.search import SearchResults
from app.domain.models.tool_result import ToolResult

logger = logging.getLogger(__name__)


class FallbackSearchEngine(SearchEngine):
    """主搜索不可用或无结果时调用备用搜索。"""

    def __init__(self, primary: SearchEngine, fallback: SearchEngine) -> None:
        self.primary = primary
        self.fallback = fallback

    async def invoke(self, query: str, date_range: Optional[str] = None) -> ToolResult[SearchResults]:
        result = await self.primary.invoke(query, date_range)
        if result.success and result.data and result.data.results:
            return result
        logger.warning("主搜索无可用结果，切换备用搜索: %s", result.message or "empty results")
        return await self.fallback.invoke(query, date_range)
