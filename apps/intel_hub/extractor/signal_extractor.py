"""Layer 2: 经营信号抽取层 —— 从 NoteContentFrame 中提炼 BusinessSignalFrame。

使用基于关键词词典 + 正则的规则抽取，不依赖 LLM。
V2.1: 支持按 ``CategoryLens`` 动态注入词库；缺省回退到内置桌布向词库，
与 V2.0 行为完全一致。

调用方通常来自 :mod:`apps.intel_hub.workflow.refresh_pipeline` 或
:class:`apps.intel_hub.engine.category_lens_engine.CategoryLensEngine`。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from apps.intel_hub.domain.category_lens import CategoryLens
from apps.intel_hub.extractor.comment_classifier import classify_comment
from apps.intel_hub.schemas.content_frame import (
    BusinessSignalFrame,
    CommentFrame,
    NoteContentFrame,
)

logger = logging.getLogger(__name__)

# ── 默认（桌布向）词典定义 —— 只在没有传 lens 时使用 ──

SCENE_KEYWORDS: dict[str, list[str]] = {
    "出租屋": ["出租屋", "租房", "出租房", "合租"],
    "餐桌": ["餐桌", "饭桌", "餐厅桌"],
    "茶几": ["茶几", "茶台"],
    "书桌": ["书桌", "学习桌", "办公桌", "工作台"],
    "拍照布景": ["拍照", "拍摄", "布景", "背景布"],
    "宝宝家庭": ["宝宝", "宝妈", "母婴", "儿童"],
    "宠物家庭": ["宠物", "猫", "狗", "猫咪"],
    "宿舍": ["宿舍", "寝室"],
}

STYLE_KEYWORDS: dict[str, list[str]] = {
    "奶油风": ["奶油风", "奶油色", "奶白"],
    "ins风": ["ins风", "ins", "博主风"],
    "北欧风": ["北欧", "北欧风", "简约北欧"],
    "法式": ["法式", "法式风", "浪漫法式"],
    "复古风": ["复古", "复古风", "怀旧"],
    "原木风": ["日式", "日系", "原木风", "原木"],
}

MATERIAL_KEYWORDS: dict[str, list[str]] = {
    "PVC": ["pvc", "PVC"],
    "棉麻": ["棉麻", "亚麻", "纯棉", "棉"],
    "皮革": ["皮革", "皮质", "PU皮"],
    "硅胶": ["硅胶"],
}

SELLING_POINT_KEYWORDS: dict[str, list[str]] = {
    "防水": ["防水", "不怕水"],
    "防油": ["防油", "不沾油"],
    "易清洁": ["好打理", "易清洁", "一擦就干净", "免洗", "好清洁"],
    "出片": ["出片", "上镜", "好拍", "拍照好看"],
    "高级感": ["高级感", "质感", "显高级", "有质感"],
    "平价": ["平价", "便宜", "性价比", "白菜价", "不贵"],
    "易铺平": ["易铺平", "贴合", "不起皱", "服帖"],
}

RISK_KEYWORDS: dict[str, list[str]] = {
    "卷边": ["卷边", "翘边", "边缘翘", "翘起来"],
    "廉价感": ["廉价感", "塑料感", "质感差", "像塑料", "廉价"],
    "尺寸不合": ["尺寸不合", "大小不对", "尺寸不对", "太大", "太小"],
    "难清洁": ["难清洁", "不好洗", "洗不干净", "难打理"],
    "色差/实物不符": ["色差", "实物不符", "滤镜", "照骗", "翻车"],
}

PAIN_POINT_KEYWORDS: dict[str, list[str]] = {
    "难清洁": ["难清洁", "不好洗", "洗不干净"],
    "不好铺平": ["不好铺", "起皱", "不服帖"],
    "尺寸选择难": ["尺寸怎么选", "大小不好选"],
}

AUDIENCE_KEYWORDS: dict[str, list[str]] = {
    "租房党": ["租房党", "租房"],
    "女生": ["女生", "小姐姐", "闺蜜"],
    "宝妈": ["宝妈", "妈妈", "带娃"],
    "学生": ["学生", "宿舍", "学生党"],
    "精致生活": ["精致", "生活美学", "氛围感"],
}

HOOK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "recommendation": ["推荐", "安利", "种草", "必买", "好物"],
    "review": ["测评", "评测", "实测", "亲测"],
    "makeover": ["改造", "翻新", "大变样", "焕新"],
    "comparison": ["对比", "比较", "PK", "vs"],
    "pitfall": ["踩坑", "踩雷", "避坑", "翻车", "不要买"],
    "unboxing": ["开箱", "到手", "到货"],
}

RESULT_KEYWORDS: list[str] = [
    "出片", "显高级", "提升幸福感", "后悔没早买", "太好看", "绝绝子",
    "真香", "好看到哭", "爱了", "强推",
]

PROBLEM_KEYWORDS: list[str] = [
    "翻车", "踩雷", "不值", "难打理", "鸡肋", "退货", "差评",
    "不推荐", "后悔", "踩坑",
]

CONTENT_PATTERN_KEYWORDS: dict[str, list[str]] = {
    "推荐": ["推荐", "安利", "种草", "必买", "好物"],
    "测评": ["测评", "评测", "实测", "亲测"],
    "改造": ["改造", "翻新", "大变样"],
    "踩坑": ["踩坑", "踩雷", "避坑"],
    "平替": ["平替", "替代"],
    "对比": ["对比", "比较", "PK"],
    "开箱": ["开箱", "到手", "到货"],
}

PURCHASE_INTENT_RE = re.compile(
    r"(求链接|想买|哪里买|多少钱|有链接|怎么买|求购|已下单|已入|同款|被种草)",
    re.IGNORECASE,
)
NEGATIVE_FEEDBACK_RE = re.compile(
    r"(卷边|翘边|廉价|塑料感|色差|翻车|退货|差评|不好|质量差|不推荐|难清洁|不好洗)",
    re.IGNORECASE,
)
COMPARISON_RE = re.compile(
    r"(和.+比|跟.+比|比.+好|不如.+|哪个好|哪个更|选哪个)",
    re.IGNORECASE,
)
QUESTION_RE = re.compile(
    r"(吗\?|吗？|怎么选|怎么样|好不好|值不值|会不会|能不能|可以.+吗)",
    re.IGNORECASE,
)
UNMET_NEED_RE = re.compile(
    r"(想要.+色|想要.+尺寸|有没有.+款|出.+色|什么时候出|求.+版|希望有)",
    re.IGNORECASE,
)
TRUST_GAP_RE = re.compile(
    r"(实物一样吗|会不会翻车|真的吗|靠谱吗|真实吗|是不是托)",
    re.IGNORECASE,
)


# ── lens 向词库合并 ───────────────────────────────────────


def _resolve_dict_lexicon(
    lens_dict: dict[str, list[str]] | None,
    fallback: dict[str, list[str]],
) -> dict[str, list[str]]:
    """若 lens 提供了分组词库（如 scene_words），则完全采用 lens 词库；
    否则回退到内置桌布向词库（保证既有行为不被破坏）。"""
    if lens_dict:
        return lens_dict
    return fallback


def _resolve_list_lexicon(
    lens_list: list[str] | None,
    fallback: list[str],
) -> list[str]:
    if lens_list:
        return list(lens_list)
    return fallback


# ── 主入口 ────────────────────────────────────────────────


def extract_business_signals(
    frame: NoteContentFrame,
    *,
    lens: CategoryLens | None = None,
) -> BusinessSignalFrame:
    """从 NoteContentFrame 中基于关键词规则抽取经营信号。

    传入 ``lens`` 时优先使用该 lens 的 ``text_lexicons`` 与
    ``user_expression_map``，未命中时回退到内置桌布向词库。
    """
    title = frame.title_text
    body = frame.body_text
    tags_text = " ".join(frame.tag_list)
    full_text = f"{title} {body} {tags_text}"

    comment_frames = list(frame.comments) + list(frame.top_comments) + list(frame.neg_comments)
    comment_texts = [c.comment_text for c in comment_frames if c.comment_text]

    lex = lens.text_lexicons if lens is not None else None
    scene_words = _resolve_dict_lexicon(lex.scene_words if lex else None, SCENE_KEYWORDS)
    style_words = _resolve_dict_lexicon(lex.style_words if lex else None, STYLE_KEYWORDS)
    audience_words = _resolve_dict_lexicon(lex.audience_words if lex else None, AUDIENCE_KEYWORDS)
    material_words = _resolve_dict_lexicon(
        lex.product_feature_words if lex else None, MATERIAL_KEYWORDS
    )
    content_pattern_words = _resolve_dict_lexicon(
        lex.content_pattern_words if lex else None, CONTENT_PATTERN_KEYWORDS
    )
    pain_words = _resolve_list_lexicon(lex.pain_words if lex else None, [])
    emotion_words = _resolve_list_lexicon(lex.emotion_words if lex else None, [])
    trust_barrier_words = _resolve_list_lexicon(
        lex.trust_barrier_words if lex else None, []
    )
    comment_question_words = _resolve_list_lexicon(
        lex.comment_question_words if lex else None, []
    )
    comment_trust_barrier_words = _resolve_list_lexicon(
        lex.comment_trust_barrier_words if lex else None, []
    )

    # 默认 selling_point / risk / pain 三类仍使用内置词库（后续可在 lens
    # 中扩展）：保持桌布类目的精确度，不会被泛化的 lens 词库覆盖。
    selling_point_words = SELLING_POINT_KEYWORDS
    risk_words = RISK_KEYWORDS
    pain_dict = PAIN_POINT_KEYWORDS

    bsf = BusinessSignalFrame(
        note_id=frame.note_id,
        lens_id=lens.lens_id if lens else None,
        # 标题信号
        title_hook_types=_match_dict(title, HOOK_TYPE_KEYWORDS),
        title_scene_signals=_match_dict(title, scene_words),
        title_style_signals=_match_dict(title, style_words),
        title_result_signals=_match_list(title, RESULT_KEYWORDS)
        + [w for w in emotion_words if w.lower() in title.lower()],
        title_problem_signals=_match_list(title, PROBLEM_KEYWORDS)
        + [w for w in pain_words if w.lower() in title.lower()],
        # 正文信号
        body_scene_signals=_match_dict(body, scene_words),
        body_audience_signals=_match_dict(body, audience_words),
        body_style_signals=_match_dict(body, style_words),
        body_material_signals=_match_dict(body, material_words),
        body_selling_points=_match_dict(body, selling_point_words),
        body_constraints=_extract_constraints(body),
        body_pain_points=_match_dict(body, pain_dict)
        + _match_list(body, pain_words),
        body_risk_signals=_match_dict(body, risk_words)
        + _match_list(body, trust_barrier_words),
        body_comparison_signals=_extract_comparisons(body),
        body_size_signals=_extract_size_signals(body),
        body_price_signals=_extract_price_signals(body),
        body_content_pattern_signals=_match_dict(full_text, content_pattern_words),
        body_emotion_signals=_match_list(full_text, emotion_words),
        # 标签信号
        topic_pool_signals=[t for t in frame.tag_list if t],
        distribution_semantics=_match_dict(tags_text, scene_words)
        + _match_dict(tags_text, style_words),
        trend_tags=_match_dict(tags_text, style_words),
        # 评论信号
        purchase_intent_signals=_regex_match_comments(comment_texts, PURCHASE_INTENT_RE),
        positive_feedback_signals=_match_dict_comments(comment_texts, selling_point_words),
        negative_feedback_signals=_regex_match_comments(comment_texts, NEGATIVE_FEEDBACK_RE)
        + _match_list_comments(comment_texts, trust_barrier_words),
        question_signals=_regex_match_comments(comment_texts, QUESTION_RE)
        + _match_list_comments(comment_texts, comment_question_words),
        comparison_signals=_regex_match_comments(comment_texts, COMPARISON_RE),
        unmet_need_signals=_regex_match_comments(comment_texts, UNMET_NEED_RE),
        audience_signals_from_comments=_match_dict_comments(comment_texts, audience_words),
        trust_gap_signals=_regex_match_comments(comment_texts, TRUST_GAP_RE),
        comment_trust_barrier_signals=_match_list_comments(
            comment_texts, comment_trust_barrier_words
        ),
    )

    # 用户话术命中（lens 提供时）：把命中的话术短语记入 body_user_expression_hits
    if lens is not None and lens.user_expression_map:
        bsf.body_user_expression_hits = _match_user_expressions(
            full_text + " " + " ".join(comment_texts), lens
        )

    # 评论分类计数（CommentSignalType 频次表）
    bsf.comment_classification_counts = _classify_comment_counts(comment_frames)

    # 简单去重
    _dedupe_bsf_lists_inplace(bsf)
    return bsf


# ── 内部工具 ──────────────────────────────────────────────


def _classify_comment_counts(comment_frames: list[CommentFrame]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for comment in comment_frames:
        for signal_type in classify_comment(comment):
            key = signal_type.value if hasattr(signal_type, "value") else str(signal_type)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _match_user_expressions(text: str, lens: CategoryLens) -> list[str]:
    hits: list[str] = []
    text_lower = text.lower()
    for mapping in lens.user_expression_map:
        phrase = mapping.user_phrase
        if phrase and phrase.lower() in text_lower and phrase not in hits:
            hits.append(phrase)
    return hits


def _dedupe_bsf_lists_inplace(bsf: BusinessSignalFrame) -> None:
    for field_name, value in bsf.__dict__.items():
        if isinstance(value, list):
            seen: set[Any] = set()
            unique: list[Any] = []
            for item in value:
                key = item if isinstance(item, (str, int, float, bool)) else id(item)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(item)
            bsf.__dict__[field_name] = unique


def _match_dict(text: str, keyword_dict: dict[str, list[str]]) -> list[str]:
    text_lower = text.lower()
    return [
        label
        for label, keywords in keyword_dict.items()
        if any(kw.lower() in text_lower for kw in keywords)
    ]


def _match_list(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _match_dict_comments(
    comments: list[str], keyword_dict: dict[str, list[str]]
) -> list[str]:
    results: list[str] = []
    for comment in comments:
        matched = _match_dict(comment, keyword_dict)
        results.extend(m for m in matched if m not in results)
    return results


def _match_list_comments(comments: list[str], keywords: list[str]) -> list[str]:
    results: list[str] = []
    for comment in comments:
        for kw in keywords:
            if kw.lower() in comment.lower() and kw not in results:
                results.append(kw)
    return results


def _regex_match_comments(comments: list[str], pattern: re.Pattern[str]) -> list[str]:
    results: list[str] = []
    for comment in comments:
        match = pattern.search(comment)
        if match:
            matched_text = match.group(0)
            if matched_text not in results:
                results.append(matched_text)
    return results


def _extract_constraints(text: str) -> list[str]:
    constraint_patterns = [
        r"(一定要.{2,8})",
        r"(注意.{2,8})",
        r"(要选对.{0,6})",
        r"(记得.{2,8})",
        r"(千万别.{2,8})",
    ]
    results: list[str] = []
    for pattern in constraint_patterns:
        for match in re.finditer(pattern, text):
            snippet = match.group(1).strip()
            if snippet and snippet not in results:
                results.append(snippet)
    return results


def _extract_comparisons(text: str) -> list[str]:
    comparison_patterns = [
        r"(比.{1,6}(好|强|便宜|贵|差|软|硬))",
        r"(和.{1,6}(比|相比))",
        r"(不如.{2,8})",
    ]
    results: list[str] = []
    for pattern in comparison_patterns:
        for match in re.finditer(pattern, text):
            snippet = match.group(0).strip()
            if snippet and snippet not in results:
                results.append(snippet)
    return results


def _extract_size_signals(text: str) -> list[str]:
    size_pattern = re.compile(r"(\d{2,4}\s*[xX×*]\s*\d{2,4})")
    matches = size_pattern.findall(text)
    table_shapes = _match_list(text, ["圆桌", "长桌", "方桌", "椭圆"])
    return matches + table_shapes


def _extract_price_signals(text: str) -> list[str]:
    results: list[str] = []
    price_range = re.compile(r"(\d{1,4}[-~到]\d{1,4})(元|块|¥)?")
    for match in price_range.finditer(text):
        results.append(match.group(0))
    price_words = _match_list(text, ["平价", "便宜", "性价比", "贵", "白菜价"])
    results.extend(pw for pw in price_words if pw not in results)
    return results
