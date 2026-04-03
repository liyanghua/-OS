"""场景维度提取器 V2 —— 五层架构：显式场景 + 隐式推断 + 目标/约束 + LLM 补充 + 组合生成。

新增 LLM 层用于发现规则层遗漏的场景和深层用户需求。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.xhs_signals import SceneSignals, VisualSignals

if TYPE_CHECKING:
    from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 关键词词表
# ---------------------------------------------------------------------------

SCENE_KEYWORDS: dict[str, list[str]] = {
    "出租屋": ["出租屋", "租房", "出租房", "合租"],
    "餐桌": ["餐桌", "饭桌", "餐厅桌", "餐桌布"],
    "茶几": ["茶几", "茶台", "茶桌"],
    "书桌": ["书桌", "学习桌", "办公桌", "工作台"],
    "宿舍": ["宿舍", "寝室", "学生宿舍"],
    "宝宝家庭": ["宝宝", "宝妈", "母婴", "儿童", "婴儿"],
    "宠物家庭": ["宠物", "猫", "狗", "猫咪", "铲屎官"],
    "小户型": ["小户型", "小空间", "蜗居", "小面积"],
    "拍照布景": ["拍照", "拍摄", "布景", "背景布"],
}

GOAL_KEYWORDS: dict[str, list[str]] = {
    "改造氛围": ["改造", "翻新", "大变样", "焕新", "氛围改造"],
    "提升高级感": ["提升高级感", "显高级", "有质感", "高级感", "品质感"],
    "防脏防油": ["防脏", "防油", "防水", "不怕脏"],
    "方便清洁": ["好打理", "易清洁", "免洗", "好擦", "方便清洁"],
    "适合拍照": ["出片", "拍照好看", "上镜", "好拍"],
    "平价升级": ["平价", "便宜", "性价比", "白菜价", "省钱"],
}

CONSTRAINT_KEYWORDS: dict[str, list[str]] = {
    "预算敏感": ["平价", "便宜", "省钱", "预算", "学生党", "白菜"],
    "尺寸多样": ["尺寸", "多尺寸", "定制", "大小"],
    "小空间显乱": ["显乱", "拥挤", "太满", "显小"],
    "清洁压力大": ["难清洁", "不好洗", "难打理", "洗不干净"],
    "有孩子/宠物": ["宝宝", "宝妈", "宠物", "猫", "狗", "铲屎官", "带娃"],
    "需要不易卷边": ["卷边", "翘边", "不卷边", "不翘"],
}

AUDIENCE_KEYWORDS: dict[str, list[str]] = {
    "租房党": ["租房党", "租房"],
    "年轻女性": ["女生", "小姐姐", "闺蜜", "女孩"],
    "宝妈": ["宝妈", "妈妈", "带娃", "母婴"],
    "学生": ["学生", "学生党", "宿舍", "大学生"],
    "宠物主": ["铲屎官", "养猫", "养狗", "宠物主"],
    "家居美学": ["精致", "生活美学", "氛围感", "家居爱好者"],
}

# 隐式场景推断规则：关键词 -> 推断场景
INFERENCE_RULES: dict[str, dict[str, list[str]]] = {
    "宿舍": {
        "keywords": ["大学生", "学生党", "寝室", "室友", "上铺", "下铺"],
    },
    "小户型": {
        "keywords": ["小面积", "蜗居", "单间", "开间", "一居室"],
    },
    "宝宝家庭": {
        "keywords": ["宝妈", "母婴", "带娃", "防摔", "儿童安全"],
    },
    "宠物家庭": {
        "keywords": ["铲屎官", "猫抓", "狗咬", "宠物友好"],
    },
    "出租屋": {
        "keywords": ["房东", "搬家", "短租", "毕业", "打工"],
    },
    "餐桌": {
        "keywords": ["吃饭", "火锅", "下厨", "厨房", "烹饪"],
    },
}

# 高潜力组合模板
OPPORTUNITY_TEMPLATES: list[dict[str, str]] = [
    {"pattern": "{scene}×{style}×{selling}", "hint": "可能是高潜力内容方向"},
    {"pattern": "{scene}×{selling}", "hint": "场景-功能组合"},
]


# ---------------------------------------------------------------------------
# 第一层：显式场景
# ---------------------------------------------------------------------------

def extract_explicit_scene_signals(
    title: str,
    body: str,
    tags: list[str],
    comments: list[str],
    note_id: str,
) -> tuple[list[str], list[XHSEvidenceRef]]:
    """从标题/正文/标签/评论直接匹配显式场景关键词。"""
    tags_text = " ".join(tags)
    evidence: list[XHSEvidenceRef] = []
    scenes = _match_all_sources(title, body, tags_text, comments, SCENE_KEYWORDS, note_id, evidence)
    return scenes, evidence


# ---------------------------------------------------------------------------
# 第二层：隐式场景推断
# ---------------------------------------------------------------------------

def infer_scene_signals(
    title: str,
    body: str,
    tags: list[str],
    explicit_scenes: list[str],
    visual_signals: VisualSignals | None = None,
) -> tuple[list[str], float | None]:
    """基于规则推断隐式场景，如 "大学生" -> 宿舍。

    Returns:
        (inferred_scenes, inference_confidence)
    """
    full_text = f"{title} {body} {' '.join(tags)}".lower()
    inferred: list[str] = []

    for scene, rule in INFERENCE_RULES.items():
        if scene in explicit_scenes:
            continue
        if any(kw in full_text for kw in rule["keywords"]):
            inferred.append(scene)

    if visual_signals and visual_signals.visual_scene_signals:
        for vs in visual_signals.visual_scene_signals:
            normalized = vs.replace("场景", "")
            for scene in SCENE_KEYWORDS:
                if normalized in scene and scene not in explicit_scenes and scene not in inferred:
                    inferred.append(scene)

    confidence = None
    if inferred:
        confidence = 0.5 + min(0.3, 0.1 * len(inferred))

    return inferred, confidence


# ---------------------------------------------------------------------------
# 第三层：目标与约束
# ---------------------------------------------------------------------------

def extract_scene_goals_and_constraints(
    title: str,
    body: str,
    tags: list[str],
    comments: list[str],
    note_id: str,
) -> tuple[list[str], list[str], list[str], list[XHSEvidenceRef]]:
    """提取场景目标、约束和受众信号。

    Returns:
        (goals, constraints, audience, evidence_refs)
    """
    tags_text = " ".join(tags)
    evidence: list[XHSEvidenceRef] = []

    goals = _match_all_sources(title, body, tags_text, comments, GOAL_KEYWORDS, note_id, evidence)
    constraints = _match_all_sources(title, body, tags_text, comments, CONSTRAINT_KEYWORDS, note_id, evidence)
    audience = _match_all_sources(title, body, tags_text, comments, AUDIENCE_KEYWORDS, note_id, evidence)

    return goals, constraints, audience, evidence


# ---------------------------------------------------------------------------
# 第四层：LLM 补充层（可选）
# ---------------------------------------------------------------------------

_SCENE_LLM_SYSTEM_PROMPT = """你是一个电商用户场景分析专家，专注于小红书桌布品类。
请分析给定的笔记内容，提取使用场景、用户需求和潜在机会信号。

