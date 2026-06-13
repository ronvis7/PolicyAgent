from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.domain.models.membership import MembershipRole
from app.interfaces.schemas.auth import EMAIL_PATTERN


class MemberItem(BaseModel):
    """组织成员列表条目"""
    membership_id: str
    user_id: str
    email: str
    display_name: str
    role: str
    status: str
    created_at: datetime


class ListMembersResponse(BaseModel):
    """组织成员列表响应"""
    members: List[MemberItem] = Field(default_factory=list)


class AddMemberRequest(BaseModel):
    """按邮箱添加成员请求"""
    email: str = Field(pattern=EMAIL_PATTERN, description="待添加成员的邮箱")
    role: MembershipRole = MembershipRole.MEMBER


class ChangeRoleRequest(BaseModel):
    """变更成员角色请求"""
    role: MembershipRole
