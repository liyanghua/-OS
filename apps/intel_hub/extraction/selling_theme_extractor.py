"""卖点主题维度提取器 V2 —— 四层架构：文本承诺层 + 评论验证层 + LLM 补充层 + 卖点分类层。

每个卖点被分类为 点击型 / 转化型 / 可产品化 / 纯内容型，
同时输出卖点主题归纳和优先级排序。
LLM 层用于发现规则层遗漏的隐含卖点和笔记内容主题。
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.xhs_signals import SellingThemeSignals

if TYPE_CHECKING:
    from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 关键词词表
# ---------------------------------------------------------------------------

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
    "材质有质感": ["棉麻", "皮革", "蕾丝", "刺绣", "绒面"],
}

CHALLENGE_KEYWORDS: dict[str, list[str]] = {
    "卷边": ["卷边", "翘边", "边缘翘", "翘起来", "会不会卷边"],
    "廉价感": ["廉价感", "塑料感", "质感差", "像塑料", "廉价", "看起来廉价"],
    "尺寸难选": ["尺寸不合", "大小不对", "尺寸不对", "太大", "太小", "尺寸怎么选", "尺寸不好选"],
    "实物翻车": ["实物不符", "色差", "照骗", "翻车", "和图片不一样", "实物翻车吗"],
    "难清洁": ["难清洁", "不好洗", "洗不干净", "难打理", "擦不掉", "好不好清理"],
    "防水存疑": ["真的防水吗", "防水吗", "能防水"],
}

THEME_KEYWORDS: dict[str, list[str]] = {
    "推荐种草": ["推荐", "安利", "种草", "必买", "好物"],
    "测评实测": ["测评", "评测", "实测", "亲测"],
    "改造翻新": ["改造", "翻新", "大变样", "焕新"],
    "避坑指南": ["踩坑", "踩雷", "避坑", "翻车"],
    "对比评测": ["对比", "比较", "PK", "vs"],
    "平替推荐": ["平替", "替代", "代替"],
}

# 卖点主题归纳
SELLING_THEME_MAPPING: dict[str, list[str]] = {
    "清洁便利主题": ["防水", "防油", "好打理", "易铺平"],
    "氛围升级主题": ["出片", "显高级", "颜值高"],
    "平价高级感主题": ["平价", "显高级"],
    "场景改造主题": ["颜值高", "出片"],
    "材质质感主题": ["厚实", "材质有质感"],
}

# 卖点分类
CLICK_ORIENTED = {"出片", "显高级", "颜值高"}
CONVERSION_ORIENTED = {"防水", "防油", "好打理", "易铺平", "厚实", "尺寸适配"}
PRODUCTIZABLE = {"防水", "防油", "尺寸适配", "厚实", "易铺平", "材质有质感"}
CONTENT_ONLY = {"出片", "显高级", "颜值高"}

PURCHASE_INTENT_RE = re.compile(
    r"(求链接|想买|哪里买|多少钱|有链接|怎么买|求购|已下单|已入手?|同款|被种草|求同款|想入手|链接)",
    re.IGNORECASE,
)

TRUST_GAP_RE = re.compile(
    r"(真的吗|会不会|实物一样吗|靠谱吗|真实吗|是不是托|有用吗|好用吗|值不值|耐用吗)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 第一层：文本承诺层
# ---------------------------------------------------------------------------

def extract_claimed_selling_points(
    title: str,
    body: str,
    tags: list[str],
    note_id: str,
) -> tuple[list[str], list[str], list[str], list[XHSEvidenceRef]]:
    """从标题/正文/标签抽显性卖点承诺。

    Returns:
        (primary_selling_points, secondary_selling_points,
         selling_point_priority, evidence_refs)
    """
    tags_text = " ".join(tags)
    evidence: list[XHSEvidenceRef] = []

    title_hits: list[str] = []
    body_early_hits: list[str] = []
    body_late_hits: list[str] = []
    tag_hits: list[str] = []

    body_mid = len(body) // 2 if body else 0

    for label, keywords in SELLING_POINT_KEYWORDS.items():
        matched_source = None
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in title.lower():
                title_hits.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="title", source_ref=note_id,
                    snippet=_snippet(title, kw), confidence=0.85,
                ))
                matched_source = "title"
                break
            idx = body.lower().find(kw_lower)
            if idx >= 0:
                if idx < body_mid:
                    body_early_hits.append(label)
                else:
                    body_late_hits.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="body", source_ref=note_id,
                    snippet=_snippet(body, kw), confidence=0.7,
                ))
                matched_source = "body"
                break
            if kw_lower in tags_text.lower():
                tag_hits.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="tag", source_ref=note_id,
                    snippet=kw, confidence=0.6,
                ))
                matched_source = "tag"
                break
        if not matched_source:
            continue

    priority = _dedupe_ordered(title_hits + body_early_hits + body_late_hits + tag_hits)
    primary = _dedupe_ordered(title_hits + body_early_hits)
    secondary = [p for p in priority if p not in primary]

    return primary, secondary, priority, evidence


# ---------------------------------------------------------------------------
# 第二层：评论验证层
# ---------------------------------------------------------------------------

def extract_comment_validation_signals(
    selling_points: list[str],
    comments: list[str],
    note_id: str,
) -> tuple[list[str], list[str], list[str], list[str], list[XHSEvidenceRef]]:
    """从评论中提取验证/质疑/购买意图/信任差距信号。

    Returns:
        (validated, challenges, purchase_intent, trust_gap, evidence_refs)
    """
    evidence: list[XHSEvidenceRef] = []

    validated: list[str] = []
    for sp in selling_points:
        sp_kws = SELLING_POINT_KEYWORDS.get(sp, [sp])
        for ci, ct in enumerate(comments):
            if any(kw.lower() in ct.lower() for kw in sp_kws):
                if sp not in validated:
                    validated.append(sp)
                    evidence.append(XHSEvidenceRef(
                        source_kind="comment",
                        source_ref=f"{note_id}:comment_{ci}",
                        snippet=_snippet(ct, sp_kws[0]),
                        confidence=0.7,
                    ))
                break

    challenges: list[str] = []
    for label, keywords in CHALLENGE_KEYWORDS.items():
        for ci, ct in enumerate(comments):
            for kw in keywords:
                if kw.lower() in ct.lower() and label not in challenges:
                    challenges.append(label)
                    evidence.append(XHSEvidenceRef(
                        source_kind="comment",
                        source_ref=f"{note_id}:comment_{ci}",
                        snippet=_snippet(ct, kw),
                        confidence=0.6,
                    ))
                    break
            if label in challenges:
                break

    purchase_intent: list[str] = []
    for ci, ct in enumerate(comments):
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
    for ci, ct in enumerate(comments):
        m = TRUST_GAP_RE.search(ct)
        if m and m.group(0) not in trust_gap:
            trust_gap.append(m.group(0))
            evidence.append(XHSEvidenceRef(
                source_kind="comment",
                source_ref=f"{note_id}:comment_{ci}",
                snippet=_snippet(ct, m.group(0)),
                confidence=0.6,
            ))

    return validated, challenges, purchase_intent, trust_gap, evidence


# ---------------------------------------------------------------------------
# 第三层：LLM 补充层（可选）
# ---------------------------------------------------------------------------

_SELLING_LLM_SYSTEM_PROMPT = """你是一个电商内容分析专家，专注于小红书桌布品类。
请分析给定的笔记内容，提取卖点信号。重点关注规则层可能遗漏的隐含卖点。

