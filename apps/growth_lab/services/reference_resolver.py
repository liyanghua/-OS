"""ReferenceResolver — 根据用户自然语言里的"这里/右边/主体/背景/文案/logo"等
指代，结合 SelectionContext 与节点对象列表，推出 ResolvedEditReference。

V1：
- 优先用 selection_context.primary_object_id / selected_object_ids
- 其次用 selected_region + 对象粗略方位（按对象在 objects 列表中的顺序拟合左右/上下）
- 再次用文字关键词 → object.type/role 映射
- 解析后置信度 < 0.5 返回 needs_clarification 让前端弹澄清卡
"""

from __future__ import annotations

import re
from typing import Iterable

from apps.growth_lab.schemas.visual_workspace import (
    EditContextPack,
    ResolvedEditReference,
    RuntimeObjectSummary,
)

# 关键词 → 对象 type/role 集合（V1 粗匹配）
_KEYWORD_TO_TAGS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"(主体|主图|产品|商品|瓶|罐|包装)", re.I), ["product", "hero_product"]),
    (re.compile(r"(背景|场景|氛围|底图)", re.I), ["background", "lifestyle_bg", "clean_bg"]),
    (re.compile(r"(标题|大字|主文案|主标|headline)", re.I), ["copy", "title_copy"]),
    (re.compile(r"(副标|小字|副文案|subtitle|描述)", re.I), ["copy", "subtitle_copy"]),
    (re.compile(r"(文案|文字|字体|排版|copy)", re.I), ["copy", "title_copy", "subtitle_copy"]),
    (re.compile(r"(人物|模特|用户|使用者)", re.I), ["person", "lifestyle_person"]),
    (re.compile(r"(装饰|标注|箭头|徽章|badge)", re.I), ["decoration", "trust_badge"]),
    (re.compile(r"(logo|商标|品牌标)", re.I), ["logo", "brand_logo"]),
    (re.compile(r"(before|前态|使用前|痛点)", re.I), ["decoration", "before_area"]),
    (re.compile(r"(after|后态|使用后|效果)", re.I), ["decoration", "after_area"]),
]

_DIRECTION_KEYWORDS: dict[str, re.Pattern[str]] = {
    "left": re.compile(r"(左边|左侧|left)", re.I),
    "right": re.compile(r"(右边|右侧|right)", re.I),
    "top": re.compile(r"(上方|顶部|top)", re.I),
    "bottom": re.compile(r"(下方|底部|bottom)", re.I),
    "center": re.compile(r"(中间|中心|正中|center)", re.I),
}

_VAGUE_KEYWORDS = re.compile(r"(这里|那里|那个|这个|这边|那边|它|它们)", re.I)


def _has_direction(user_message: str) -> str | None:
    for name, pat in _DIRECTION_KEYWORDS.items():
        if pat.search(user_message):
            return name
    return None


def _split_objects_by_direction(
    summaries: Iterable[RuntimeObjectSummary],
) -> dict[str, list[RuntimeObjectSummary]]:
    """没有真 bbox 时，用 role 关键字近似方位。"""
    out: dict[str, list[RuntimeObjectSummary]] = {
        "left": [],
        "right": [],
        "top": [],
        "bottom": [],
        "center": [],
    }
    for s in summaries:
        role = (s.role or "").lower()
        label = (s.label or "").lower()
        if "before" in role or "before" in label or "左" in s.label:
            out["left"].append(s)
        elif "after" in role or "after" in label or "右" in s.label:
            out["right"].append(s)
        elif "title" in role or "headline" in role:
            out["top"].append(s)
        elif "subtitle" in role:
            out["bottom"].append(s)
        else:
            out["center"].append(s)
    return out


def _match_tags(user_message: str, summaries: list[RuntimeObjectSummary]) -> list[str]:
    want_tags: set[str] = set()
    for pat, tags in _KEYWORD_TO_TAGS:
        if pat.search(user_message):
            want_tags.update(tags)
    if not want_tags:
        return []
    hits: list[str] = []
    for s in summaries:
        if s.role and s.role in want_tags:
            hits.append(s.object_id)
        elif s.type in want_tags and s.object_id not in hits:
            hits.append(s.object_id)
    return hits


