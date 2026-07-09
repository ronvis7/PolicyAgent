from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SourceCrawlStateModel(Base):
    """每个来源(source)的最近一次抓取运行状态(全局共享，非租户隔离)。

    「数据来源」页的"最近更新"原本取 MAX(policies.crawled_at)——抓取到 0 条(全被保鲜
    过滤/门户无匹配)时没有政策行被写，时间戳不动，前端一直显示"尚未抓取"。本表按 source
    记录每次抓取的运行时刻与结果计数，与是否入库无关，使"跑过但 0 条"也能如实反映。
    """
    __tablename__ = "source_crawl_states"

    source: Mapped[str] = mapped_column(String(64), primary_key=True)  # 来源标识(如 cnmaker-contest)
    last_crawled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 最近一次抓取运行时刻(无论是否有新增)
    last_new_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )  # 最近一次首次入库(新增)条数
    last_crawled_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )  # 最近一次抓取到的总条数(去重后)
