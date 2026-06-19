"""企业档案 × 公开政策的纯函数匹配逻辑（主线③匹配的可测内核，无 IO）。

两路信号：
- 结构化命中：档案的关键词/技术域/资质/行业落在政策标题(权重高)与正文中。
- 语义召回：由档案画像拼成查询向量去检索公开政策库(在应用服务层完成)。

两路各自产出有序候选后，用 RRF(倒数排名融合)合并；融合只依赖名次而非异质分数，
避免结构化命中数与余弦相似度量纲不一致带来的偏置。
"""

from typing import Dict, List, Set, Tuple

import jieba

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.policy import Policy

# RRF 阻尼常数(标准取值 60)：弱化头部名次的极端影响，名次靠后仍有非零贡献
RRF_K = 60
# 命中权重：标题命中比正文命中更能代表政策主题
_TITLE_WEIGHT = 2.0
_BODY_WEIGHT = 1.0
# 命中分饱和点：一处标题命中≈0.5，分值随命中增长但不被"未命中的档案词"稀释
# (旧实现按全部词数归一，档案填得越全分越低，反直觉)
_SATURATION = 2.0
# 地区命中加成：仅在已有内容命中时叠加，避免"只地区匹配"的政策单独刷分
_REGION_BONUS = 0.15
# 分词最小词长：过滤单字/标点，单字 token 噪声大、易误命中
_MIN_TOKEN_LEN = 2
# 通用高频词停用：避免"企业管理"靠"企业"误命中任意惠企政策
_STOPWORDS = frozenset({
    "企业", "公司", "政策", "通知", "管理", "发展", "工作", "实施",
    "办法", "关于", "推进", "建设", "支持", "促进", "我市", "我区",
})


def _tokenize(text: str) -> Set[str]:
    """中文分词为 token 集合，过滤短词/停用词(降噪)。"""
    return {
        tok
        for raw in jieba.cut(text or "")
        if (tok := raw.strip()) and len(tok) >= _MIN_TOKEN_LEN and tok not in _STOPWORDS
    }


def _term_hits(term: str, text: str, text_tokens: Set[str]) -> bool:
    """档案词是否命中文本：原样子串(最强信号) 或 分词后任一有效子词落在文本 token 集。

    后者解决"长组合词不是短文本子串"的脆性，如档案「集成电路设计」命中标题「集成电路产业…」。
    """
    term = (term or "").strip()
    if not term or not text:
        return False
    if term in text:
        return True
    return any(
        (tok := raw.strip()) and len(tok) >= _MIN_TOKEN_LEN
        and tok not in _STOPWORDS and tok in text_tokens
        for raw in jieba.cut(term)
    )


def extract_profile_terms(profile: EnterpriseProfile) -> List[str]:
    """从档案抽取用于结构化命中的词表(关键词+技术域+资质+行业)，去空白并去重保序。"""
    raw: List[str] = []
    raw.extend(profile.keywords)
    raw.extend(profile.tech_domains)
    raw.extend(profile.qualifications)
    if profile.industry:
        raw.append(profile.industry)

    seen = set()
    terms: List[str] = []
    for term in raw:
        cleaned = (term or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            terms.append(cleaned)
    return terms


def build_profile_query(profile: EnterpriseProfile) -> str:
    """拼接档案要素为语义检索查询(行业+主营业务+技术域+关键词)。"""
    parts: List[str] = [profile.industry, profile.main_business]
    parts.extend(profile.tech_domains)
    parts.extend(profile.keywords)
    return " ".join(p.strip() for p in parts if p and p.strip())


def region_matches(profile: EnterpriseProfile, policy: Policy) -> bool:
    """政策适用地区是否覆盖档案所在地(按区→市逐级判断，命中其一即可)。"""
    region = policy.region or ""
    if not region:
        return False
    for level in (profile.district, profile.city):
        level = (level or "").strip()
        if level and level in region:
            return True
    return False


def score_terms(
    terms: List[str], policy: Policy, region_match: bool = False,
) -> Tuple[float, List[str]]:
    """给定档案词表，对单篇政策做加权命中打分(标题权重高于正文)。

    返回(命中分∈[0,1], 命中词列表)。空词表或零命中返回 (0.0, [])。命中判定走
    中文分词 token 重合(标题)+原样子串(正文)，比纯子串召回更稳；分值用饱和归一，
    随命中增长但不被未命中的档案词稀释。`region_match` 为真时在已有内容命中上叠加地区加成。
    入参 terms 由调用方预先抽取并复用，避免对每篇候选重复构建词表。
    """
    if not terms:
        return 0.0, []

    title = policy.title or ""
    body = policy.body_text or ""
    # 标题短、命中权重高，做分词；正文走子串以控成本(每篇全文分词代价高)
    title_tokens = _tokenize(title)
    matched: List[str] = []
    weight = 0.0
    for term in terms:
        if _term_hits(term, title, title_tokens):
            matched.append(term)
            weight += _TITLE_WEIGHT
        elif (term or "").strip() and term in body:
            matched.append(term)
            weight += _BODY_WEIGHT

    if weight == 0:
        return 0.0, []

    score = weight / (weight + _SATURATION)  # 饱和归一：不被未命中词稀释
    if region_match:
        score = min(1.0, score + _REGION_BONUS)
    return score, matched


def structured_score(profile: EnterpriseProfile, policy: Policy) -> Tuple[float, List[str]]:
    """从档案抽取词表后对单篇政策结构化打分(score_terms 的便捷封装，含地区加成)。"""
    return score_terms(
        extract_profile_terms(profile), policy, region_matches(profile, policy),
    )


def reciprocal_rank_fusion(rankings: List[List[str]], k: int = RRF_K) -> Dict[str, float]:
    """对多个有序 id 列表做 RRF 融合，返回 id->融合分(越大越靠前)。

    每个列表内排名第 r(从0起)的项贡献 1/(k+r+1)；同一 id 在多个列表出现则累加，
    天然奖励两路都召回的政策。
    """
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return scores
