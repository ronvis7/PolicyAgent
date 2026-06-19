"""关键词智能提取端点测试（离线）：鉴权 + 返回候选 + 排除已填项。

不进 lifespan；覆盖 get_token_service 使真实 get_current_user 仍跑。端点内核是纯函数
suggest_keywords，无需 service 覆盖。
"""

import pytest
from fastapi.testclient import TestClient

from app.application.errors.exceptions import UnauthorizedError
from app.interfaces import service_dependencies as deps
from app.main import app

TOKEN = "tok-a"


class _FakeTokenService:
    def decode(self, token: str) -> dict:
        if token != TOKEN:
            raise UnauthorizedError("无效的访问令牌")
        return {"sub": "user-a", "tid": "tenant-a", "role": "owner", "type": "access"}


@pytest.fixture()
def client() -> TestClient:
    app.dependency_overrides[deps.get_token_service] = lambda: _FakeTokenService()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(deps.get_token_service, None)


def _post(client: TestClient, body: dict):
    return client.post(
        "/api/enterprise-profile/keyword-suggestions",
        json=body,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


def test_suggestions_returned_for_business_text(client: TestClient):
    resp = _post(client, {"text": "公司专注集成电路设计与半导体测试，提供车规级芯片。", "exclude": []})
    assert resp.status_code == 200
    suggestions = resp.json()["data"]["suggestions"]
    assert any(s in suggestions for s in ("集成电路", "半导体", "芯片"))
    assert "公司" not in suggestions  # 停用词被过滤


def test_excluded_terms_not_suggested(client: TestClient):
    text = "主营工业机器人与自动化产线集成，深耕智能制造。"
    base = _post(client, {"text": text, "exclude": []}).json()["data"]["suggestions"]
    assert base
    again = _post(client, {"text": text, "exclude": [base[0]]}).json()["data"]["suggestions"]
    assert base[0] not in again


def test_empty_text_returns_empty(client: TestClient):
    resp = _post(client, {"text": "", "exclude": []})
    assert resp.status_code == 200
    assert resp.json()["data"]["suggestions"] == []


def test_requires_auth(client: TestClient):
    resp = client.post("/api/enterprise-profile/keyword-suggestions", json={"text": "x"})
    assert resp.status_code == 401
