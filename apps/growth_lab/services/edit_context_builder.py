"""EditContextBuilder — 把 CompilePlan/ResultNode/ObjectNode/session_events 拼装成
一个面向 Agent 的 EditContextPack，供 /edit-context 与 /propose-edit v2 使用。
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from apps.growth_lab.schemas.visual_workspace import (
    CompilePlan,
    CurrentVariantContext,
    EditContextPack,
    EditIntentContext,
    EditStrategyContext,
    EditTemplateContext,
    RecentEditHistory,
    ResultNode,
    RuntimeCopyBlock,
    RuntimeObjectSummary,
    SelectionContext,
    TemplateBinding,
    Variant,
    VisualStateSummary,
)
from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)


# ResultNode.result_type → EditContextPack.node_type 映射（两套 Literal 名字不同）
_RESULT_TO_NODE_TYPE: dict[str, str] = {
    "main_image": "main_image",
    "detail_module": "detail",
    "video_shot": "video_shots",
    "buyer_show": "buyer_show",
    "competitor_ref": "competitor",
}


def _get_store(store: GrowthLabStore | None) -> GrowthLabStore:
    return store or GrowthLabStore()


def _hydrate_plan(plan_d: dict) -> CompilePlan | None:
    try:
        return CompilePlan.model_validate(plan_d)
    except Exception as exc:  # noqa: BLE001
        logger.warning("EditContextBuilder: bad plan dict %s", exc)
        return None


def _hydrate_node(node_d: dict) -> ResultNode | None:
    try:
        return ResultNode.model_validate(node_d)
    except Exception as exc:  # noqa: BLE001
        logger.warning("EditContextBuilder: bad node dict %s", exc)
        return None


def _hydrate_variant(v: dict) -> Variant | None:
    try:
        return Variant.model_validate(v)
    except Exception:  # noqa: BLE001
        return None


def _find_binding(plan: CompilePlan, frame_key: str) -> TemplateBinding | None:
    for b in plan.template_bindings:
        if b.frame_key == frame_key:
            return b
    return plan.template_bindings[0] if plan.template_bindings else None


def _object_summaries(node: ResultNode) -> list[RuntimeObjectSummary]:
    out: list[RuntimeObjectSummary] = []
    for o in node.objects:
        if o.type == "copy":
            continue
        out.append(RuntimeObjectSummary(
            object_id=o.object_id,
            type=str(o.type),
            role=o.role,
            label=o.label or str(o.type),
            locked=bool(o.locked),
            editable_actions=list(o.editable_actions or []),
            semantic_description=o.semantic_description,
            bbox=o.bbox,
        ))
    return out


def _copy_blocks(node: ResultNode) -> list[RuntimeCopyBlock]:
    out: list[RuntimeCopyBlock] = []
    for o in node.objects:
        if o.type != "copy":
            continue
        out.append(RuntimeCopyBlock(
            object_id=o.object_id,
            role=o.role,
            label=o.label or "文案",
            text=(o.prompt_hint or o.label or "").strip(),
            locked=bool(o.locked),
        ))
    return out


def _pick_variant(
    node: ResultNode, variants: list[Variant], variant_id: str | None
) -> Variant | None:
    if not variants:
        return None
    if variant_id:
        for v in variants:
            if v.variant_id == variant_id:
                return v
    if node.active_variant_id:
        for v in variants:
            if v.variant_id == node.active_variant_id:
                return v
    # 最新一张
    return variants[-1]


def _intent_ctx(plan: CompilePlan) -> EditIntentContext:
    it = plan.intent
    return EditIntentContext(
        product_name=it.product_name or None,
        category=(it.output_types[0] if it.output_types else None),
        audience=it.audience or None,
        output_goal=";".join(it.output_types) if it.output_types else None,
        style_refs=list(it.style_refs or []),
        must_have=list(it.must_have or []),
        avoid=list(it.avoid or []),
        raw_prompt=None,
    )


def _template_ctx(
    plan: CompilePlan, node: ResultNode, binding: TemplateBinding | None,
) -> EditTemplateContext:
    template_id = (binding.template_id if binding else "") or ""
    snapshot = binding.adapted_template_snapshot if binding else None
    template_name: str | None = None
    if snapshot and isinstance(snapshot, dict):
        template_name = snapshot.get("name") or snapshot.get("display_name")
    constraints: list[str] = []
    if binding and binding.locked_fields:
        constraints.extend([f"锁定字段：{fld}" for fld in binding.locked_fields[:4]])
    if node.brand_rule_refs:
        constraints.extend([f"品牌规则：{r}" for r in node.brand_rule_refs[:3]])
    return EditTemplateContext(
        template_id=template_id or None,
        template_name=template_name,
        slot_role=node.slot_role,
        slot_objective=node.slot_objective,
        adapted_template_snapshot=snapshot,
        template_constraints=constraints,
    )


def _strategy_ctx(plan: CompilePlan, node: ResultNode) -> EditStrategyContext:
    it = plan.intent
    core = None
    if it.must_have:
        core = it.must_have[0]
    elif node.slot_objective:
        core = node.slot_objective
    return EditStrategyContext(
        core_claim=core,
        supporting_claims=list(it.must_have[1:4]) if it.must_have else [],
        visual_goal=node.slot_objective,
        copy_goal=None,
        platform_goal=None,
        brand_rules=list(node.brand_rule_refs or []),
    )


def _current_variant_ctx(
    node: ResultNode, variants: list[Variant], variant: Variant | None
) -> CurrentVariantContext:
    if not variant:
        return CurrentVariantContext()
    extra = variant.extra or {}
    rev_idx = 0
    try:
        for i, v in enumerate(variants):
            if v.variant_id == variant.variant_id:
                rev_idx = i
                break
    except Exception:  # noqa: BLE001
        rev_idx = 0
    return CurrentVariantContext(
        variant_id=variant.variant_id,
        image_url=variant.asset_url or None,
        revision_index=rev_idx,
        batch_tag=extra.get("batch_tag"),
        batch_size=extra.get("batch_size"),
    )


def _selection_ctx(
    node: ResultNode,
    *,
    primary_object_id: str | None,
    selected_object_ids: Iterable[str] | None,
    selected_region: dict[str, Any] | None,
) -> SelectionContext:
    selected = [s for s in (selected_object_ids or []) if s]
    primary = primary_object_id or (selected[0] if selected else None)
    secondary = [s for s in selected if s != primary]
    locked_ids = [o.object_id for o in node.objects if o.locked]
    editable_ids = [o.object_id for o in node.objects if o.editable and not o.locked]
    # V1: 仅按对象 id 存在推断 mode
    if selected_region:
        mode = "region"
    elif primary and secondary:
        mode = "multi_object"
    elif primary:
        mode = "object"
    else:
        mode = "scene"
    labels: list[str] = []
    for oid in [primary] + secondary:
        if not oid:
            continue
        for o in node.objects:
            if o.object_id == oid:
                labels.append(o.label or str(o.type))
                break
    return SelectionContext(
        mode=mode,  # type: ignore[arg-type]
        selected_object_ids=selected,
        primary_object_id=primary,
        secondary_object_ids=secondary,
        selected_region=selected_region,
        anchor_object_id=None,
        selected_labels=labels,
        locked_object_ids=locked_ids,
        editable_object_ids=editable_ids,
        resolution_confidence=None,
        needs_clarification=False,
    )


def build_recent_history(
    store: GrowthLabStore, plan_id: str, node_id: str, *, limit: int = 5,
) -> RecentEditHistory:
    try:
        events = store.list_workspace_session_events(
            plan_id=plan_id, node_id=node_id, limit=200,
        )
    except Exception:  # noqa: BLE001
        events = []
    last_user: list[str] = []
    last_applied: list[str] = []
    last_proposal: list[str] = []
    for ev in reversed(events):
        t = ev.get("type") or ""
        p = ev.get("payload") or {}
        if t == "user_message" and p.get("text"):
            last_user.append(str(p["text"])[:160])
        if t in {"proposal_applied", "variant_done"} and p.get("summary"):
            last_applied.append(str(p["summary"])[:160])
        if t == "proposal_proposed":
            s = p.get("summary") or ""
            if s:
                last_proposal.append(str(s)[:160])
        if len(last_user) >= limit and len(last_applied) >= limit and len(last_proposal) >= limit:
            break
    return RecentEditHistory(
        last_user_requests=list(reversed(last_user))[-limit:],
        last_applied_changes=list(reversed(last_applied))[-limit:],
        last_proposal_summaries=list(reversed(last_proposal))[-limit:],
    )


def build_edit_context_pack(
    node_id: str,
    *,
    variant_id: str | None = None,
    primary_object_id: str | None = None,
    selected_object_ids: Iterable[str] | None = None,
    selected_region: dict[str, Any] | None = None,
    store: GrowthLabStore | None = None,
) -> EditContextPack | None:
    """读取 node/plan/frame/variants/sessions，组装 EditContextPack。"""

    s = _get_store(store)
    node_d = s.get_workspace_node(node_id)
    if not node_d:
        return None
    node = _hydrate_node(node_d)
    if not node:
        return None
    plan_d = s.get_workspace_plan(node.plan_id) if node.plan_id else None
    plan = _hydrate_plan(plan_d) if plan_d else None
    if not plan:
        plan = CompilePlan(plan_id=node.plan_id or "")
    frame_d = s.get_workspace_frame(node.frame_id) if node.frame_id else None
    frame_key = (frame_d or {}).get("frame_key") or node.result_type or "main_image"
    binding = _find_binding(plan, frame_key) if plan else None

    variants_raw = s.list_workspace_variants(node.node_id)
    variants: list[Variant] = []
    for v in variants_raw:
        vv = _hydrate_variant(v)
        if vv:
            variants.append(vv)

    current_variant = _pick_variant(node, variants, variant_id)
    recent = build_recent_history(s, plan.plan_id or node.plan_id, node.node_id)

    visual_state = VisualStateSummary(
        object_summaries=_object_summaries(node),
        copy_blocks=_copy_blocks(node),
        composition_summary=None,
        salience_summary=None,
        current_direction_summary=node.direction_summary,
    )
    return EditContextPack(
        plan_id=plan.plan_id or node.plan_id,
        frame_id=node.frame_id,
        node_id=node.node_id,
        node_type=_RESULT_TO_NODE_TYPE.get(node.result_type or "main_image", "main_image"),
        node_title=node.slot_role or node.result_type,
        node_objective=node.slot_objective,
        node_status=node.status,
        intent_context=_intent_ctx(plan),
        template_context=_template_ctx(plan, node, binding),
        strategy_context=_strategy_ctx(plan, node),
        current_variant=_current_variant_ctx(node, variants, current_variant),
        selection_context=_selection_ctx(
            node,
            primary_object_id=primary_object_id,
            selected_object_ids=selected_object_ids,
            selected_region=selected_region,
        ),
        visual_state=visual_state,
        recent_history=recent,
    )
