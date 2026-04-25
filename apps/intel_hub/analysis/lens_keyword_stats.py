"""按 CategoryLens 视角统计跨笔记的词频 / TF-IDF / 热门短语。

用于 ``CategoryLensEngine`` 的第 1 层「内容信号层」——生成机会卡
``layer1_signals.hot_keywords`` 时需要：

- 每个 Lens 内限定候选词汇范围（避免爆词导致噪声）；
- 对候选词做 DF（多少篇笔记出现过）与 TF（所有笔记中出现总次数）；
- 计算 TF-IDF 指标：``tf * log((N + 1) / (df + 1)) + 1``；
- 按 TF-IDF 降序返回热门关键词列表。

不引入 sklearn 等重依赖，纯 Python 实现，方便测试。
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from apps.intel_hub.domain.category_lens import CategoryLens
from apps.intel_hub.schemas.content_frame import NoteContentFrame


@dataclass(slots=True)
class KeywordHit:
    keyword: str
    tf: int
    df: int
    tf_idf: float
    category: str | None = None


def _lens_candidate_pool(lens: CategoryLens) -> dict[str, str]:
    """返回 lens 候选词 → 归属维度 的字典。

    维度 key 仅做分类展示，实际排序以 TF-IDF 为准。
    """
    pool: dict[str, str] = {}

    def _add(words: Iterable[str], category: str) -> None:
        for w in words:
            w = w.strip()
            if w and w not in pool:
                pool[w] = category

    lex = lens.text_lexicons
    _add(lex.pain_words, "pain")
    _add(lex.emotion_words, "emotion")
    _add(lex.trust_barrier_words, "trust_barrier")
    _add(lex.comment_question_words, "comment_question")
    _add(lex.comment_trust_barrier_words, "comment_trust_barrier")
    for values in lex.scene_words.values():
        _add(values, "scene")
    for values in lex.style_words.values():
        _add(values, "style")
    for values in lex.audience_words.values():
        _add(values, "audience")
    for values in lex.product_feature_words.values():
        _add(values, "product_feature")
    for values in lex.content_pattern_words.values():
        _add(values, "content_pattern")
    _add(lens.keyword_aliases, "alias")
    _add(lens.product_feature_taxonomy, "product_feature")
    _add(lens.content_patterns, "content_pattern")
    return pool


def _collect_note_text(frame: NoteContentFrame, *, include_comments: bool = True) -> str:
    parts = [frame.title_text, frame.body_text, " ".join(frame.tag_list)]
    if include_comments:
        parts.extend(c.comment_text for c in frame.comments if c.comment_text)
        parts.extend(c.comment_text for c in frame.top_comments if c.comment_text)
        parts.extend(c.comment_text for c in frame.neg_comments if c.comment_text)
    return " ".join(parts)


def compute_lens_hot_keywords(
    frames: list[NoteContentFrame],
    lens: CategoryLens,
    *,
    top_k: int = 12,
    min_df: int = 1,
) -> list[KeywordHit]:
    """统计 lens 候选词在一组笔记里的 TF-IDF。

    Args:
        frames: 所有属于本 lens 的笔记帧。
        lens: 当前类目透镜。
        top_k: 返回的关键词数量上限。
        min_df: 至少命中几篇笔记才纳入（过滤极少数噪声）。
    """
    if not frames:
        return []

    pool = _lens_candidate_pool(lens)
    if not pool:
        return []

    note_texts = [_collect_note_text(f).lower() for f in frames]
    doc_count = len(note_texts)

    results: list[KeywordHit] = []
    for keyword, category in pool.items():
        kw_lower = keyword.lower()
        if not kw_lower:
            continue
        tf = sum(text.count(kw_lower) for text in note_texts)
        if tf == 0:
            continue
        df = sum(1 for text in note_texts if kw_lower in text)
        if df < min_df:
            continue
        idf = math.log((doc_count + 1) / (df + 1)) + 1.0
        tf_idf = round(tf * idf, 4)
        results.append(
            KeywordHit(
                keyword=keyword,
                tf=tf,
                df=df,
                tf_idf=tf_idf,
                category=category,
            )
        )

    results.sort(key=lambda r: (-r.tf_idf, -r.df, -r.tf))
    return results[:top_k]


def hits_to_dict_list(hits: list[KeywordHit]) -> list[dict]:
    """序列化为 LensInsightBundle.layer1_signals.hot_keywords 可直接写入的形式。"""
    return [
        {
            "keyword": h.keyword,
            "tf": h.tf,
            "df": h.df,
            "tf_idf": h.tf_idf,
            "category": h.category,
        }
        for h in hits
    ]


__all__ = [
    "KeywordHit",
    "compute_lens_hot_keywords",
    "hits_to_dict_list",
]
