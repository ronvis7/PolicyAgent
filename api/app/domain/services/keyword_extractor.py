"""从企业自述文本提取候选关键词（帮用户把档案关键词填到位，提升 ③ 结构化命中）。

纯函数、无 IO：用 jieba 的 TF-IDF 关键词抽取(自带 IDF 语料)从主营业务/行业描述里挑出
名词性候选词，过滤停用词与已存在项。建议词来自企业自己的描述——这些词最可能也出现在
与之相关的政策文本里，因而对 structured_score 命中最有帮助。
"""

from typing import Iterable, List

import jieba.analyse

# 候选词通用停用：行业/公文高频词命中价值低，避免刷出无区分度的建议
_STOPWORDS = frozenset({
    "企业", "公司", "政策", "通知", "管理", "发展", "工作", "实施", "办法",
    "关于", "推进", "建设", "支持", "促进", "我市", "我区", "主要", "提供",
    "服务", "产品", "技术", "领域", "业务", "从事", "致力", "专业", "相关",
    "包括", "以及", "公司主", "目前", "通过", "实现", "应用", "系统", "解决方案",
})
# 最短候选词长(单字噪声大、无区分度)
_MIN_LEN = 2


def suggest_keywords(
    text: str, exclude: Iterable[str] = (), top_k: int = 12,
) -> List[str]:
    """从文本抽取候选关键词，过滤停用词与 exclude(已填项)，按相关度返回至多 top_k 个。"""
    if not text or not text.strip():
        return []

    exclude_set = {(e or "").strip() for e in exclude if e and e.strip()}
    # 多取一些再过滤，保证过滤后仍有足量候选
    tags = jieba.analyse.extract_tags(text, topK=max(1, top_k) * 3)

    out: List[str] = []
    seen: set = set()
    for raw in tags:
        tag = raw.strip()
        if (
            len(tag) < _MIN_LEN
            or tag in _STOPWORDS
            or tag in exclude_set
            or tag in seen
        ):
            continue
        seen.add(tag)
        out.append(tag)
        if len(out) >= top_k:
            break
    return out
