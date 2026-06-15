"""policy_matcher 纯函数单测：词表抽取、结构化命中打分、地区判定、RRF 融合。

全部为无 IO 纯函数，直接断言，不需异步驱动。
"""

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.policy import Policy
from app.domain.services.policy_matcher import (
    build_profile_query,
    extract_profile_terms,
    reciprocal_rank_fusion,
    region_matches,
    score_terms,
    structured_score,
)


def _profile(**kw) -> EnterpriseProfile:
    return EnterpriseProfile(tenant_id="t1", **kw)


def _policy(title: str = "", body: str = "", region: str = "江苏省无锡市新吴区") -> Policy:
    return Policy(source_url="u", title=title, body_text=body, region=region)


# ---------- extract_profile_terms ----------

def test_extract_terms_merges_dedup_and_strips() -> None:
    profile = _profile(
        keywords=["高新", " 高新 ", "研发"],
        tech_domains=["集成电路"],
        qualifications=["专精特新"],
        industry="电子信息",
    )
    terms = extract_profile_terms(profile)
    # 去重保序(高新只一次)，空白被裁剪，行业并入
    assert terms == ["高新", "研发", "集成电路", "专精特新", "电子信息"]


def test_extract_terms_empty_profile_returns_empty() -> None:
    assert extract_profile_terms(_profile()) == []


# ---------- build_profile_query ----------

def test_build_query_joins_nonempty_fields() -> None:
    profile = _profile(
        industry="电子信息", main_business="芯片设计",
        tech_domains=["集成电路"], keywords=["流片"],
    )
    query = build_profile_query(profile)
    assert query == "电子信息 芯片设计 集成电路 流片"


# ---------- region_matches ----------

def test_region_matches_by_district_then_city() -> None:
    assert region_matches(_profile(), _policy(region="江苏省无锡市新吴区")) is True
    # 区不匹配但市匹配
    p = _profile(district="梁溪区")
    assert region_matches(p, _policy(region="无锡市全域")) is True
    # 都不匹配
    assert region_matches(_profile(), _policy(region="苏州市")) is False
    # 政策无地区
    assert region_matches(_profile(), _policy(region="")) is False


# ---------- structured_score ----------

def test_structured_score_title_outweighs_body() -> None:
    profile = _profile(keywords=["高新", "研发"])
    in_title = _policy(title="高新技术企业认定", body="无关")
    in_body = _policy(title="某通知", body="支持企业研发活动")

    s_title, m_title = structured_score(profile, in_title)
    s_body, m_body = structured_score(profile, in_body)

    assert m_title == ["高新"] and m_body == ["研发"]
    assert s_title > s_body  # 标题命中权重更高


def test_score_terms_uses_precomputed_terms() -> None:
    # 直接传入词表(服务层抽取一次复用的路径)，空词表短路
    score, matched = score_terms(["高新"], _policy(title="高新技术企业"))
    assert matched == ["高新"] and score > 0
    assert score_terms([], _policy(title="高新技术企业")) == (0.0, [])


def test_structured_score_no_terms_or_no_hit_is_zero() -> None:
    assert structured_score(_profile(), _policy(title="任意")) == (0.0, [])
    profile = _profile(keywords=["半导体"])
    assert structured_score(profile, _policy(title="农业补贴")) == (0.0, [])


def test_structured_score_normalized_within_unit_interval() -> None:
    profile = _profile(keywords=["高新", "研发", "孵化"])
    policy = _policy(title="高新 研发 孵化 全部命中")
    score, matched = structured_score(profile, policy)
    assert matched == ["高新", "研发", "孵化"]
    assert score == 1.0  # 全部词标题命中 = 满分


# ---------- reciprocal_rank_fusion ----------

def test_rrf_rewards_items_in_both_rankings() -> None:
    structured = ["p1", "p2", "p3"]
    semantic = ["p3", "p4"]
    fused = reciprocal_rank_fusion([structured, semantic])
    # p3 两路都召回，融合分应高于仅单路出现的 p1
    assert fused["p3"] > fused["p1"]
    assert fused["p3"] > fused["p4"]
    # 单一列表内名次靠前分更高
    assert fused["p1"] > fused["p2"]


def test_rrf_empty_rankings_returns_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == {}
