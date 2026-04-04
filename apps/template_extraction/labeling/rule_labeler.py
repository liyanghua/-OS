"""基于规则的小红书笔记四层标注。"""

from __future__ import annotations

from typing import Iterable

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.template_extraction.schemas.labels import LabelResult
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled

from apps.template_extraction.labeling.label_taxonomy import (
    ALL_COVER_TASK_LABELS,
    ALL_SEMANTIC_LABELS,
    get_trigger_keywords,
)

# --- 规则用词（与 YAML / 产品约定对齐的补充）---

_STYLE_WORDS_TITLE = ["法式", "奶油", "中古", "北欧", "原木", "极简", "奶油风", "复古", "ins风", "ins"]
_SCENE_WORDS_TITLE = ["氛围感", "仪式感", "生活方式", "周末", "居家", "餐桌", "餐厅", "场景"]
_PRICE_VALUE_EXTRA = ["改造", "租房", "焕新", "百元", "平价", "性价比", "便宜", "实惠", "学生党"]
_GIFT_EVENT_EXTRA = ["节日", "生日", "圣诞", "情人节", "送礼", "礼盒", "纪念日", "过年"]
_TEXTURE_EXTRA = ["特写", "质感", "材质", "纹理", "刺绣", "蕾丝", "垂坠", "做工"]

_CLOTH_KEYWORDS = [
    "桌布",
    "台布",
    "餐布",
    "布艺",
    "桌旗",
    "tablecloth",
    "亚麻桌",
    "防水桌布",
    "油桌布",
]

_VISUAL_RULES: list[tuple[str, list[str]]] = [
    ("shot_topdown", ["俯拍", "俯视", "俯瞰"]),
    ("shot_angled", ["斜拍", "斜侧", "侧拍", "斜视"]),
    ("shot_closeup", ["特写", "近景", "近拍", "细节图"]),
    ("shot_wide_scene", ["全景", "远景", "一整张桌", "整桌"]),
    ("composition_centered", ["居中", "中心构图", "对称"]),
    ("composition_diagonal", ["对角", "对角线"]),
    ("composition_layered", ["层次", "前后景", "景深"]),
    ("composition_dense", ["满满", "丰富", "一桌"]),
    ("composition_minimal", ["极简", "留白", "干净"]),
    ("has_tablecloth_main", ["桌布", "台布", "餐布"]),
    ("has_tableware", ["餐具", "餐盘", "刀叉", "杯碟", "碗碟", "盘子"]),
    ("has_food", ["美食", "早餐", "下午茶", "面包", "水果", "菜肴", "上桌"]),
    ("has_flower_vase", ["花瓶", "花艺", "插花", "鲜花", "绿植"]),
    ("has_candle", ["蜡烛", "烛光", "烛台"]),
    ("has_hand_only", ["手部", "伸手", "手拿"]),
    ("has_people", ["人像", "出镜", "博主", "小姐姐", "本人"]),
    ("has_chair_or_room_bg", ["椅背", "餐椅", "客厅", "餐厅一角", "背景墙", "房间"]),
    ("has_gift_box", ["礼盒", "礼袋", "礼品盒"]),
    ("has_festival_props", ["圣诞", "雪花", "彩灯", "年味", "新年装饰", "生日帽"]),
    ("cloth_full_spread", ["铺满", "整面", "大面积"]),
    ("cloth_partial_visible", ["一角", "局部", "露出一点"]),
    ("cloth_texture_emphasis", ["织纹", "提花", "麻感", "棉麻纹理"]),
    ("cloth_pattern_emphasis", ["格纹", "条纹", "印花", "碎花", "格子"]),
    ("cloth_edge_emphasis", ["流苏", "蕾丝边", "包边", "花边"]),
    ("cloth_with_other_products", ["组合", "套装", "搭配清单", "一桌搭"]),
    ("text_light", ["小字", "角标"]),
    ("text_medium", ["标题", "副标题", "说明"]),
    ("text_heavy", ["大字", "海报", "贴纸满", "信息多"]),
    ("text_style_label", ["法式", "奶油", "中古", "ins"]),
    ("text_price_label", ["元", "￥", "百元", "平价"]),
    ("text_transformation_claim", ["改造", "焕新", "换了", "前后"]),
    ("text_scene_claim", ["早餐", "下午茶", "聚餐", "晚餐"]),
    ("palette_warm", ["暖色", "暖调", "焦糖", "美拉德"]),
    ("palette_cool", ["冷色", "冷调", "蓝灰"]),
    ("palette_cream", ["奶油色", "奶白", "米白", "杏色"]),
    ("palette_festival_red_green", ["红绿", "圣诞配色", "新年红"]),
    ("lighting_soft", ["柔光", "柔和光线"]),
    ("lighting_natural", ["自然光", "窗光", "日光"]),
    ("lighting_dramatic", ["明暗", "高光比", "戏剧光"]),
]