def resolve_edit_reference(
    pack: EditContextPack, user_message: str,
) -> ResolvedEditReference:
    msg = (user_message or "").strip()
    sel = pack.selection_context
    summaries = pack.visual_state.object_summaries
    # 把 copy blocks 也当可寻址对象（简化）
    copy_as_summaries = [
        RuntimeObjectSummary(
            object_id=c.object_id, type="copy", role=c.role,
            label=c.label, locked=c.locked,
        )
        for c in pack.visual_state.copy_blocks
    ]
    all_summaries = list(summaries) + copy_as_summaries

    # 1. 用户已选对象优先
    if sel.primary_object_id:
        primary = [sel.primary_object_id]
        secondary = list(sel.secondary_object_ids or [])
        return ResolvedEditReference(
            scope="multi_object" if secondary else "object",
            primary_targets=primary,
            secondary_targets=secondary,
            ambiguous_refs=[],
            resolution_confidence=0.95,
            needs_clarification=False,
        )

    # 2. region 解析
    if sel.selected_region:
        region = sel.selected_region or {}
        # 优先：anchor
        primary: list[str] = []
        if sel.anchor_object_id:
            primary.append(sel.anchor_object_id)
        # 再：文本 tag 命中
        tag_hits = _match_tags(msg, all_summaries)
        for h in tag_hits:
            if h not in primary:
                primary.append(h)
        # 再：从 region 中心推断方位
        if not primary:
            try:
                cx = float(region.get("x", 0.0)) + float(region.get("w", 0.0)) / 2.0
                cy = float(region.get("y", 0.0)) + float(region.get("h", 0.0)) / 2.0
            except Exception:
                cx, cy = 0.5, 0.5
            region_dir = "center"
            if cx < 0.4:
                region_dir = "left"
            elif cx > 0.6:
                region_dir = "right"
            elif cy < 0.4:
                region_dir = "top"
            elif cy > 0.6:
                region_dir = "bottom"
            # 文本方位词更精确
            msg_dir = _has_direction(msg)
            direction = msg_dir or region_dir
            by_dir = _split_objects_by_direction(all_summaries)
            pool = by_dir.get(direction) or []
            primary = [p.object_id for p in pool[:1]]
        return ResolvedEditReference(
            scope="region",
            primary_targets=primary,
            secondary_targets=[],
            ambiguous_refs=[msg] if not primary else [],
            resolution_confidence=0.7 if primary else 0.4,
            needs_clarification=not primary,
            clarification_question=(
                "圈选区域里没有能直接识别的对象，你想改的是这里的哪个元素？"
                if not primary else None
            ),
        )

    # 3. 文本关键词直接命中
    tag_hits = _match_tags(msg, all_summaries)
    if tag_hits:
        primary = [tag_hits[0]]
        secondary = tag_hits[1:3]
        return ResolvedEditReference(
            scope="multi_object" if secondary else "object",
            primary_targets=primary,
            secondary_targets=secondary,
            ambiguous_refs=[],
            resolution_confidence=0.75,
            needs_clarification=False,
        )

    # 4. 方位关键词 + scene
    direction = _has_direction(msg)
    if direction:
        by_dir = _split_objects_by_direction(all_summaries)
        pool = by_dir.get(direction) or []
        if pool:
            return ResolvedEditReference(
                scope="object",
                primary_targets=[pool[0].object_id],
                secondary_targets=[p.object_id for p in pool[1:2]],
                ambiguous_refs=[],
                resolution_confidence=0.6,
                needs_clarification=False,
            )
        return ResolvedEditReference(
            scope="region",
            primary_targets=[],
            secondary_targets=[],
            ambiguous_refs=[direction],
            resolution_confidence=0.3,
            needs_clarification=True,
            clarification_question=f"你说的「{direction}」具体对应哪个对象？可以先在画布上点击它。",
        )

    # 5. 模糊指代（这里/那个）
    if _VAGUE_KEYWORDS.search(msg):
        return ResolvedEditReference(
            scope="scene",
            primary_targets=[],
            secondary_targets=[],
            ambiguous_refs=[msg[:60]],
            resolution_confidence=0.25,
            needs_clarification=True,
            clarification_question="你想改的是画面里的哪个对象？请在画布上点击它，或在右栏点一张变体作为底图。",
        )

    # 6. 兜底：按整图（scene）
    return ResolvedEditReference(
        scope="scene",
        primary_targets=[],
        secondary_targets=[],
        ambiguous_refs=[],
        resolution_confidence=0.55,
        needs_clarification=False,
    )
