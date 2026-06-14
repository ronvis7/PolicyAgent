import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class Policy(BaseModel):
    """公开政策领域模型（全局共享层，非租户隔离）。

    主线②「公开政策库」的结构化载体：爬取权威源(首版无锡新吴区门户)后结构化入库，
    作为后续③匹配、④工作台 Feed 的数据地基。以 source_url 作为去重键(同一篇政策
    重复爬取走 upsert)。正文 body_text 另由入库编排复用 RAG 流水线 embedding 进
    全局公开知识库，支持语义检索。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 政策id
    source: str = ""  # 来源标识(如 wnd=无锡新吴区门户)
    source_url: str = ""  # 详情页URL(全局唯一，去重键)
    index_number: str = ""  # 信息索引号(来源站点编号)
    title: str = ""  # 政策标题
    issuer: str = ""  # 发布部门/发文机构
    doc_number: str = ""  # 文号/发文字号
    status: str = ""  # 效力状况(如 有效/废止)
    publish_date: Optional[date] = None  # 发文/公开日期
    body_text: str = ""  # 政策正文纯文本
    region: str = ""  # 适用地区(如 江苏省无锡市新吴区)
    crawled_at: datetime = Field(default_factory=datetime.now)  # 最近抓取时间
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
