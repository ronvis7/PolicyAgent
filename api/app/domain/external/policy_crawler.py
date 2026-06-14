from typing import List, Protocol

from app.domain.models.policy import Policy


class PolicyCrawler(Protocol):
    """公开政策爬虫接口协议：抓取权威源并产出结构化 Policy 列表。"""

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        """抓取最多 max_pages 页政策列表(含详情正文)，返回结构化政策。"""
        ...