必须返回严格的 JSON 格式（不要加任何解释文字），字段如下：

{
  "scenes": ["使用场景，如：餐桌、书桌、茶几、出租屋、宿舍、拍照布景、宝宝家庭、宠物家庭、小户型、婚房、新家、办公室"],
  "goals": ["场景目标，如：改造氛围、提升高级感、防脏防油、方便清洁、适合拍照、平价升级、保护桌面、装饰点缀"],
  "constraints": ["用户约束/痛点，如：预算敏感、尺寸难选、清洁压力大、有孩子/宠物、担心翻车、担心色差、选择困难"],
  "audience": ["目标受众，如：租房党、年轻女性、宝妈、学生、宠物主、家居美学、新婚夫妻、独居青年"],
  "opportunity_hints": ["场景机会提示——基于内容分析发现的潜在产品/内容机会，如：学生宿舍防水桌布需求大、拍照布景类桌布可走高颜值溢价、宠物家庭需要耐抓材质"]
}

每个列表字段返回 0-6 个标签。opportunity_hints 需要具体、可操作。只返回 JSON，不要任何其他文字。"""


def extract_scene_with_llm(
    note: "XHSParsedNote",
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[XHSEvidenceRef]]:
    """通过文本 LLM 补充分析场景信号。无 API key 时返回空结果。

    Returns:
        (scenes, goals, constraints, audience, opportunity_hints, evidence_refs)
    """
    from apps.intel_hub.extraction.llm_client import (
        call_text_llm,
        is_llm_available,
        parse_json_response,
    )

    empty = ([], [], [], [], [], [])
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
        f"请分析该桌布笔记的使用场景和用户需求。"
    )

    raw = call_text_llm(_SCENE_LLM_SYSTEM_PROMPT, user_prompt)
    if not raw:
        return empty

    data = parse_json_response(raw)
    if not data:
        logger.debug("scene LLM: JSON 解析失败")
        return empty

    def _ensure_list(v):
        return v if isinstance(v, list) else []

    evidence = [
        XHSEvidenceRef(
            source_kind="llm",
            source_ref=f"{note.note_id}:text_llm",
            snippet="文本 LLM 场景补充分析",
            confidence=0.65,
        )
    ]

    return (
        _ensure_list(data.get("scenes")),
        _ensure_list(data.get("goals")),
        _ensure_list(data.get("constraints")),
        _ensure_list(data.get("audience")),
        _ensure_list(data.get("opportunity_hints")),
        evidence,
    )


# ---------------------------------------------------------------------------
# 第五层：组合生成 + 机会提示
# ---------------------------------------------------------------------------

def build_scene_style_value_combos(
    scenes: list[str],
    styles: list[str],
    selling_points: list[str],
) -> tuple[list[str], list[str]]:
    """生成场景×风格×卖点组合及机会提示。

    Returns:
        (combos, opportunity_hints)
    """
    combos: list[str] = []
    hints: list[str] = []

    for sc in scenes:
        for st in styles:
            for sp in selling_points:
                combo = f"{sc}×{st}×{sp}"
                combos.append(combo)
                hints.append(f"{combo} 可能是高潜力内容方向")
            combo2 = f"{sc}×{st}"
            if combo2 not in combos:
                combos.append(combo2)

        for sp in selling_points:
            combo3 = f"{sc}×{sp}"
            if combo3 not in combos:
                combos.append(combo3)

    for st in styles:
        for sp in selling_points:
            combo4 = f"{st}×{sp}"
            if combo4 not in combos:
                combos.append(combo4)

    return combos[:20], hints[:10]


# ---------------------------------------------------------------------------
# 主入口（保持原签名兼容）
# ---------------------------------------------------------------------------

def extract_scene_signals(
    note: XHSParsedNote,
    visual_signals: VisualSignals | None = None,
) -> SceneSignals:
    """从解析后的笔记中提取场景维度信号（五层架构）。"""
    title = note.normalized_title
    body = note.normalized_body
    tags = note.normalized_tags
    comments = [c.content for c in note.parsed_comments]
    note_id = note.note_id

    # 第一层：显式场景
    explicit_scenes, scene_ev = extract_explicit_scene_signals(
        title, body, tags, comments, note_id,
    )

    # 第二层：隐式推断
    inferred, inference_conf = infer_scene_signals(
        title, body, tags, explicit_scenes, visual_signals,
    )

    # 第三层：目标与约束
    goals, constraints, audience, gc_ev = extract_scene_goals_and_constraints(
        title, body, tags, comments, note_id,
    )

    # 第四层：LLM 补充
    llm_scenes, llm_goals, llm_constraints, llm_audience, llm_hints, llm_ev = (
        extract_scene_with_llm(note)
    )

    # 合并 LLM 场景到隐式推断（不重复已有的显式/隐式场景）
    known_scene_labels = set(SCENE_KEYWORDS.keys())
    for s in llm_scenes:
        if s in known_scene_labels and s not in explicit_scenes and s not in inferred:
            inferred.append(s)
        elif s not in known_scene_labels and s not in explicit_scenes and s not in inferred:
            inferred.append(s)

    if inferred and inference_conf is None:
        inference_conf = 0.6

    goals = _dedupe_ordered(goals + [g for g in llm_goals if g not in goals])
    constraints = _dedupe_ordered(constraints + [c for c in llm_constraints if c not in constraints])
    audience = _dedupe_ordered(audience + [a for a in llm_audience if a not in audience])

    # 第五层：组合生成
    from apps.intel_hub.extraction.visual_extractor import STYLE_KEYWORDS
    from apps.intel_hub.extraction.selling_theme_extractor import SELLING_POINT_KEYWORDS
    styles = _extract_text_only(title, body, tags, STYLE_KEYWORDS)
    selling_points = _extract_text_only(title, body, tags, SELLING_POINT_KEYWORDS)

    all_scenes = explicit_scenes + inferred
    combos, rule_hints = build_scene_style_value_combos(all_scenes, styles, selling_points)

    # LLM 机会提示优先（更具体），规则提示补充
    all_hints = _dedupe_ordered(llm_hints + rule_hints)

    return SceneSignals(
        note_id=note_id,
        scene_signals=explicit_scenes,
        inferred_scene_signals=inferred,
        inference_confidence=inference_conf,
        scene_goal_signals=goals,
        scene_constraints=constraints,
        audience_signals=audience,
        scene_style_value_combos=combos,
        scene_opportunity_hints=all_hints,
        evidence_refs=scene_ev + gc_ev + llm_ev,
    )


def _dedupe_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _match_all_sources(
    title: str,
    body: str,
    tags_text: str,
    comment_texts: list[str],
    keyword_dict: dict[str, list[str]],
    note_id: str,
    evidence: list[XHSEvidenceRef],
) -> list[str]:
    results: list[str] = []
    for label, keywords in keyword_dict.items():
        matched = False
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in title.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="title", source_ref=note_id,
                    snippet=_snippet(title, kw), confidence=0.8,
                ))
                matched = True
                break
            if kw_lower in body.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="body", source_ref=note_id,
                    snippet=_snippet(body, kw), confidence=0.7,
                ))
                matched = True
                break
            if kw_lower in tags_text.lower() and label not in results:
                results.append(label)
                evidence.append(XHSEvidenceRef(
                    source_kind="tag", source_ref=note_id,
                    snippet=kw, confidence=0.6,
                ))
                matched = True
                break
        if not matched:
            for ci, ct in enumerate(comment_texts):
                for kw in keywords:
                    if kw.lower() in ct.lower() and label not in results:
                        results.append(label)
                        evidence.append(XHSEvidenceRef(
                            source_kind="comment",
                            source_ref=f"{note_id}:comment_{ci}",
                            snippet=_snippet(ct, kw),
                            confidence=0.5,
                        ))
                        matched = True
                        break
                if matched:
                    break
    return results


def _extract_text_only(
    title: str, body: str, tags: list[str],
    keyword_dict: dict[str, list[str]],
) -> list[str]:
    full = f"{title} {body} {' '.join(tags)}".lower()
    return [
        label for label, keywords in keyword_dict.items()
        if any(kw.lower() in full for kw in keywords)
    ]


def _snippet(text: str, kw: str, window: int = 30) -> str:
    idx = text.lower().find(kw.lower())
    if idx < 0:
        return kw
    start = max(0, idx - window)
    end = min(len(text), idx + len(kw) + window)
    return text[start:end].strip()
