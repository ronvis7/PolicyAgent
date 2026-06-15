"""PolicyMatchService 离线单测：结构化+语义双路融合、空档案短路、语义聚合到政策。

用内存级 UoW(含 policy/document_chunk/enterprise_profile) + 关键词驱动的伪 embedding，
不依赖真实数据库与向量服务。异步方法用 asyncio.run 驱动(与本仓库其他测试一致)。
"""

import asyncio
from datetime import date
from typing import List

from app.application.services.policy_ingest_service import PUBLIC_KB_ID, PUBLIC_TENANT_ID
from app.application.services.policy_match_service import PolicyMatchService
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.policy import Policy

from ._fakes import make_uow_factory


class KeywordEmbedding:
    """关键词驱动的伪 embedding：含「芯片」的文本向量偏向第一维，便于断言语义排序。"""

    @property
    def model_name(self) -> str:
        return "kw-embed"

    def _vec(self, text: str) -> List[float]:
        return [1.0 if "芯片" in text else 0.0, 1.0 if "农业" in text else 0.0, 0.1]

    async def embed_query(self, text: str) -> List[float]:
        return self._vec(text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._vec(t) for t in texts]


def _policy(url: str, title: str, body: str = "", d: date = date(2026, 6, 1)) -> Policy:
    return Policy(source="wnd", source_url=url, title=title, body_text=body,
                  region="江苏省无锡市新吴区", publish_date=d)


def _public_chunk(policy: Policy, content: str) -> DocumentChunk:
    return DocumentChunk(
        tenant_id=PUBLIC_TENANT_ID, knowledge_base_id=PUBLIC_KB_ID,
        knowledge_file_id=f"kf-{policy.source_url}", content=content,
        chunk_metadata={"source_url": policy.source_url, "title": policy.title},
    )


def test_empty_profile_returns_no_matches() -> None:
    profiles = {"t1": EnterpriseProfile(tenant_id="t1")}  # 全空档案
    service = PolicyMatchService(
        make_uow_factory(enterprise_profiles=profiles, policies={"a": _policy("a", "某政策")}),
        KeywordEmbedding(),
    )
    assert asyncio.run(service.match_for_tenant("t1")) == []


def test_structured_only_when_no_public_chunks() -> None:
    profiles = {"t1": EnterpriseProfile(tenant_id="t1", keywords=["集成电路"])}
    policies = {
        "a": _policy("a", "集成电路企业奖励办法"),  # 标题命中
        "b": _policy("b", "农业补贴通知"),  # 不命中
    }
    service = PolicyMatchService(
        make_uow_factory(enterprise_profiles=profiles, policies=policies),
        KeywordEmbedding(),
    )

    matches = asyncio.run(service.match_for_tenant("t1"))

    assert [m.policy.source_url for m in matches] == ["a"]
    assert matches[0].matched_terms == ["集成电路"]
    assert matches[0].structured_score > 0
    assert any("命中关键词" in r for r in matches[0].reasons)


def test_combines_structured_and_semantic_paths() -> None:
    profiles = {"t1": EnterpriseProfile(
        tenant_id="t1", industry="电子信息", main_business="芯片设计", keywords=["集成电路"],
    )}
    # a：结构化命中(标题含"集成电路")，无公开库切片
    # b：结构化不命中，但公开库切片含"芯片"，语义可召回
    p_struct = _policy("a", "集成电路企业奖励办法")
    p_sem = _policy("b", "某产业扶持通知", body="支持芯片产业")
    policies = {"a": p_struct, "b": p_sem}
    chunk_store = {f"kf-{p_sem.source_url}": [(_public_chunk(p_sem, "支持芯片产业发展"), [1.0, 0.0, 0.1])]}

    service = PolicyMatchService(
        make_uow_factory(
            enterprise_profiles=profiles, policies=policies, document_chunks=chunk_store,
        ),
        KeywordEmbedding(),
    )

    matches = asyncio.run(service.match_for_tenant("t1"))
    by_url = {m.policy.source_url: m for m in matches}

    # 两路各自召回的政策都进入结果
    assert set(by_url) == {"a", "b"}
    # 结构化命中政策带命中词
    assert by_url["a"].matched_terms == ["集成电路"]
    # 语义召回政策带正相似度与语义理由
    assert by_url["b"].semantic_score > 0
    assert any("语义相关度" in r for r in by_url["b"].reasons)


def test_top_k_limits_results() -> None:
    profiles = {"t1": EnterpriseProfile(tenant_id="t1", keywords=["政策"])}
    policies = {f"u{i}": _policy(f"u{i}", f"政策{i}通知", d=date(2026, 6, i + 1)) for i in range(5)}
    service = PolicyMatchService(
        make_uow_factory(enterprise_profiles=profiles, policies=policies),
        KeywordEmbedding(),
    )

    matches = asyncio.run(service.match_for_tenant("t1", top_k=2))
    assert len(matches) == 2
