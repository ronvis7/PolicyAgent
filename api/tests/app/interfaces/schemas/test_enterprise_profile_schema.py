"""UpdateEnterpriseProfileRequest 的边界校验单测(A0 新增结构化字段)。

数值字段非负、成立日期格式宽松校验、to_domain 透传——这些是 owner/admin 提交档案时
的输入边界，错值应在 schema 层被拒，避免脏数据进 JSONB 污染后续差距分析。
"""

import pytest
from pydantic import ValidationError

from app.interfaces.schemas.enterprise_profile import UpdateEnterpriseProfileRequest


def test_to_domain_passes_structured_fields() -> None:
    req = UpdateEnterpriseProfileRequest(
        company_name="某科技",
        established_date="2019-06-01",
        total_staff=120,
        rd_staff=45,
        registered_capital_wan=1000.0,
        invention_patents=6,
    )

    profile = req.to_domain("tenant-a")

    assert profile.established_date == "2019-06-01"
    assert profile.total_staff == 120
    assert profile.rd_staff == 45
    assert profile.registered_capital_wan == 1000.0
    assert profile.invention_patents == 6
    assert profile.annual_revenue_wan is None  # 未填写保持 None


def test_to_domain_passes_contest_regions_cleaned() -> None:
    """参赛关注地区随请求进领域模型，并按标签规则清洗(去空白/去重)。"""
    req = UpdateEnterpriseProfileRequest(
        contest_regions=["江苏省", " 江苏省 ", "重庆市", ""],
    )

    profile = req.to_domain("tenant-a")

    assert profile.contest_regions == ["江苏省", "重庆市"]


@pytest.mark.parametrize("field", ["total_staff", "rd_staff", "invention_patents", "registered_capital_wan"])
def test_negative_numbers_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        UpdateEnterpriseProfileRequest(**{field: -1})


@pytest.mark.parametrize("value", ["2019", "2019-06", "2019-06-01", ""])
def test_valid_established_date_accepted(value: str) -> None:
    req = UpdateEnterpriseProfileRequest(established_date=value)
    assert req.established_date == value


@pytest.mark.parametrize("value", ["2019/06/01", "June 2019", "19-6-1", "not-a-date"])
def test_invalid_established_date_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        UpdateEnterpriseProfileRequest(established_date=value)


def test_defaults_are_all_empty() -> None:
    req = UpdateEnterpriseProfileRequest()
    assert req.established_date == ""
    assert req.total_staff is None
    assert req.annual_revenue_wan is None
    assert req.other_ip_count is None
