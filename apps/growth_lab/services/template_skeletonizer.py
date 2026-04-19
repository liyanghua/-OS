"""template_skeletonizer — 把一个 ScriptTemplate 裁成"品类无关"的骨架。

目标：在跨品类复用主图 v2 模板时，保留叙事/构图/角色这些"结构性设定"，
同时丢弃所有"洁面乳专属"的文本细节，让 category_adapter 后续可以按新
品类重新灌入。

保留：
- card_type / message_role / role 的"角色名"（'人群+场景直击图' 这类抽象标题）
- objective（语义级描述，也偏抽象）
- visual_spec.layout_type / shot_type / composition / labels 的"结构"
- copy_spec.text_position / selling_points 作为"角色占位"（保留抽象卖点如"痛点解决"）
- compile_spec.prompt_intent / render_hints
- review_spec / prompt_compile_spec.rules

丢弃：
- business_context（全部）
- strategy_pack（positioning/message_hierarchy 的具体内容）
- global_style.visual_keywords / color_system / avoid_keywords（品类相关）
- 每张卡的 visual_spec.scene / subjects[].description / background.type
- compile_spec.positive_prompt_blocks / negative_prompt_blocks（文本硬编码）
- copy_spec.headline / subheadline（具体文案）
- tags（多数和品类强绑定）
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from apps.growth_lab.schemas.visual_workspace import ScriptTemplate, TemplateSlot

logger = logging.getLogger(__name__)


# 下面这批词倾向于"结构/抽象"，允许保留在 selling_points 里
_ABSTRACT_SELLING_POINT_KEYWORDS = {
    "痛点", "对比", "解决", "认可", "回购", "信任", "适配",
    "实用", "场景", "多场景", "角色", "差异", "温和",
    "日常", "收口", "背书",
}


def _is_abstract_selling_point(text: str) -> bool:
    if not text:
        return False
    # 极短（<=4 字）且含抽象关键词，视作结构化占位
    if len(text) > 10:
        return False
    return any(kw in text for kw in _ABSTRACT_SELLING_POINT_KEYWORDS)


def _structural_composition(comp: dict[str, Any] | None) -> dict[str, Any]:
    comp = comp or {}
    out: dict[str, Any] = {}
    # 仅保留结构性字段
    for k in ("product_ratio", "text_ratio"):
        if k in comp:
            out[k] = comp[k]
    # focal_points：只保留极短的抽象词（≤4 字），避免"温和洁面氛围"这类品类泄漏
    fps = comp.get("focal_points") or []
    out["focal_points"] = [
        fp for fp in fps
        if isinstance(fp, str) and len(fp) <= 4
    ]
    return out


def skeletonize(tpl: ScriptTemplate) -> ScriptTemplate:
    """返回一份 tpl 的深拷贝，其中品类细节被清空、结构字段保留。

    不修改入参。仅支持 `source_kind in {"yaml_v2", "yaml_v2_skeleton"}`；
    其他类型原样返回（调用侧负责判断）。
    """
    if tpl.source_kind not in {"yaml_v2", "yaml_v2_skeleton"}:
        logger.info("skeletonize: 模板 %s 非 v2，原样返回", tpl.template_id)
        return tpl

    cloned = tpl.model_copy(deep=True)

    # ── 顶层细节清空 ──
    cloned.business_context = {}
    # strategy_pack：仅保留结构键，内容清空
    if cloned.strategy_pack:
        cloned.strategy_pack = {
            "positioning": {
                "core_positioning": "",
                "differentiation": [],
                "user_pains": [],
            },
            "message_hierarchy": {
                "primary_message": "",
                "secondary_messages": [],
                "trust_signals": [],
            },
        }
    # global_style：保留 tone 占位，其余清空
    if cloned.global_style:
        cloned.global_style = {
            "tone": "",
            "style_tags": [],
            "visual_keywords": [],
            "avoid_keywords": [],
            "color_system": {
                "primary": "",
                "secondary": "",
                "contrast_level": cloned.global_style.get("color_system", {}).get("contrast_level", ""),
                "emotion": "",
            },
        }
    # prompt_compile_spec.rules 保留；inputs/outputs 保留（是结构 schema）
    # review_spec 整体保留（它是打分维度）

    # default_brand_rules 保留；很抽象
    # description 保留；后续 adapter 会替换

    # ── slot 层清空 ──
    new_slots: list[TemplateSlot] = []
    for slot in cloned.slots:
        slot = slot.model_copy(deep=True)
        # visual_spec 文本清空（场景描述这类硬编码）
        slot.visual_spec = ""
        slot.copy_spec = ""
        # 结构字段清掉文案细节
        slot.positive_prompt_blocks = []
        slot.negative_prompt_blocks = []
        slot.headline = ""
        slot.subheadline = ""
        slot.labels = []
        # selling_points 仅保留抽象项
        slot.selling_points = [
            sp for sp in (slot.selling_points or [])
            if _is_abstract_selling_point(sp)
        ]

        extra = slot.extra or {}
        kept = {}
        # 保留结构性 extra
        if "card_id" in extra:
            kept["card_id"] = extra["card_id"]
        if "card_type" in extra:
            kept["card_type"] = extra["card_type"]
        if "message_role" in extra:
            kept["message_role"] = extra["message_role"]
        if "prompt_intent" in extra:
            kept["prompt_intent"] = extra["prompt_intent"]
        # composition 只保留数值/比例结构
        if "composition" in extra:
            kept["composition"] = _structural_composition(extra["composition"])
        # background 只保留 complexity，type 丢弃
        if "background" in extra:
            bg = extra["background"] or {}
            kept["background"] = {
                "complexity": bg.get("complexity", ""),
            }
        # lighting 保留 style（'soft_natural' 这类偏结构）
        if "lighting" in extra:
            kept["lighting"] = extra["lighting"] or {}
        # objective 保留（偏语义级，adapter 可参考）
        if "objective" in extra:
            kept["objective"] = extra["objective"]
        # tags 丢弃（品类强相关）
        slot.extra = kept

        new_slots.append(slot)
    cloned.slots = new_slots

    # 标记骨架
    cloned.source_kind = "yaml_v2_skeleton"
    cloned.template_id = f"{tpl.template_id}__skeleton"
    cloned.name = f"{tpl.name}（骨架）"

    return cloned