_SEMANTIC_EXTRA: list[tuple[str, list[str]]] = [
    ("mood_refined_life", ["氛围", "精致", "品位", "高级感", "仪式感"]),
    ("mood_photo_friendly", ["出片", "好拍", "上镜", "拍照"]),
    ("mood_low_cost_upgrade", ["改造", "租房", "低成本", "省钱", "平价改造", "出租屋"]),
    ("mood_festival_setup", ["生日", "圣诞", "新年", "节日布置", "年味", "节庆"]),
    ("mood_anniversary", ["纪念日", "周年", "情侣"]),
    ("mood_friends_gathering", ["聚餐", "聚会", "朋友", "家宴"]),
    ("mood_brunch_afternoontea", ["早餐", "brunch", "下午茶", "咖啡角"]),
    ("mood_daily_healing", ["治愈", "温馨", "日常", "舒服", "温柔"]),
    ("mood_small_space_upgrade", ["小户型", "租房", "小餐厅", "出租屋"]),
    ("mood_style_identity", ["我的家", "本命风格", "就爱这种"]),
    ("mood_giftable", ["送礼", "礼物", "妈妈", "女友"]),
    ("mood_practical_value", ["耐脏", "好洗", "实用", "防油", "防水", "易打理"]),
]

_SELLING_HINTS = [
    "防水",
    "防油",
    "防烫",
    "易打理",
    "免洗",
    "耐用",
    "卖点",
    "性价比",
    "百元",
    "平价",
    "实惠",
    "尺寸",
    "选购",
    "推荐",
]

_AD_LIKE = ["秒杀", "限时", "点击购买", "全网最低", "下单", "私信", "戳链接", "9.9", "特价疯抢"]


def _confidence_from_hits(hit_count: int) -> float:
    if hit_count <= 0:
        return 0.0
    if hit_count == 1:
        return 0.3
    if hit_count == 2:
        return 0.5
    return 0.7


def _match_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    return [kw for kw in keywords if kw and kw in text]


def _merge_results(results: list[LabelResult]) -> list[LabelResult]:
    by_id: dict[str, LabelResult] = {}
    for lr in results:
        prev = by_id.get(lr.label_id)
        if prev is None or lr.confidence > prev.confidence:
            by_id[lr.label_id] = lr
    return list(by_id.values())


def _label_cover_tasks(title: str, body: str, tags_blob: str) -> list[LabelResult]:
    text = f"{title} {body} {tags_blob}"
    out: list[LabelResult] = []

    for label_id in sorted(ALL_COVER_TASK_LABELS):
        kws = get_trigger_keywords(label_id)
        if not kws:
            continue
        matched = _match_keywords(text, kws)
        if not matched:
            continue
        conf = _confidence_from_hits(len(matched))
        ev = "、".join(matched[:8])
        out.append(
            LabelResult(
                label_id=label_id,
                confidence=conf,
                evidence_snippet=ev or matched[0],
                labeler_mode="rule",
            )
        )

    # 标题风格 / 场景
    for kw in _match_keywords(title, _STYLE_WORDS_TITLE):
        out.append(
            LabelResult(
                label_id="style_anchor",
                confidence=_confidence_from_hits(len(_match_keywords(title, _STYLE_WORDS_TITLE))),
                evidence_snippet=kw,
                labeler_mode="rule",
            )
        )
        break
    for kw in _match_keywords(title, _SCENE_WORDS_TITLE):
        out.append(
            LabelResult(
                label_id="scene_seed",
                confidence=_confidence_from_hits(len(_match_keywords(title, _SCENE_WORDS_TITLE))),
                evidence_snippet=kw,
                labeler_mode="rule",
            )
        )
        break

    pv = _match_keywords(text, _PRICE_VALUE_EXTRA)
    if pv:
        out.append(
            LabelResult(
                label_id="price_value",
                confidence=_confidence_from_hits(len(pv)),
                evidence_snippet="、".join(pv[:6]),
                labeler_mode="rule",
            )
        )

    ge = _match_keywords(text, _GIFT_EVENT_EXTRA)
    if ge:
        out.append(
            LabelResult(
                label_id="gift_event",
                confidence=_confidence_from_hits(len(ge)),
                evidence_snippet="、".join(ge[:6]),
                labeler_mode="rule",
            )
        )

    tx = _match_keywords(text, _TEXTURE_EXTRA)
    if tx:
        out.append(
            LabelResult(
                label_id="texture_detail",
                confidence=_confidence_from_hits(len(tx)),
                evidence_snippet="、".join(tx[:6]),
                labeler_mode="rule",
            )
        )

    merged = _merge_results(out)
    if not merged:
        merged.append(
            LabelResult(
                label_id="hook_click",
                confidence=0.3,
                evidence_snippet="默认弱钩子（无明确任务词命中）",
                labeler_mode="rule",
            )
        )
    return merged


