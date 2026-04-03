"""视觉维度提取器 V2 —— 三层架构：规则层 + VLM 层 + 合并层。

规则层（metadata）零依赖必定运行，VLM 层可选，合并层统一结果。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.xhs_signals import VisualSignals

if TYPE_CHECKING:
    from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 关键词词表
# ---------------------------------------------------------------------------

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

VISUAL_SCENE_KEYWORDS: dict[str, list[str]] = {
    "餐桌场景": ["餐桌", "饭桌", "吃饭", "餐厅"],
    "书桌场景": ["书桌", "工作台", "学习桌", "办公桌"],
    "茶几场景": ["茶几", "客厅桌"],
    "出租屋场景": ["出租屋", "出租房", "租房"],
    "宿舍场景": ["宿舍", "寝室", "学生宿舍"],
    "拍照布景": ["拍照", "摆拍", "布景", "拍摄背景"],
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
    "材质厚薄感不明确": ["厚薄不清", "不知道多厚", "看不出厚度"],
    "质感夸大": ["实物不符", "色差", "照骗", "翻车", "和图片不一样"],
    "场景过于样板间化": ["样板间", "太假", "不真实"],
}

FEATURE_VIS_KEYWORDS: dict[str, list[str]] = {
    "防水展示": ["防水", "泼水", "水珠", "不渗水"],
    "贴合桌面展示": ["贴合", "平整", "不卷边", "服帖"],
    "出片感展示": ["出片", "上镜", "好看", "拍照"],
    "高级感展示": ["高级感", "显高级", "质感", "有格调"],
    "材质纹理展示": ["纹理", "质感", "肌理", "面料"],
    "尺寸适配展示": ["尺寸", "合适", "刚好", "铺满"],
}

# 视觉差异化评估：若笔记同时具备风格 + 构图 + 特色表达 -> 差异化
DIFF_STYLE_BONUS = {"奶油风", "法式风", "复古风"}
DIFF_COMPOSITION_BONUS = {"前后对比", "局部特写"}

# ---------------------------------------------------------------------------
# VLM prompt
# ---------------------------------------------------------------------------

_VLM_SYSTEM_PROMPT = """你是一个电商视觉分析专家。请分析给定的小红书桌布笔记图片，提取以下维度的视觉信号。

必须返回严格的 JSON 格式（不要加任何解释文字），字段如下：

{
  "visual_style_signals": ["风格标签，如：奶油风、ins风、北欧风、法式、复古风、原木风、日系、极简"],
  "visual_scene_signals": ["场景标签，如：餐桌、书桌、茶几、出租屋、拍照布景、宿舍"],
  "visual_composition_types": ["构图类型，如：俯拍、平拍、局部特写、全景、对比图"],
  "visual_color_palette": ["色彩特征，如：低饱和、暖白、木色、高对比、柔和"],
  "visual_texture_signals": ["材质/质感，如：棉麻质感、PVC光泽、皮革纹理、蕾丝、柔软"],
  "visual_feature_highlights": ["卖点视觉化，如：防水展示、贴合展示、出片效果"],
  "hero_image_pattern": "封面图类型，如：氛围图、功能说明图、对比图、产品特写",
  "visual_misleading_risk": ["风险标签，如：滤镜重、尺寸感不清楚、质感夸大"]
}

