"""卖点主题维度提取器 —— 从标题/正文/标签/评论中提取卖点信号。"""

from __future__ import annotations

import re

from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.intel_hub.schemas.xhs_signals import SellingThemeSignals

SELLING_POINT_KEYWORDS: dict[str, list[str]] = {
    "防水": ["防水", "不怕水", "不渗水"],
    "防油": ["防油", "不沾油", "防烫"],
    "好打理": ["好打理", "易清洁", "一擦就干净", "免洗", "好清洁", "好擦"],
    "出片": ["出片", "上镜", "好拍", "拍照好看"],
    "显高级": ["显高级", "高级感", "质感好", "有质感"],
    "平价": ["平价", "便宜", "性价比", "白菜价", "不贵", "低价"],
    "易铺平": ["易铺平", "贴合", "不起皱", "服帖", "不翘边"],
    "尺寸适配": ["尺寸合适", "尺寸可选", "多尺寸", "定制尺寸"],
    "颜值高": ["颜值高", "好看", "漂亮", "高颜值"],
    "厚实": ["厚实", "加厚", "厚款", "不透"],
}

CHALLENGE_KEYWORDS: dict[str, list[str]] = {
    "卷边": ["卷边", "翘边", "边缘翘", "翘起来"],
    "廉价感": ["廉价感", "塑料感", "质感差", "像塑料", "廉价"],
    "尺寸难选": ["尺寸不合", "大小不对", "尺寸不对", "太大", "太小", "尺寸怎么选"],
    "实物翻车": ["实物不符", "色差", "照骗", "翻车", "和图片不一样"],
    "难清洁": ["难清洁", "不好洗", "洗不干净", "难打理", "擦不掉"],
}

THEME_KEYWORDS: dict[str, list[str]] = {
    "推荐种草": ["推荐", "安利", "种草", "必买", "好物"],
    "测评实测": ["测评", "评测", "实测", "亲测"],
    "改造翻新": ["改造", "翻新", "大变样", "焕新"],
    "避坑指南": ["踩坑", "踩雷", "避坑", "翻车"],
    "对比评测": ["对比", "比较", "PK", "vs"],
    "平替推荐": ["平替", "替代", "代替"],
}

PURCHASE_INTENT_RE = re.compile(
    r"(求链接|想买|哪里买|多少钱|有链接|怎么买|求购|已下单|已入手?|同款|被种草|求同款|想入手|链接)",
    re.IGNORECASE,
)

TRUST_GAP_RE = re.compile(
    r"(真的吗|会不会|实物一样吗|靠谱吗|真实吗|是不是托|有用吗|好用吗|值不值|耐用吗)",
    re.IGNORECASE,
)


def extract_selling_theme_signals(note: XHSParsedNote) -> SellingThemeSignals:
    """从解析后的笔记中提取卖点主题维度信号。"""
    title = note.normalized_title
    body = note.normalized_body
    tags_text = " ".join(note.normalized_tags)
    comment_texts = [c.content for c in note.parsed_comments]

    evidence: list[XHSEvidenceRef] = []
    note_id = note.note_id

    selling_points = _extract_from_text_sources(
        title, body, tags_text, SELLING_POINT_KEYWORDS, note_id, evidence,
    )

    challenges = _extract_from_text_sources(
        title, body, tags_text, CHALLENGE_KEYWORDS, note_id, evidence,
    )
    for ci, ct in enumerate(comment_texts):
        for label, keywords in CHALLENGE_KEYWORDS.items():
            if label in challenges:
                continue
            for kw in keywords:
                if kw.lower() in ct.lower():
                    challenges.append(label)
                    evidence.append(XHSEvidenceRef(
                        source_kind="comment",
                        source_ref=f"{note_id}:comment_{ci}",
                        snippet=_snippet(ct, kw),
                        confidence=0.6,
                    ))
                    break

    themes = _extract_from_text_sources(
        title, body, tags_text, THEME_KEYWORDS, note_id, evidence,
    )

    validated: list[str] = []
    for sp in selling_points:
        for ci, ct in enumerate(comment_texts):
            sp_kws = SELLING_POINT_KEYWORDS.get(sp, [])
            if any(kw.lower() in ct.lower() for kw in sp_kws):
                if sp not in validated:
                    validated.append(sp)
                    evidence.append(XHSEvidenceRef(
                        source_kind="comment",
                        source_ref=f"{note_id}:comment_{ci}",
                        snippet=_snippet(ct, sp_kws[0] if sp_kws else sp),
                        confidence=0.7,
                    ))
                break

    purchase_intent: list[str] = []
    for ci, ct in enumerate(comment_texts):
        m = PURCHASE_INTENT_RE.search(ct)
        if m and m.group(0) not in purchase_intent:
            purchase_intent.append(m.group(0))
            evidence.append(XHSEvidenceRef(
                source_kind="comment",
                source_ref=f"{note_id}:comment_{ci}",
                snippet=_snippet(ct, m.group(0)),
                confidence=0.7,
            ))

    trust_gap: list[str] = []
    for ci, ct in enumerate(comment_texts):
        m = TRUST_GAP_RE.search(ct)
        if m and m.group(0) not in trust_gap:
            trust_gap.append(m.group(0))
            evidence.append(XHSEvidenceRef(
                source_kind="comment",
                source_ref=f"{note_id}:comment_{ci}",
                snippet=_snippet(ct, m.group(0)),
                confidence=0.6,
            ))

    return SellingThemeSignals(
        note_id=note_id,
        selling_point_signals=selling_points,
        validated_selling_points=validated,
        selling_point_challenges=challenges,
        selling_theme_refs=themes,
        purchase_intent_signals=purchase_intent,
        trust_gap_signals=trust_gap,
        evidence_refs=evidence,
    )


def _extract_from_text_sources(
    title: str,
    body: str,
    tags_text: str,
    keyword_dict: dict[str, list[str]],
    note_id: str,
    evidence: list[XHSEvidenceRef],
) -> list[str]:
    results: list[str] = []
    for label, keywords in keyword_dict.items():
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in title.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="title", source_ref=note_id,
                    snippet=_snippet(title, kw), confidence=0.8,
                ))
                break
            if kw_lower in body.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="body", source_ref=note_id,
                    snippet=_snippet(body, kw), confidence=0.7,
                ))
                break
            if kw_lower in tags_text.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="tag", source_ref=note_id,
                    snippet=kw, confidence=0.6,
                ))
                break
    return results


def _snippet(text: str, kw: str, window: int = 30) -> str:
    idx = text.lower().find(kw.lower())
    if idx < 0:
        return kw
    start = max(0, idx - window)
    end = min(len(text), idx + len(kw) + window)
    return text[start:end].strip()
