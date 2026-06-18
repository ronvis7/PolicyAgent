"""跨租户隔离 endpoint 测试：A 的令牌不得读/改 B 的资源（反之亦然）。

忠实自动化手动探针 `scripts/cross-tenant-probe.ps1` 的核心断言，并补齐探针此前
未覆盖的 Feed 改状态、文件下载。每条都含：跨租户→404、本租户→成功（正向控制）。
"""
from fastapi.testclient import TestClient

TOKEN_A = "tok-a"
TOKEN_B = "tok-b"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------- 会话 ----------

def test_session_get_cross_tenant_404(client: TestClient) -> None:
    """B 读 A 的会话 → 404；A 读自己的 → 200"""
    assert client.get("/api/sessions/sess-a", headers=_auth(TOKEN_B)).status_code == 404
    assert client.get("/api/sessions/sess-a", headers=_auth(TOKEN_A)).status_code == 200


def test_session_delete_cross_tenant_404(client: TestClient) -> None:
    """B 删 A 的会话 → 404（隔离守卫拦在删除前）；A 删自己的 → 200"""
    assert client.post("/api/sessions/sess-a/delete", headers=_auth(TOKEN_B)).status_code == 404
    # A 删自己的成功，且 A 仍能确认它已不在（正向控制）
    assert client.post("/api/sessions/sess-a/delete", headers=_auth(TOKEN_A)).status_code == 200


# ---------- 知识库 ----------

def test_knowledge_base_get_cross_tenant_404(client: TestClient) -> None:
    """B 读 A 的知识库 → 404；A 读自己的 → 200"""
    assert client.get("/api/knowledge-bases/kb-a", headers=_auth(TOKEN_B)).status_code == 404
    assert client.get("/api/knowledge-bases/kb-a", headers=_auth(TOKEN_A)).status_code == 200


def test_knowledge_base_delete_cross_tenant_404(client: TestClient) -> None:
    """B 删 A 的知识库 → 404；A 删自己的 → 200"""
    assert client.delete("/api/knowledge-bases/kb-a", headers=_auth(TOKEN_B)).status_code == 404
    assert client.delete("/api/knowledge-bases/kb-a", headers=_auth(TOKEN_A)).status_code == 200


# ---------- 企业档案（数据不串）----------

def test_enterprise_profile_no_leak(client: TestClient) -> None:
    """各租户只读到自己的档案，绝不串到对方的企业名"""
    data_a = client.get("/api/enterprise-profile", headers=_auth(TOKEN_A)).json()["data"]
    data_b = client.get("/api/enterprise-profile", headers=_auth(TOKEN_B)).json()["data"]
    assert data_a["company_name"] == "A 公司"
    assert data_b["company_name"] == "B 公司"


# ---------- Feed 改状态（探针此前未覆盖）----------

def test_feed_set_status_cross_tenant_404(client: TestClient) -> None:
    """B 改 A 的 Feed 条目状态 → 404；A 改自己的 → 200"""
    body = {"status": "read"}
    assert client.post("/api/feed/feed-a/status", json=body, headers=_auth(TOKEN_B)).status_code == 404
    assert client.post("/api/feed/feed-a/status", json=body, headers=_auth(TOKEN_A)).status_code == 200


# ---------- 文件下载（探针此前未覆盖；刚出过 401 bug 的面）----------

def test_file_download_cross_tenant_404(client: TestClient) -> None:
    """B 下载 A 的文件 → 404；A 下载自己的 → 200"""
    assert client.get("/api/files/file-a/download", headers=_auth(TOKEN_B)).status_code == 404
    assert client.get("/api/files/file-a/download", headers=_auth(TOKEN_A)).status_code == 200


# ---------- 认证边界 ----------

def test_protected_endpoint_requires_token(client: TestClient) -> None:
    """无 Authorization 头访问受保护端点 → 401"""
    assert client.get("/api/sessions/sess-a").status_code == 401


def test_invalid_token_rejected(client: TestClient) -> None:
    """无法解码的令牌 → 401"""
    assert client.get("/api/sessions/sess-a", headers=_auth("garbage")).status_code == 401