每个列表字段返回 0-5 个标签。只返回 JSON，不要任何其他文字。"""


# ---------------------------------------------------------------------------
# 第一层：规则层
# ---------------------------------------------------------------------------

def extract_visual_signals_from_metadata(note: XHSParsedNote) -> VisualSignals:
    """纯关键词/规则层，零外部依赖，必定运行。"""
    title = note.normalized_title
    body = note.normalized_body
    tags_text = " ".join(note.normalized_tags)
    comment_texts = [c.content for c in note.parsed_comments]

    evidence: list[XHSEvidenceRef] = []

    styles = _match_keywords(title, body, tags_text, comment_texts, STYLE_KEYWORDS, note.note_id, evidence)
    scenes = _match_keywords(title, body, tags_text, comment_texts, VISUAL_SCENE_KEYWORDS, note.note_id, evidence)
    compositions = _match_keywords(title, body, tags_text, comment_texts, COMPOSITION_KEYWORDS, note.note_id, evidence)
    colors = _match_keywords(title, body, tags_text, comment_texts, COLOR_KEYWORDS, note.note_id, evidence)
    textures = _match_keywords(title, body, tags_text, comment_texts, TEXTURE_KEYWORDS, note.note_id, evidence)
    expressions = _match_keywords(title, body, tags_text, comment_texts, EXPRESSION_KEYWORDS, note.note_id, evidence)
    misleading = _match_keywords(title, body, tags_text, comment_texts, MISLEADING_KEYWORDS, note.note_id, evidence)
    feature_vis = _match_keywords(title, body, tags_text, comment_texts, FEATURE_VIS_KEYWORDS, note.note_id, evidence)

    primary_style = styles[0] if styles else None
    secondary_styles = styles[1:] if len(styles) > 1 else []
    style_confidence = min(0.9, 0.5 + 0.1 * len(styles)) if styles else None

    all_known_features = set(FEATURE_VIS_KEYWORDS.keys())
    missing_features = sorted(all_known_features - set(feature_vis))

    diff_points: list[str] = []
    if set(styles) & DIFF_STYLE_BONUS:
        diff_points.append(f"风格差异化: {', '.join(set(styles) & DIFF_STYLE_BONUS)}")
    if set(compositions) & DIFF_COMPOSITION_BONUS:
        diff_points.append(f"构图差异化: {', '.join(set(compositions) & DIFF_COMPOSITION_BONUS)}")
    if feature_vis:
        diff_points.append(f"卖点可视化: {', '.join(feature_vis[:3])}")

    click_score = _calc_click_score(styles, compositions, expressions)
    conversion_score = _calc_conversion_score(feature_vis, misleading)
    risk_score = _calc_risk_score(misleading)
    info_density = _calc_info_density(note)

    _dedupe_evidence(evidence)

    return VisualSignals(
        note_id=note.note_id,
        visual_style_signals=styles,
        visual_scene_signals=scenes,
        visual_composition_type=compositions,
        visual_color_palette=colors,
        visual_texture_signals=textures,
        visual_feature_highlights=feature_vis,
        visual_expression_pattern=expressions,
        visual_misleading_risk=misleading,
        primary_style=primary_style,
        secondary_styles=secondary_styles,
        style_confidence=style_confidence,
        hero_image_pattern=None,
        information_density=info_density,
        missing_feature_visualization=missing_features,
        visual_differentiation_points=diff_points,
        click_differentiation_score=click_score,
        conversion_alignment_score=conversion_score,
        visual_risk_score=risk_score,
        evidence_refs=evidence,
    )


# ---------------------------------------------------------------------------
# 第二层：VLM 层（可选）
# ---------------------------------------------------------------------------

def extract_visual_signals_with_vlm(note: XHSParsedNote) -> VisualSignals:
    """通过 VLM 分析笔记图片提取视觉信号。无 API key 时返回空结果。"""
    from apps.intel_hub.extraction.llm_client import call_vlm, is_vlm_available, parse_json_response

    if not is_vlm_available():
        return VisualSignals(note_id=note.note_id)

    image_urls = [img.url for img in note.parsed_images if img.url]
    if not image_urls:
        return VisualSignals(note_id=note.note_id)

    user_prompt = f"笔记标题: {note.normalized_title}\n\n请分析以上图片的视觉信号。"
    raw = call_vlm(image_urls[:3], _VLM_SYSTEM_PROMPT, user_prompt)
    if not raw:
        return VisualSignals(note_id=note.note_id)

    data = parse_json_response(raw)
    if not data:
        return VisualSignals(note_id=note.note_id)

    evidence = [
        XHSEvidenceRef(
            source_kind="image",
            source_ref=f"{note.note_id}:vlm",
            snippet="VLM 图片分析结果",
            confidence=0.75,
        )
    ]

    return VisualSignals(
        note_id=note.note_id,
        visual_style_signals=_ensure_list(data.get("visual_style_signals")),
        visual_scene_signals=_ensure_list(data.get("visual_scene_signals")),
        visual_composition_type=_ensure_list(data.get("visual_composition_types")),
        visual_color_palette=_ensure_list(data.get("visual_color_palette")),
        visual_texture_signals=_ensure_list(data.get("visual_texture_signals")),
        visual_feature_highlights=_ensure_list(data.get("visual_feature_highlights")),
        visual_misleading_risk=_ensure_list(data.get("visual_misleading_risk")),
        hero_image_pattern=data.get("hero_image_pattern"),
        evidence_refs=evidence,
    )


# ---------------------------------------------------------------------------
# 第三层：合并层
# ---------------------------------------------------------------------------

def merge_visual_signals(
    metadata: VisualSignals,
    vlm: VisualSignals,
) -> VisualSignals:
    """合并规则层与 VLM 层结果。VLM 补充但不覆盖规则层已有证据。"""

    def _merge_lists(a: list[str], b: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in a + b:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    merged_styles = _merge_lists(metadata.visual_style_signals, vlm.visual_style_signals)
    primary = merged_styles[0] if merged_styles else metadata.primary_style
    secondary = merged_styles[1:] if len(merged_styles) > 1 else metadata.secondary_styles

    return VisualSignals(
        note_id=metadata.note_id,
        visual_style_signals=merged_styles,
        visual_scene_signals=_merge_lists(metadata.visual_scene_signals, vlm.visual_scene_signals),
        visual_composition_type=_merge_lists(metadata.visual_composition_type, vlm.visual_composition_type),
        visual_color_palette=_merge_lists(metadata.visual_color_palette, vlm.visual_color_palette),
        visual_texture_signals=_merge_lists(metadata.visual_texture_signals, vlm.visual_texture_signals),
        visual_feature_highlights=_merge_lists(metadata.visual_feature_highlights, vlm.visual_feature_highlights),
        visual_expression_pattern=_merge_lists(metadata.visual_expression_pattern, vlm.visual_expression_pattern),
        visual_misleading_risk=_merge_lists(metadata.visual_misleading_risk, vlm.visual_misleading_risk),
        primary_style=primary,
        secondary_styles=secondary,
        style_confidence=metadata.style_confidence,
        hero_image_pattern=vlm.hero_image_pattern or metadata.hero_image_pattern,
        information_density=metadata.information_density,
        missing_feature_visualization=metadata.missing_feature_visualization,
        visual_differentiation_points=metadata.visual_differentiation_points,
        click_differentiation_score=metadata.click_differentiation_score,
        conversion_alignment_score=metadata.conversion_alignment_score,
        visual_risk_score=metadata.visual_risk_score,
        evidence_refs=metadata.evidence_refs + vlm.evidence_refs,
    )


# ---------------------------------------------------------------------------
# 主入口（保持原签名兼容）
# ---------------------------------------------------------------------------

def extract_visual_signals(note: XHSParsedNote) -> VisualSignals:
    """从解析后的笔记中提取视觉维度信号（三层架构）。"""
    metadata_signals = extract_visual_signals_from_metadata(note)
    vlm_signals = extract_visual_signals_with_vlm(note)
    if vlm_signals.is_empty:
        return metadata_signals
    return merge_visual_signals(metadata_signals, vlm_signals)


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _match_keywords(
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


def _ensure_list(val: object) -> list[str]:
    if isinstance(val, list):
        return [str(v) for v in val if v]
    if isinstance(val, str) and val:
        return [val]
    return []


def _calc_click_score(styles: list[str], compositions: list[str], expressions: list[str]) -> float:
    score = 0.0
    if styles:
        score += 0.3
    if set(compositions) & {"前后对比", "氛围图"}:
        score += 0.2
    if set(expressions) & {"出片", "氛围感", "高级感呈现"}:
        score += 0.3
    if len(styles) >= 2:
        score += 0.1
    return min(1.0, round(score, 2))


def _calc_conversion_score(feature_vis: list[str], misleading: list[str]) -> float:
    score = min(1.0, len(feature_vis) * 0.2)
    penalty = len(misleading) * 0.15
    return max(0.0, round(score - penalty, 2))


def _calc_risk_score(misleading: list[str]) -> float:
    if not misleading:
        return 0.0
    return min(1.0, round(len(misleading) * 0.25, 2))


def _calc_info_density(note: XHSParsedNote) -> str:
    image_count = len(note.parsed_images)
    body_len = len(note.normalized_body)
    if image_count >= 6 and body_len > 300:
        return "high"
    if image_count >= 3 or body_len > 150:
        return "medium"
    return "low"