必须返回严格的 JSON 格式（不要加任何解释文字），字段如下：

{
  "selling_points": ["卖点标签列表，如：防水、防油、好打理、出片、显高级、平价、颜值高、厚实、材质有质感、尺寸适配、易铺平、透气、柔软舒适、环保无味"],
  "content_themes": ["内容主题，如：推荐种草、测评实测、改造翻新、避坑指南、对比评测、平替推荐、氛围升级、场景改造"],
  "implicit_selling_points": ["隐含卖点——笔记没有直说但暗示或暗含的功能/优势，如：多场景适配、季节通用、颜色百搭、不易褪色"],
  "target_pain_points": ["笔记触达的用户痛点，如：桌面显脏、经常翻车、尺寸难选、选不到好看的"]
}

每个列表字段返回 0-8 个标签。只返回 JSON，不要任何其他文字。"""


def extract_selling_points_with_llm(
    note: "XHSParsedNote",
) -> tuple[list[str], list[str], list[str], list[str], list[XHSEvidenceRef]]:
    """通过文本 LLM 补充分析卖点信号。无 API key 时返回空结果。

    Returns:
        (selling_points, content_themes, implicit_selling_points,
         target_pain_points, evidence_refs)
    """
    from apps.intel_hub.extraction.llm_client import (
        call_text_llm,
        is_llm_available,
        parse_json_response,
    )

    empty = ([], [], [], [], [])
    if not is_llm_available():
        return empty

    comments_sample = " | ".join(
        c.content[:80] for c in note.parsed_comments[:10]
    )
    user_prompt = (
        f"笔记标题: {note.normalized_title}\n\n"
        f"笔记正文: {note.normalized_body[:600]}\n\n"
        f"标签: {', '.join(note.normalized_tags)}\n\n"
        f"精选评论: {comments_sample}\n\n"
        f"请提取该桌布笔记的卖点信号。"
    )

    raw = call_text_llm(_SELLING_LLM_SYSTEM_PROMPT, user_prompt)
    if not raw:
        return empty

    data = parse_json_response(raw)
    if not data:
        logger.debug("selling LLM: JSON 解析失败")
        return empty

    def _ensure_list(v):
        return v if isinstance(v, list) else []

    evidence = [
        XHSEvidenceRef(
            source_kind="llm",
            source_ref=f"{note.note_id}:text_llm",
            snippet="文本 LLM 卖点补充分析",
            confidence=0.65,
        )
    ]

    return (
        _ensure_list(data.get("selling_points")),
        _ensure_list(data.get("content_themes")),
        _ensure_list(data.get("implicit_selling_points")),
        _ensure_list(data.get("target_pain_points")),
        evidence,
    )


# ---------------------------------------------------------------------------
# 第四层：卖点分类层
# ---------------------------------------------------------------------------

def classify_selling_theme(
    all_selling_points: list[str],
    validated: list[str],
    challenges: list[str],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """区分卖点类型并归纳主题。

    Returns:
        (click_oriented, conversion_oriented, productizable,
         content_only, selling_theme_refs)
    """
    click = [sp for sp in all_selling_points if sp in CLICK_ORIENTED]
    conversion = [sp for sp in all_selling_points if sp in CONVERSION_ORIENTED]
    productizable = [sp for sp in all_selling_points if sp in PRODUCTIZABLE]
    content_only = [sp for sp in all_selling_points if sp in CONTENT_ONLY]

    themes: list[str] = []
    for theme, required_points in SELLING_THEME_MAPPING.items():
        if any(sp in all_selling_points for sp in required_points):
            themes.append(theme)

    return click, conversion, productizable, content_only, themes


# ---------------------------------------------------------------------------
# 主入口（保持原签名兼容）
# ---------------------------------------------------------------------------

def extract_selling_theme_signals(note: XHSParsedNote) -> SellingThemeSignals:
    """从解析后的笔记中提取卖点主题维度信号（四层架构）。"""
    title = note.normalized_title
    body = note.normalized_body
    tags = note.normalized_tags
    comment_texts = [c.content for c in note.parsed_comments]
    note_id = note.note_id

    # 第一层：规则层
    primary, secondary, priority, claimed_ev = extract_claimed_selling_points(
        title, body, tags, note_id,
    )

    all_sp = priority

    theme_evidence: list[XHSEvidenceRef] = []
    theme_refs = _extract_themes(title, body, tags, note_id, theme_evidence)

    # 第二层：评论验证层
    validated, challenges, purchase_intent, trust_gap, comment_ev = (
        extract_comment_validation_signals(all_sp, comment_texts, note_id)
    )

    # 第三层：LLM 补充层
    llm_sp, llm_themes, llm_implicit, llm_pains, llm_ev = (
        extract_selling_points_with_llm(note)
    )

    # 合并 LLM 发现的新卖点到规则层结果
    known_sp_labels = set(SELLING_POINT_KEYWORDS.keys())
    for sp in llm_sp:
        if sp in known_sp_labels and sp not in all_sp:
            secondary.append(sp)
            all_sp.append(sp)

    # LLM 发现的隐含卖点归入 secondary（用 "[隐]" 标记来源）
    for sp in llm_implicit:
        if sp not in all_sp:
            secondary.append(sp)
            all_sp.append(sp)

    combined_themes = _dedupe_ordered(theme_refs + llm_themes)

    # 重新跑评论验证（包含 LLM 补充的卖点）
    if llm_sp:
        new_validated, new_challenges, new_pi, new_tg, extra_ev = (
            extract_comment_validation_signals(
                [sp for sp in llm_sp if sp not in priority],
                comment_texts,
                note_id,
            )
        )
        validated = _dedupe_ordered(validated + new_validated)
        challenges = _dedupe_ordered(challenges + new_challenges)
        purchase_intent = _dedupe_ordered(purchase_intent + new_pi)
        trust_gap = _dedupe_ordered(trust_gap + new_tg)
        comment_ev = comment_ev + extra_ev

    # 第四层：卖点分类
    click, conversion, productizable, content_only, selling_themes = (
        classify_selling_theme(all_sp, validated, challenges)
    )

    combined_themes = _dedupe_ordered(combined_themes + selling_themes)

    all_evidence = claimed_ev + comment_ev + theme_evidence + llm_ev

    return SellingThemeSignals(
        note_id=note_id,
        selling_point_signals=all_sp,
        validated_selling_points=validated,
        selling_point_challenges=challenges,
        selling_theme_refs=combined_themes,
        purchase_intent_signals=purchase_intent,
        trust_gap_signals=trust_gap,
        primary_selling_points=primary,
        secondary_selling_points=secondary,
        selling_point_priority=_dedupe_ordered(priority + [sp for sp in all_sp if sp not in priority]),
        click_oriented_points=click,
        conversion_oriented_points=conversion,
        productizable_points=productizable,
        content_only_points=content_only,
        evidence_refs=all_evidence,
    )


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _extract_themes(
    title: str,
    body: str,
    tags: list[str],
    note_id: str,
    evidence: list[XHSEvidenceRef],
) -> list[str]:
    tags_text = " ".join(tags)
    results: list[str] = []
    for label, keywords in THEME_KEYWORDS.items():
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


def _dedupe_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
