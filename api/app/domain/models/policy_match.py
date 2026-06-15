from typing import List

from pydantic import BaseModel, Field

from app.domain.models.policy import Policy


class PolicyMatch(BaseModel):
    """企业档案 × 公开政策的单条匹配候选（主线③匹配输出）。

    由结构化命中(档案关键词/技术域/资质/行业落在政策标题+正文)与语义召回(档案画像
    向量检索公开政策库)两路经 RRF 融合而成。`score` 为融合总分用于排序，
    `matched_terms`/`reasons` 提供「为什么推荐」的可解释依据，供前端候选页展示。
    """
    policy: Policy  # 命中的政策(含正文，供前端直接展示详情)
    score: float = 0.0  # RRF 融合总分(越大越靠前)
    structured_score: float = 0.0  # 结构化命中归一化分∈[0,1]
    semantic_score: float = 0.0  # 语义最高相似度∈[-1,1]
    matched_terms: List[str] = Field(default_factory=list)  # 命中的档案词(标题/正文)
    reasons: List[str] = Field(default_factory=list)  # 可读的推荐理由
