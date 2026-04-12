"""PromptComposer: 从策划全链路（Brief/Strategy/Plan/ImageBrief/Template/Draft）
融合生成结构化富图片 prompt，支持来源追溯与渐进降级。"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.services.image_generator import (
    PromptSource,
    RichImagePrompt,
)

logger = logging.getLogger(__name__)

_MAX_PROMPT_LEN = 300


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        return "，".join(str(v) for v in val if v).strip()
    return str(val).strip()


def _safe_list(val: Any) -> list[str]:
    if not val:
        return []
    if isinstance(val, str):
        return [val.strip()] if val.strip() else []
    if isinstance(val, list):
        return [str(v).strip() for v in val if v]
    return []


def _truncate(text: str, max_len: int = _MAX_PROMPT_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _dedup_segments(segments: list[str]) -> list[str]:
    """去重保序。"""
    seen: set[str] = set()
    result: list[str] = []
    for s in segments:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)
    return result


def compose_image_prompts(
    draft: dict[str, Any] | None = None,
    brief: Any | None = None,
    strategy: Any | None = None,
    note_plan: Any | None = None,
    image_briefs: list[Any] | None = None,
    match_result: dict[str, Any] | None = None,
    ref_image_urls: list[str] | None = None,
    generated_images_history: list[dict[str, Any]] | None = None,
) -> list[RichImagePrompt]:
    """从策划全链路数据融合生成 RichImagePrompt 列表。

    数据优先级（高→低）:
    0.5. user preferences (from history with good rating)
    1. image_briefs (ImageSlotBrief) — 逐槽精细指令
    2. note_plan.image_plan (ImageSlotPlan) — 结构化 visual_brief
    3. strategy (RewriteStrategy) — 全局策略方向
    4. brief (OpportunityBrief) — 方向性指引
    5. draft (quick_draft) — 基础 prompt
    6. match_result — 风格锚点
    """
    draft = draft or {}
    refs = ref_image_urls or []
    slots: dict[str, _SlotAccumulator] = {}

    _collect_from_image_briefs(slots, image_briefs)
    _collect_from_plan(slots, note_plan)
    _collect_from_strategy(slots, strategy)
    _collect_from_brief(slots, brief)
    _collect_from_draft(slots, draft)
    _collect_from_match(slots, match_result)

    if not slots:
        cover_prompt = _safe_str(draft.get("cover_image_prompt", ""))
        if not cover_prompt and brief:
            cover_prompt = _safe_str(getattr(brief, "visual_direction", "")) or _safe_str(getattr(brief, "cover_direction", ""))
        if cover_prompt:
            slots["cover"] = _SlotAccumulator(slot_id="cover")
            slots["cover"].add_positive(cover_prompt, "draft.cover_image_prompt", 5)

    results: list[RichImagePrompt] = []
    for slot_id, acc in sorted(slots.items(), key=lambda x: (0 if x[0] == "cover" else 1, x[0])):
        idx = _slot_index(slot_id)
        ref_url = refs[idx] if idx < len(refs) else (refs[0] if refs else "")
        results.append(acc.build(ref_image_url=ref_url))

    applied = apply_user_preferences(results, generated_images_history)
    return results if not applied else results


class _SlotAccumulator:
    """单个 slot 的 prompt 片段收集器。"""

    def __init__(self, slot_id: str) -> None:
        self.slot_id = slot_id
        self._positives: list[tuple[str, str, int]] = []
        self._negatives: list[tuple[str, str, int]] = []
        self._style_tags: list[str] = []
        self._sources: list[PromptSource] = []
        self._subject: str = ""
        self._must_include: list[str] = []
        self._avoid_items: list[str] = []

    def set_subject(self, text: str) -> None:
        text = text.strip()
        if text and not self._subject:
            self._subject = text

    def add_must_include(self, item: str) -> None:
        item = item.strip()
        if item and item not in self._must_include:
            self._must_include.append(item)

    def add_avoid_item(self, item: str) -> None:
        item = item.strip()
        if item and item not in self._avoid_items:
            self._avoid_items.append(item)

    def add_positive(self, text: str, field: str, priority: int) -> None:
        text = text.strip()
        if text:
            self._positives.append((text, field, priority))
            self._sources.append(PromptSource(field=field, content=text, priority=priority))

    def add_negative(self, text: str, field: str, priority: int) -> None:
        text = text.strip()
        if text:
            self._negatives.append((text, field, priority))
            self._sources.append(PromptSource(field=field, content=f"[negative] {text}", priority=priority))

    def add_style(self, tag: str) -> None:
        tag = tag.strip()
        if tag and tag not in self._style_tags:
            self._style_tags.append(tag)

    def build(self, ref_image_url: str = "") -> RichImagePrompt:
        pos_sorted = sorted(self._positives, key=lambda x: x[2])
        pos_segments = _dedup_segments([t[0] for t in pos_sorted])
        prompt_text = _truncate("，".join(pos_segments))

        neg_sorted = sorted(self._negatives, key=lambda x: x[2])
        neg_segments = _dedup_segments([t[0] for t in neg_sorted])
        negative_prompt = "，".join(neg_segments)

        size = "1024*1365" if self.slot_id == "cover" else "1024*1024"
        return RichImagePrompt(
            slot_id=self.slot_id,
            prompt_text=prompt_text,
            negative_prompt=negative_prompt,
            style_tags=self._style_tags,
            subject=self._subject,
            must_include=self._must_include,
            avoid_items=self._avoid_items,
            ref_image_url=ref_image_url,
            sources=self._sources,
            size=size,
        )


def _slot_index(slot_id: str) -> int:
    if slot_id == "cover":
        return 0
    parts = slot_id.split("_")
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0


# ── 各层数据收集 ──────────────────────────────────────────────


def _collect_from_image_briefs(
    slots: dict[str, _SlotAccumulator],
    image_briefs: list[Any] | None,
) -> None:
    """Priority 1: ImageSlotBrief — 逐槽精细指令。"""
    if not image_briefs:
        return
    for i, sb in enumerate(image_briefs[:5]):
        slot_id = f"content_{i + 1}" if i > 0 else "cover"
        if hasattr(sb, "slot_index"):
            idx = getattr(sb, "slot_index", i)
            slot_id = "cover" if idx == 0 else f"content_{idx}"

        acc = slots.setdefault(slot_id, _SlotAccumulator(slot_id=slot_id))

        subject = _safe_str(getattr(sb, "subject", ""))
        composition = _safe_str(getattr(sb, "composition", ""))
        props = _safe_list(getattr(sb, "props", []))
        color_mood = _safe_str(getattr(sb, "color_mood", ""))
        avoid = _safe_list(getattr(sb, "avoid_items", []))
        text_overlay = _safe_str(getattr(sb, "text_overlay", ""))

        if subject:
            acc.set_subject(subject)
            acc.add_positive(subject, "image_briefs.subject", 1)
        if composition:
            acc.add_positive(composition, "image_briefs.composition", 1)
        if props:
            acc.add_positive("，".join(props), "image_briefs.props", 1)
            for p in props:
                acc.add_must_include(p)
        if color_mood:
            acc.add_style(color_mood)
            acc.add_positive(color_mood, "image_briefs.color_mood", 1)
        if text_overlay:
            acc.add_positive(f"图上文字：{text_overlay}", "image_briefs.text_overlay", 1)
        for a in avoid:
            acc.add_negative(a, "image_briefs.avoid_items", 1)
            acc.add_avoid_item(a)


def _collect_from_plan(
    slots: dict[str, _SlotAccumulator],
    note_plan: Any | None,
) -> None:
    """Priority 2: NewNotePlan.image_plan (MainImagePlan.ImageSlotPlan)。"""
    if not note_plan:
        return
    image_plan = getattr(note_plan, "image_plan", None)
    if not image_plan:
        return

    global_notes = _safe_str(getattr(image_plan, "global_notes", ""))
    priority_axis = _safe_str(getattr(image_plan, "priority_axis", ""))
    plan_slots = getattr(image_plan, "image_slots", []) or []

    for sp in plan_slots[:5]:
        idx = getattr(sp, "slot_index", 0)
        slot_id = "cover" if idx == 0 else f"content_{idx}"
        acc = slots.setdefault(slot_id, _SlotAccumulator(slot_id=slot_id))

        visual_brief = _safe_str(getattr(sp, "visual_brief", ""))
        intent = _safe_str(getattr(sp, "intent", ""))
        must_include = _safe_list(getattr(sp, "must_include_elements", []))
        avoid = _safe_list(getattr(sp, "avoid_elements", []))

        if visual_brief:
            acc.set_subject(visual_brief)
            acc.add_positive(visual_brief, "plan.image_slots.visual_brief", 2)
        if intent:
            acc.add_positive(intent, "plan.image_slots.intent", 2)
        if must_include:
            acc.add_positive("，".join(must_include), "plan.image_slots.must_include", 2)
            for m in must_include:
                acc.add_must_include(m)
        for a in avoid:
            acc.add_negative(a, "plan.image_slots.avoid_elements", 2)
            acc.add_avoid_item(a)

    if global_notes:
        for acc in slots.values():
            acc.add_positive(global_notes, "plan.image_plan.global_notes", 2)
    if priority_axis:
        for acc in slots.values():
            acc.add_style(priority_axis)


def _collect_from_strategy(
    slots: dict[str, _SlotAccumulator],
    strategy: Any | None,
) -> None:
    """Priority 3: RewriteStrategy — 全局策略方向。"""
    if not strategy:
        return

    image_strategy = _safe_list(getattr(strategy, "image_strategy", []))
    positioning = _safe_str(getattr(strategy, "positioning_statement", ""))
    scene = _safe_list(getattr(strategy, "scene_emphasis", []))
    avoid = _safe_list(getattr(strategy, "avoid_elements", []))
    tone = _safe_str(getattr(strategy, "tone_of_voice", ""))

    def _apply_to_all(text: str, field: str, is_neg: bool = False) -> None:
        for acc in slots.values():
            if is_neg:
                acc.add_negative(text, field, 3)
            else:
                acc.add_positive(text, field, 3)

    if not slots:
        slots["cover"] = _SlotAccumulator(slot_id="cover")

    if image_strategy:
        combined = "，".join(image_strategy)
        _apply_to_all(combined, "strategy.image_strategy")
    if positioning:
        _apply_to_all(positioning, "strategy.positioning_statement")
    if scene:
        _apply_to_all("，".join(scene), "strategy.scene_emphasis")
    if tone:
        for acc in slots.values():
            acc.add_style(tone)
    for a in avoid:
        _apply_to_all(a, "strategy.avoid_elements", is_neg=True)


def _collect_from_brief(
    slots: dict[str, _SlotAccumulator],
    brief: Any | None,
) -> None:
    """Priority 4: OpportunityBrief — 方向性指引。"""
    if not brief:
        return

    visual_styles = _safe_list(getattr(brief, "visual_style_direction", []))
    cover_dir = _safe_str(getattr(brief, "cover_direction", ""))
    visual_dir = _safe_str(getattr(brief, "visual_direction", ""))
    avoid_dirs = _safe_list(getattr(brief, "avoid_directions", []))
    constraints = _safe_list(getattr(brief, "constraints", []))
    target_user = _safe_str(getattr(brief, "target_user", ""))
    target_scene = _safe_str(getattr(brief, "target_scene", ""))
    content_goal = _safe_str(getattr(brief, "content_goal", ""))

    if not slots:
        slots["cover"] = _SlotAccumulator(slot_id="cover")

    if target_user or target_scene:
        scene_ctx = "、".join(filter(None, [target_user, target_scene]))
        for acc in slots.values():
            acc.add_positive(f"目标受众/场景：{scene_ctx}", "brief.target_user_scene", 4)
    if content_goal:
        for acc in slots.values():
            acc.add_positive(content_goal, "brief.content_goal", 4)

    for tag in visual_styles:
        for acc in slots.values():
            acc.add_style(tag)

    if cover_dir:
        cover_acc = slots.get("cover")
        if cover_acc:
            cover_acc.add_positive(cover_dir, "brief.cover_direction", 4)

    if visual_dir:
        for acc in slots.values():
            acc.add_positive(visual_dir, "brief.visual_direction", 4)

    for a in avoid_dirs:
        for acc in slots.values():
            acc.add_negative(a, "brief.avoid_directions", 4)
    for c in constraints:
        for acc in slots.values():
            acc.add_negative(c, "brief.constraints", 4)


def _collect_from_draft(
    slots: dict[str, _SlotAccumulator],
    draft: dict[str, Any],
) -> None:
    """Priority 5: quick_draft — 基础 prompt。"""
    cover_prompt = _safe_str(draft.get("cover_image_prompt", ""))
    if not cover_prompt:
        return

    acc = slots.setdefault("cover", _SlotAccumulator(slot_id="cover"))
    acc.add_positive(cover_prompt, "draft.cover_image_prompt", 5)


def _collect_from_match(
    slots: dict[str, _SlotAccumulator],
    match_result: dict[str, Any] | None,
) -> None:
    """Priority 6: TemplateMatchResult — 风格锚点。"""
    if not match_result:
        return

    primary = match_result.get("primary_template") if isinstance(match_result, dict) else None
    if isinstance(primary, dict):
        tname = _safe_str(primary.get("template_name", ""))
        if tname:
            for acc in slots.values():
                acc.add_style(f"模板: {tname}")
    elif hasattr(match_result, "primary_template"):
        pt = getattr(match_result, "primary_template", None)
        tname = _safe_str(getattr(pt, "template_name", "")) if pt else ""
        if tname:
            for acc in slots.values():
                acc.add_style(f"模板: {tname}")


# ── F1: 基于用户编辑历史的自进化 ─────────────────────────────────

def apply_user_preferences(
    slots: list[RichImagePrompt],
    history: list[dict[str, Any]] | None,
) -> bool:
    """从生成历史中提取用户编辑偏好并应用到当前 prompt。

    - 遍历 user_edited=True 且含 rating="good" 的轮次
    - 提取用户添加的风格标签 → 合并到当前 slot
    - 提取用户添加的必含/规避项 → 合并

    Returns True if any preference was applied.
    """
    if not history or not isinstance(history, list) or not slots:
        return False

    good_rounds = [
        r for r in history
        if isinstance(r, dict) and r.get("user_edited") and any(
            res.get("rating") == "good"
            for res in r.get("results", [])
            if isinstance(res, dict)
        )
    ]
    if not good_rounds:
        return False

    slot_map = {s.slot_id: s for s in slots}
    applied = False

    for rnd in good_rounds:
        for pl in rnd.get("prompt_log", []):
            if not isinstance(pl, dict):
                continue
            sid = pl.get("slot_id", "")
            target = slot_map.get(sid)
            if not target:
                continue

            for tag in pl.get("style_tags", []):
                tag = tag.strip()
                if tag and tag not in target.style_tags:
                    target.style_tags.append(tag)
                    applied = True

            for mi in pl.get("must_include", []):
                mi = mi.strip()
                if mi and mi not in target.must_include:
                    target.must_include.append(mi)
                    applied = True

            for ai in pl.get("avoid_items", []):
                ai = ai.strip()
                if ai and ai not in target.avoid_items:
                    target.avoid_items.append(ai)
                    applied = True

    if applied:
        logger.info("apply_user_preferences: applied edits from %d good round(s)", len(good_rounds))

    return applied
