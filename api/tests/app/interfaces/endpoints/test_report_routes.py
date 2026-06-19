"""政策匹配简报端点测试（离线）：鉴权 + PDF 响应 + 限当前租户作用域。

不进 lifespan（TestClient 不进上下文管理器即不连库）；覆盖 get_token_service 使真实
get_current_user 仍跑，覆盖 get_report_service 为记录被调租户的间谍，断言用令牌租户而非客户端输入。
"""

import pytest
from fastapi.testclient import TestClient

from app.application.errors.exceptions import UnauthorizedError
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.report import ReportData
from app.interfaces import service_dependencies as deps
from app.main import app

TENANT_A, USER_A, TOKEN_A = "tenant-a", "user-a", "tok-a"


class _FakeTokenService:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping

    def decode(self, token: str) -> dict:
        claims = self._mapping.get(token)
        if claims is None:
            raise UnauthorizedError("无效的访问令牌")
        return claims


class _SpyReportService:
    """间谍简报服务：记录被调租户，返回固定 ReportData。"""

    def __init__(self) -> None:
        self.calls: list = []

    async def build_brief(self, tenant_id: str) -> ReportData:
        self.calls.append(tenant_id)
        return ReportData(
            tenant_id=tenant_id,
            profile=EnterpriseProfile(tenant_id=tenant_id, company_name="A 公司"),
        )


@pytest.fixture()
def spy() -> _SpyReportService:
    return _SpyReportService()


@pytest.fixture()
def client(spy: _SpyReportService) -> TestClient:
    token_service = _FakeTokenService({
        TOKEN_A: {"sub": USER_A, "tid": TENANT_A, "role": "owner", "type": "access"},
    })
    overrides = {
        deps.get_token_service: lambda: token_service,
        deps.get_report_service: lambda: spy,
    }
    app.dependency_overrides.update(overrides)
    try:
        yield TestClient(app)
    finally:
        for key in overrides:
            app.dependency_overrides.pop(key, None)


def test_export_brief_returns_pdf_for_authorized_user(client: TestClient, spy: _SpyReportService):
    resp = client.get("/api/reports/policy-brief", headers={"Authorization": f"Bearer {TOKEN_A}"})

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert "attachment" in resp.headers["content-disposition"]
    # 用令牌里的租户作用域，而非任何客户端输入
    assert spy.calls == [TENANT_A]


def test_export_brief_requires_auth(client: TestClient):
    resp = client.get("/api/reports/policy-brief")
    assert resp.status_code == 401


def test_export_brief_rejects_bad_token(client: TestClient):
    resp = client.get("/api/reports/policy-brief", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401