def _label_gallery_tasks(parsed_note: XHSParsedNote) -> list[LabelResult]:
    n = len(parsed_note.parsed_images) or int(parsed_note.raw_note.image_count or 0)
    out: list[LabelResult] = []
    if n < 1:
        return out

    out.append(
        LabelResult(
            label_id="cover_hook",
            confidence=0.5 if n < 5 else 0.6,
            evidence_snippet=f"图组共 {n} 张，首图承担点击任务",
            labeler_mode="rule",
        )
    )
    if n >= 5:
        sequence = [
            ("style_expand", "第2张及后续补足风格/空间气质"),
            ("texture_expand", "中段补充纹理与工艺近景"),
            ("usage_expand", "使用场景与上桌延展"),
            ("guide_expand", "尾部尺寸/清单/选购信息"),
        ]
        for lid, desc in sequence:
            out.append(
                LabelResult(
                    label_id=lid,
                    confidence=0.55,
                    evidence_snippet=f"{desc}（≥5 张角色序列启发式）",
                    labeler_mode="rule",
                )
            )
    return out


def _label_visual(title: str, body: str, tags_blob: str) -> list[LabelResult]:
    text = f"{title} {body} {tags_blob}"
    out: list[LabelResult] = []
    for label_id, kws in _VISUAL_RULES:
        matched = _match_keywords(text, kws)
        if not matched:
            continue
        # 桌布为主体：标题命中加权
        conf = 0.55
        if label_id == "has_tablecloth_main" and any(k in title for k in ["桌布", "台布", "餐布"]):
            conf = 0.65
        out.append(
            LabelResult(
                label_id=label_id,
                confidence=conf,
                evidence_snippet="、".join(matched[:6]),
                labeler_mode="rule",
            )
        )
    return _merge_results(out)


def _label_semantic(title: str, body: str, tags_blob: str) -> list[LabelResult]:
    text = f"{title} {body} {tags_blob}"
    out: list[LabelResult] = []

    for label_id in sorted(ALL_SEMANTIC_LABELS):
        kws = get_trigger_keywords(label_id)
        matched = _match_keywords(text, kws)
        if not matched:
            continue
        out.append(
            LabelResult(
                label_id=label_id,
                confidence=_confidence_from_hits(len(matched)),
                evidence_snippet="、".join(matched[:8]),
                labeler_mode="rule",
            )
        )

    for label_id, kws in _SEMANTIC_EXTRA:
        matched = _match_keywords(text, kws)
        if not matched:
            continue
        out.append(
            LabelResult(
                label_id=label_id,
                confidence=_confidence_from_hits(len(matched)),
                evidence_snippet="、".join(matched[:8]),
                labeler_mode="rule",
            )
        )

    return _merge_results(out)


def _label_risk(title: str, body: str, tags_blob: str) -> list[LabelResult]:
    text = f"{title} {body} {tags_blob}"
    out: list[LabelResult] = []

    cloth_hits = _match_keywords(text, _CLOTH_KEYWORDS)
    if not cloth_hits:
        out.append(
            LabelResult(
                label_id="risk_no_product_focus",
                confidence=0.55,
                evidence_snippet="全文未命中桌布/布艺等品类锚点词",
                labeler_mode="rule",
            )
        )

    style_hits = _match_keywords(text, _STYLE_WORDS_TITLE + get_trigger_keywords("style_anchor"))
    sell_hits = _match_keywords(text, _SELLING_HINTS)
    if len(set(style_hits)) >= 2 and not sell_hits:
        out.append(
            LabelResult(
                label_id="risk_overstyled_low_sellability",
                confidence=0.5,
                evidence_snippet=f"风格词多（{ '、'.join(style_hits[:5]) }）但缺少功能/价格/选购卖点词",
                labeler_mode="rule",
            )
        )

    price_hits = _match_keywords(text, ["元", "￥", "¥", "百元", "平价", "特价", "折扣", "秒杀", "限时"])
    if len(price_hits) >= 3 or _match_keywords(text, _AD_LIKE):
        ad_kw = _match_keywords(text, _AD_LIKE)
        ev = "、".join((price_hits + ad_kw)[:8])
        out.append(
            LabelResult(
                label_id="risk_text_too_ad_like",
                confidence=0.55,
                evidence_snippet=ev or "价格/促销语气偏重",
                labeler_mode="rule",
            )
        )

    return _merge_results(out)


def label_note_by_rules(parsed_note: XHSParsedNote) -> XHSNoteLabeled:
    """对单条解析笔记进行规则标注。"""
    title = parsed_note.normalized_title
    body = parsed_note.normalized_body
    tags_blob = " ".join(parsed_note.normalized_tags)

    cover = _label_cover_tasks(title, body, tags_blob)
    gallery = _label_gallery_tasks(parsed_note)
    visual = _label_visual(title, body, tags_blob)
    semantic = _label_semantic(title, body, tags_blob)
    risk = _label_risk(title, body, tags_blob)

    return XHSNoteLabeled(
        note_id=parsed_note.note_id,
        cover_task_labels=cover,
        gallery_task_labels=gallery,
        visual_structure_labels=visual,
        business_semantic_labels=semantic,
        risk_labels=risk,
        labeler_version="v1",
    )
