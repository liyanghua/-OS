"""场景维度提取器 —— 从标题/正文/标签/评论中提取场景信号。"""

from __future__ import annotations

from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.intel_hub.schemas.xhs_signals import SceneSignals

SCENE_KEYWORDS: dict[str, list[str]] = {
    "出租屋": ["出租屋", "租房", "出租房", "合租"],
    "餐桌": ["餐桌", "饭桌", "餐厅桌", "餐桌布"],
    "茶几": ["茶几", "茶台", "茶桌"],
    "书桌": ["书桌", "学习桌", "办公桌", "工作台"],
    "宿舍": ["宿舍", "寝室"],
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
}

AUDIENCE_KEYWORDS: dict[str, list[str]] = {
    "租房党": ["租房党", "租房"],
    "年轻女性": ["女生", "小姐姐", "闺蜜", "女孩"],
    "宝妈": ["宝妈", "妈妈", "带娃", "母婴"],
    "学生": ["学生", "学生党", "宿舍"],
    "宠物主": ["铲屎官", "养猫", "养狗", "宠物主"],
    "家居美学": ["精致", "生活美学", "氛围感", "家居爱好者"],
}


def extract_scene_signals(note: XHSParsedNote) -> SceneSignals:
    """从解析后的笔记中提取场景维度信号。"""
    title = note.normalized_title
    body = note.normalized_body
    tags_text = " ".join(note.normalized_tags)
    comment_texts = [c.content for c in note.parsed_comments]
    note_id = note.note_id

    evidence: list[XHSEvidenceRef] = []

    scenes = _extract_all_sources(title, body, tags_text, comment_texts, SCENE_KEYWORDS, note_id, evidence)
    goals = _extract_all_sources(title, body, tags_text, comment_texts, GOAL_KEYWORDS, note_id, evidence)
    constraints = _extract_all_sources(title, body, tags_text, comment_texts, CONSTRAINT_KEYWORDS, note_id, evidence)
    audience = _extract_all_sources(title, body, tags_text, comment_texts, AUDIENCE_KEYWORDS, note_id, evidence)

    from apps.intel_hub.extraction.visual_extractor import STYLE_KEYWORDS
    styles = _extract_text_only(title, body, tags_text, STYLE_KEYWORDS)

    from apps.intel_hub.extraction.selling_theme_extractor import SELLING_POINT_KEYWORDS
    selling_points = _extract_text_only(title, body, tags_text, SELLING_POINT_KEYWORDS)

    combos: list[str] = []
    for sc in scenes:
        for st in styles:
            combos.append(f"{sc}×{st}")
        for sp in selling_points:
            combos.append(f"{sc}×{sp}")
    for st in styles:
        for sp in selling_points:
            if f"{st}×{sp}" not in combos:
                combos.append(f"{st}×{sp}")

    return SceneSignals(
        note_id=note_id,
        scene_signals=scenes,
        scene_goal_signals=goals,
        scene_constraints=constraints,
        scene_style_value_combos=combos[:20],
        audience_signals=audience,
        evidence_refs=evidence,
    )


def _extract_all_sources(
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
    title: str, body: str, tags_text: str,
    keyword_dict: dict[str, list[str]],
) -> list[str]:
    full = f"{title} {body} {tags_text}".lower()
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
