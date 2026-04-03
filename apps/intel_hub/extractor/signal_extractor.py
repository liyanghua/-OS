"""Layer 2: 经营信号抽取层 — 从 NoteContentFrame 中提炼 BusinessSignalFrame。

使用基于关键词词典的规则抽取，不依赖 LLM。
后续可叠加 LLM 抽取层做精细语义理解。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from apps.intel_hub.schemas.content_frame import BusinessSignalFrame, NoteContentFrame

logger = logging.getLogger(__name__)

# ── 词典定义 ──

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


def extract_business_signals(frame: NoteContentFrame) -> BusinessSignalFrame:
    """从 NoteContentFrame 中基于关键词规则抽取经营信号。"""
    title = frame.title_text
    body = frame.body_text
    tags_text = " ".join(frame.tag_list)
    full_text = f"{title} {body} {tags_text}".lower()

    comment_texts = [c.comment_text for c in frame.comments + frame.top_comments + frame.neg_comments]

    return BusinessSignalFrame(
        note_id=frame.note_id,
        # 标题信号
        title_hook_types=_match_dict(title, HOOK_TYPE_KEYWORDS),
        title_scene_signals=_match_dict(title, SCENE_KEYWORDS),
        title_style_signals=_match_dict(title, STYLE_KEYWORDS),
        title_result_signals=_match_list(title, RESULT_KEYWORDS),
        title_problem_signals=_match_list(title, PROBLEM_KEYWORDS),
        # 正文信号
        body_scene_signals=_match_dict(body, SCENE_KEYWORDS),
        body_audience_signals=_match_dict(body, AUDIENCE_KEYWORDS),
        body_style_signals=_match_dict(body, STYLE_KEYWORDS),
        body_material_signals=_match_dict(body, MATERIAL_KEYWORDS),
        body_selling_points=_match_dict(body, SELLING_POINT_KEYWORDS),
        body_constraints=_extract_constraints(body),
        body_pain_points=_match_dict(body, PAIN_POINT_KEYWORDS),
        body_risk_signals=_match_dict(body, RISK_KEYWORDS),
        body_comparison_signals=_extract_comparisons(body),
        body_size_signals=_extract_size_signals(body),
        body_price_signals=_extract_price_signals(body),
        # 标签信号
        topic_pool_signals=[t for t in frame.tag_list if t],
        distribution_semantics=_match_dict(tags_text, SCENE_KEYWORDS) + _match_dict(tags_text, STYLE_KEYWORDS),
        trend_tags=_match_dict(tags_text, STYLE_KEYWORDS),
        # 评论信号
        purchase_intent_signals=_regex_match_comments(comment_texts, PURCHASE_INTENT_RE),
        positive_feedback_signals=_match_dict_comments(comment_texts, SELLING_POINT_KEYWORDS),
        negative_feedback_signals=_regex_match_comments(comment_texts, NEGATIVE_FEEDBACK_RE),
        question_signals=_regex_match_comments(comment_texts, QUESTION_RE),
        comparison_signals=_regex_match_comments(comment_texts, COMPARISON_RE),
        unmet_need_signals=_regex_match_comments(comment_texts, UNMET_NEED_RE),
        audience_signals_from_comments=_match_dict_comments(comment_texts, AUDIENCE_KEYWORDS),
        trust_gap_signals=_regex_match_comments(comment_texts, TRUST_GAP_RE),
    )


def _match_dict(text: str, keyword_dict: dict[str, list[str]]) -> list[str]:
    text_lower = text.lower()
    return [label for label, keywords in keyword_dict.items()
            if any(kw.lower() in text_lower for kw in keywords)]


def _match_list(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _match_dict_comments(comments: list[str], keyword_dict: dict[str, list[str]]) -> list[str]:
    results: list[str] = []
    for comment in comments:
        matched = _match_dict(comment, keyword_dict)
        results.extend(m for m in matched if m not in results)
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
