import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.policy import Policy


class PolicyModel(Base):
    """公开政策ORM模型（全局共享层，非租户隔离）。

    source_url 唯一(去重键)；标量字段直接落列，正文 body_text 用 Text。
    无 tenant 外键——这是跨租户共享的公开政策库。
    """
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=lambda: str(uuid.uuid4()),
    )  # 政策id
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''"),
    )  # 来源标识(如 wnd)
    source_url: Mapped[str] = mapped_column(
        String(1024), nullable=False, unique=True, index=True,
    )  # 详情页URL(全局唯一，去重键)
    index_number: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''"),
    )  # 信息索引号
    title: Mapped[str] = mapped_column(
        String(512), nullable=False, server_default=text("''"),
    )  # 政策标题
    issuer: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''"),
    )  # 发布部门/发文机构
    doc_number: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''"),
    )  # 文号/发文字号
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''"),
    )  # 效力状况
    publish_date: Mapped[date] = mapped_column(
        Date, nullable=True, index=True,
    )  # 发文/公开日期
    body_text: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''"),
    )  # 政策正文纯文本
    region: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("''"), index=True,
    )  # 适用地区
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'policy'"), index=True)
    origin_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'official'"), index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    apply_deadline: Mapped[date] = mapped_column(
        Date, nullable=True, index=True,
    )  # 申报截止日期(LLM 抽取，仅 extracted 时有值；索引供临期查询)
    apply_window_text: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''"),
    )  # 原文申报窗口描述(展示+人工核对)
    deadline_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'unknown'"),
    )  # extracted / rolling / unknown
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 最近抓取时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 更新时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 创建时间

    @classmethod
    def from_domain(cls, policy: Policy) -> "PolicyModel":
        """从领域模型创建ORM模型"""
        return cls(
            id=policy.id,
            source=policy.source,
            source_url=policy.source_url,
            index_number=policy.index_number,
            title=policy.title,
            issuer=policy.issuer,
            doc_number=policy.doc_number,
            status=policy.status,
            publish_date=policy.publish_date,
            body_text=policy.body_text,
            region=policy.region,
            item_type=policy.item_type,
            origin_type=policy.origin_type,
            source_name=policy.source_name,
            apply_deadline=policy.apply_deadline,
            apply_window_text=policy.apply_window_text,
            deadline_status=policy.deadline_status,
            crawled_at=policy.crawled_at,
            updated_at=policy.updated_at,
            created_at=policy.created_at,
        )

    def to_domain(self) -> Policy:
        """将ORM模型转换为领域模型"""
        return Policy(
            id=self.id,
            source=self.source,
            source_url=self.source_url,
            index_number=self.index_number,
            title=self.title,
            issuer=self.issuer,
            doc_number=self.doc_number,
            status=self.status,
            publish_date=self.publish_date,
            body_text=self.body_text,
            region=self.region,
            item_type=self.item_type,
            origin_type=self.origin_type,
            source_name=self.source_name,
            apply_deadline=self.apply_deadline,
            apply_window_text=self.apply_window_text,
            deadline_status=self.deadline_status,
            crawled_at=self.crawled_at,
            updated_at=self.updated_at,
            created_at=self.created_at,
        )

    def update_from_domain(self, policy: Policy) -> None:
        """从领域模型更新业务字段(保留 id/source_url/created_at)"""
        self.source = policy.source
        self.index_number = policy.index_number
        self.title = policy.title
        self.issuer = policy.issuer
        self.doc_number = policy.doc_number
        self.status = policy.status
        self.publish_date = policy.publish_date
        self.body_text = policy.body_text
        self.region = policy.region
        self.item_type = policy.item_type
        self.origin_type = policy.origin_type
        self.source_name = policy.source_name
        self.apply_deadline = policy.apply_deadline
        self.apply_window_text = policy.apply_window_text
        self.deadline_status = policy.deadline_status
        self.crawled_at = policy.crawled_at
