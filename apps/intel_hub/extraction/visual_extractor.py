"""视觉维度提取器 —— 从标题/正文/标签/评论中提取视觉信号并生成证据。"""

from __future__ import annotations

import re

from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.intel_hub.schemas.xhs_signals import VisualSignals

STYLE_KEYWORDS: dict[str, list[str]] = {
    "奶油风": ["奶油风", "奶油色", "奶白", "奶咖"],
    "ins风": ["ins风", "ins", "博主风", "网红风"],
    "北欧风": ["北欧", "北欧风", "简约北欧"],
    "法式风": ["法式", "法式风", "浪漫法式", "法式复古"],
    "原木风": ["原木", "原木风", "日式", "日系", "木调"],
    "复古风": ["复古", "复古风", "怀旧", "vintage"],
    "极简风": ["极简", "极简风", "极简主义", "minimalist"],
}

COMPOSITION_KEYWORDS: dict[str, list[str]] = {
    "俯拍": ["俯拍", "俯视", "平铺拍", "平铺", "从上往下"],
    "全景": ["全景", "全屋", "整体效果", "大场景"],
    "局部特写": ["特写", "细节图", "局部", "近拍"],
    "前后对比": ["前后对比", "改造前后", "before", "after", "大变样"],
    "氛围图": ["氛围", "氛围感", "氛围图", "mood"],
    "功能说明图": ["说明图", "教程", "步骤", "示意"],
}

COLOR_KEYWORDS: dict[str, list[str]] = {
    "暖白": ["暖白", "米白", "白色系"],
    "木色": ["木色", "原木色", "胡桃色", "木纹"],
    "低饱和": ["低饱和", "莫兰迪", "灰调", "高级灰"],
    "高对比": ["高对比", "撞色", "黑白", "对比色"],
    "绿色系": ["绿色", "墨绿", "牛油果绿", "橄榄绿"],
    "暖色调": ["暖色", "暖调", "棕色", "焦糖色"],
}

TEXTURE_KEYWORDS: dict[str, list[str]] = {
    "柔和": ["柔和", "柔软", "亲肤"],
    "有纹理": ["纹理", "有质感", "肌理"],
    "轻薄": ["轻薄", "薄款", "轻便"],
    "厚重": ["厚重", "加厚", "厚实", "厚款"],
    "高级感": ["高级感", "质感好", "有质感", "不廉价"],
}

EXPRESSION_KEYWORDS: dict[str, list[str]] = {
    "出片": ["出片", "上镜", "好拍", "拍照好看"],
    "氛围感": ["氛围感", "氛围", "仪式感"],
    "治愈系": ["治愈", "治愈系", "温馨"],
    "高级感呈现": ["显高级", "高级感", "质感"],
}

MISLEADING_KEYWORDS: dict[str, list[str]] = {
    "滤镜重": ["滤镜", "p图", "修图", "美颜"],
    "尺寸感不清楚": ["尺寸看不出", "比例失真", "不知道多大"],
    "质感夸大": ["实物不符", "色差", "照骗", "翻车", "和图片不一样"],
}


def extract_visual_signals(note: XHSParsedNote) -> VisualSignals:
    """从解析后的笔记中提取视觉维度信号。"""
    title = note.normalized_title
    body = note.normalized_body
    tags_text = " ".join(note.normalized_tags)
    comment_texts = [c.content for c in note.parsed_comments]

    evidence: list[XHSEvidenceRef] = []

    style = _extract_from_all(title, body, tags_text, comment_texts, STYLE_KEYWORDS, note.note_id, evidence)
    scene = _extract_from_all(title, body, tags_text, comment_texts, COMPOSITION_KEYWORDS, note.note_id, evidence)
    composition = _extract_from_all(title, body, tags_text, comment_texts, COMPOSITION_KEYWORDS, note.note_id, evidence)
    color = _extract_from_all(title, body, tags_text, comment_texts, COLOR_KEYWORDS, note.note_id, evidence)
    texture = _extract_from_all(title, body, tags_text, comment_texts, TEXTURE_KEYWORDS, note.note_id, evidence)
    features = _extract_from_all(title, body, tags_text, comment_texts, EXPRESSION_KEYWORDS, note.note_id, evidence)
    expression = _extract_from_all(title, body, tags_text, comment_texts, EXPRESSION_KEYWORDS, note.note_id, evidence)
    misleading = _extract_from_all(title, body, tags_text, comment_texts, MISLEADING_KEYWORDS, note.note_id, evidence)

    _dedupe_evidence(evidence)

    return VisualSignals(
        note_id=note.note_id,
        visual_style_signals=style,
        visual_scene_signals=scene,
        visual_composition_type=composition,
        visual_color_palette=color,
        visual_texture_signals=texture,
        visual_feature_highlights=features,
        visual_expression_pattern=expression,
        visual_misleading_risk=misleading,
        evidence_refs=evidence,
    )


def _extract_from_all(
    title: str,
    body: str,
    tags_text: str,
    comment_texts: list[str],
    keyword_dict: dict[str, list[str]],
    note_id: str,
    evidence: list[XHSEvidenceRef],
) -> list[str]:
    """从标题/正文/标签/评论中匹配关键词，生成证据引用。"""
    results: list[str] = []

    for label, keywords in keyword_dict.items():
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in title.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="title",
                    source_ref=note_id,
                    snippet=_extract_snippet(title, kw),
                    confidence=0.8,
                ))
                break
            if kw_lower in body.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="body",
                    source_ref=note_id,
                    snippet=_extract_snippet(body, kw),
                    confidence=0.7,
                ))
                break
            if kw_lower in tags_text.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="tag",
                    source_ref=note_id,
                    snippet=kw,
                    confidence=0.6,
                ))
                break
        else:
            for ci, ct in enumerate(comment_texts):
                for kw in keywords:
                    if kw.lower() in ct.lower() and label not in results:
                        results.append(label)
                        evidence.append(XHSEvidenceRef(
                            source_kind="comment",
                            source_ref=f"{note_id}:comment_{ci}",
                            snippet=_extract_snippet(ct, kw),
                            confidence=0.5,
                        ))
                        break
                if label in results:
                    break

    return results


def _extract_snippet(text: str, keyword: str, window: int = 30) -> str:
    idx = text.lower().find(keyword.lower())
    if idx < 0:
        return keyword
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    return text[start:end].strip()


def _dedupe_evidence(evidence: list[XHSEvidenceRef]) -> None:
    seen: set[str] = set()
    i = 0
    while i < len(evidence):
        key = f"{evidence[i].source_kind}:{evidence[i].snippet[:40]}"
        if key in seen:
            evidence.pop(i)
        else:
            seen.add(key)
            i += 1
