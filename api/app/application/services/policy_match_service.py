"""企业档案 × 公开政策匹配服务（主线③）。

即时计算、不落表：每次调用按当前租户档案现算政策候选，保证结果随档案/政策库实时更新。
结构化命中(档案词表 × 政策标题/正文)与语义召回(档案画像向量 × 公开政策库)两路各自
排序后经 RRF 融合，产出带「推荐理由」的候选列表，供前端候选页与后续④工作台 Feed 复用。
"""

import logging
from typing import Callable, List, Tuple

from app.application.services.policy_ingest_service import PUBLIC_KB_ID, PUBLIC_TENANT_ID
from app.domain.external.embedding import EmbeddingProvider
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.policy import Policy
from app.domain.models.policy_match import PolicyMatch
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.policy_matcher import (
    build_profile_query,
    extract_profile_terms,
    reciprocal_rank_fusion,
    region_matches,
    score_terms,
)

logger = logging.getLogger(__name__)

# top_k 取值边界，防止过大返回拖垮请求与前端
DEFAULT_TOP_K = 20
MAX_TOP_K = 50
# 结构化候选扫描上限(取最近 N 篇打分；公开库当前单区域，N 足够覆盖)
_STRUCT_CANDIDATE_LIMIT = 500
# 语义检索召回的切片数(聚合到政策后通常更少)
_SEM_CHUNK_TOP_K = 30


class PolicyMatchService:
    """企业档案 × 公开政策的即时匹配服务(结构化 + 语义，RRF 融合)"""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        embedding: EmbeddingProvider,
    ) -> None:
        self._uow_factory = uow_factory
        self._embedding = embedding

    async def match_for_tenant(
        self, tenant_id: str, top_k: int = DEFAULT_TOP_K,
    ) -> List[PolicyMatch]:
        """按租户档案匹配公开政策，返回融合排序后的候选(空档案返回空列表)。"""
        top_k = max(1, min(MAX_TOP_K, top_k or DEFAULT_TOP_K))

        async with self._uow_factory() as uow:
            profile = await uow.enterprise_profile.get_by_tenant(tenant_id)
        if profile is None:
            profile = EnterpriseProfile(tenant_id=tenant_id)

        # 无任何可匹配信号(关键词/技术域/资质/行业/主营全空)时直接返回，避免无意义检索
        terms = extract_profile_terms(profile)
        query = build_profile_query(profile)
        if not terms and not query:
            return []

        structured = await self._structured_candidates(profile, terms)
        semantic = await self._semantic_candidates(query)
        return self._fuse(profile, structured, semantic, top_k)

    async def _structured_candidates(
        self, profile: EnterpriseProfile, terms: List[str],
    ) -> List[Tuple[Policy, float, List[str]]]:
        """对最近候选政策做结构化命中打分(含地区加成)，保留有命中的，按分倒序。

        terms 由调用方抽取一次后传入，避免对每篇候选重复构建档案词表。
        """
        if not terms:
            return []
        async with self._uow_factory() as uow:
            candidates = await uow.policy.list_candidates(_STRUCT_CANDIDATE_LIMIT)

        scored: List[Tuple[Policy, float, List[str]]] = []
        for policy in candidates:
            score, matched = score_terms(terms, policy, region_matches(profile, policy))
            if score > 0:
                scored.append((policy, score, matched))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    async def _semantic_candidates(self, query: str) -> List[Tuple[Policy, float]]:
        """用档案画像查询向量检索公开政策库，聚合切片到政策(取最高相似度)。"""
        if not query:
            return []
        query_embedding = await self._embedding.embed_query(query)
        if not query_embedding:
            return []

        async with self._uow_factory() as uow:
            hits = await uow.document_chunk.search_similar(
                knowledge_base_id=PUBLIC_KB_ID,
                tenant_id=PUBLIC_TENANT_ID,
                query_embedding=query_embedding,
                top_k=_SEM_CHUNK_TOP_K,
            )
            # 同一政策可能命中多个切片：按 source_url 聚合，取最高相似度
            best_by_url: dict = {}
            for chunk, sim in hits:
                url = (chunk.chunk_metadata or {}).get("source_url")
                if url and sim > best_by_url.get(url, float("-inf")):
                    best_by_url[url] = sim

            # 批量回查政策(一次 IN 查询)，避免逐 url 的 N+1
            policies = await uow.policy.list_by_source_urls(list(best_by_url.keys()))

        results = [(p, best_by_url[p.source_url]) for p in policies if p.source_url in best_by_url]
        results.sort(key=lambda item: item[1], reverse=True)
        return results

    def _fuse(
        self,
        profile: EnterpriseProfile,
        structured: List[Tuple[Policy, float, List[str]]],
        semantic: List[Tuple[Policy, float]],
        top_k: int,
    ) -> List[PolicyMatch]:
        """RRF 融合两路有序候选，组装带推荐理由的 PolicyMatch，取前 top_k。"""
        struct_ids = [p.id for p, _, _ in structured]
        sem_ids = [p.id for p, _ in semantic]
        fused = reciprocal_rank_fusion([struct_ids, sem_ids])

        struct_map = {p.id: (score, matched) for p, score, matched in structured}
        sem_map = {p.id: sim for p, sim in semantic}
        by_id = {p.id: p for p, _, _ in structured}
        for policy, _ in semantic:
            by_id.setdefault(policy.id, policy)

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        matches: List[PolicyMatch] = []
        for policy_id, fused_score in ranked:
            policy = by_id[policy_id]
            structured_s, matched = struct_map.get(policy_id, (0.0, []))
            semantic_s = sem_map.get(policy_id, 0.0)
            matches.append(PolicyMatch(
                policy=policy,
                score=fused_score,
                structured_score=structured_s,
                semantic_score=semantic_s,
                matched_terms=matched,
                reasons=self._build_reasons(
                    profile, policy, matched, semantic_s, policy_id in sem_map,
                ),
            ))
        return matches

    @staticmethod
    def _build_reasons(
        profile: EnterpriseProfile,
        policy: Policy,
        matched: List[str],
        semantic_s: float,
        in_semantic: bool,
    ) -> List[str]:
        """构建可读推荐理由：命中关键词 / 地区匹配 / 语义相关度。"""
        reasons: List[str] = []
        if matched:
            reasons.append(f"命中关键词：{'、'.join(matched)}")
        if region_matches(profile, policy):
            reasons.append(f"地区匹配：{policy.region}")
        if in_semantic and semantic_s > 0:
            reasons.append(f"语义相关度 {semantic_s:.2f}")
        return reasons
