"""VisualPlanCompiler — 把 IntentContext + ScriptTemplate 编译成可落地的 CompilePlan。

不直接调用图像生成；
只负责"展开 Frame 与节点骨架 + 给每个节点准备好 visual/copy spec"，
后续的图像生成由 `visual_frame_generator.py` 接手，
图文编排/发布由各子 compiler 处理。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from apps.growth_lab.schemas.visual_workspace import (
    CompilePlan,
    Frame,
    IntentContext,
    ResultNode,
    ScriptTemplate,
    TemplateBinding,
)
from apps.growth_lab.services.category_adapter import adapt_skeleton
from apps.growth_lab.services.template_library import get_template_library
from apps.growth_lab.services.template_skeletonizer import skeletonize

logger = logging.getLogger(__name__)


# frame_key -> (默认 category, layout, 节点卡尺寸 [宽,高], 节点画布行布局间距)
_FRAME_KEY_CONFIG: dict[str, dict[str, Any]] = {
    "main_image": {
        "category": "main_image",
        "layout": "row",
        "node_size": (220.0, 220.0),
        "gap": 24.0,
        "title": "主图 Frame",
    },
    "detail": {
        "category": "detail_module",
        "layout": "column",
        "node_size": (260.0, 340.0),
        "gap": 24.0,
        "title": "详情 Frame",
    },
    "video_shots": {
        "category": "video_shot_list",
        "layout": "grid",
        "node_size": (200.0, 356.0),
        "gap": 20.0,
        "title": "视频分镜 Frame",
    },
    "buyer_show": {
        "category": "buyer_show",
        "layout": "grid",
        "node_size": (210.0, 280.0),
        "gap": 20.0,
        "title": "买家秀 Frame",
    },
    "competitor": {
        "category": "competitor_deconstruct",
        "layout": "column",
        "node_size": (320.0, 220.0),
        "gap": 20.0,
        "title": "竞品对标 Frame",
    },
}


_FRAME_KEY_TO_RESULT_TYPE = {
    "main_image": "main_image",
    "detail": "detail_module",
    "video_shots": "video_shot",
    "buyer_show": "buyer_show",
    "competitor": "competitor_ref",
}


class VisualPlanCompiler:
    """意图 + 模板 → 一个完整的 CompilePlan（含 Frame/Node 骨架）。"""

    def __init__(self) -> None:
        self._lib = get_template_library()

    def compile(
        self,
        intent: IntentContext,
        *,
        frame_keys: list[str] | None = None,
        template_overrides: dict[str, str] | None = None,
        borrow_frame_only: dict[str, bool] | None = None,
    ) -> tuple[CompilePlan, list[Frame], list[ResultNode]]:
        """返回 (plan, frames, nodes)。

        frame_keys: 要生成的 Frame 序列，默认由 intent.output_types 推导。
        template_overrides: {frame_key: template_id} 强制指定模板。
        borrow_frame_only: {frame_key: True} 强制走"仅借框架 + 按 intent 重参数化"路径。
        """
        frame_keys = frame_keys or self._resolve_frame_keys(intent)
        template_overrides = template_overrides or {}
        borrow_frame_only = borrow_frame_only or {}

        plan = CompilePlan(intent=intent, status="compiling")
        frames: list[Frame] = []
        nodes: list[ResultNode] = []
        bindings: list[TemplateBinding] = []

        canvas_x_cursor = 60.0
        canvas_y_cursor = 60.0

        for frame_key in frame_keys:
            cfg = _FRAME_KEY_CONFIG.get(frame_key)
            if cfg is None:
                logger.warning("未知的 frame_key: %s，跳过", frame_key)
                continue

            template_id = template_overrides.get(frame_key, "")
            orig_template = self._select_template(cfg["category"], template_id)
            if orig_template is None:
                logger.warning("frame_key=%s 无可用模板，跳过", frame_key)
                continue

            template, binding_reason, adapted_snapshot = self._apply_frame_borrow(
                orig_template=orig_template,
                intent=intent,
                borrow_forced=bool(borrow_frame_only.get(frame_key)),
            )

            frame, frame_nodes = self._build_frame(
                plan_id=plan.plan_id,
                frame_key=frame_key,
                template=template,
                cfg=cfg,
                origin_x=canvas_x_cursor,
                origin_y=canvas_y_cursor,
                intent=intent,
            )
            frames.append(frame)
            nodes.extend(frame_nodes)
            bindings.append(TemplateBinding(
                frame_key=frame_key,
                template_id=template.template_id,
                binding_reason=binding_reason,
                adapted_template_snapshot=adapted_snapshot,
            ))

            # 下一 Frame 放到当前 Frame 下方
            frame_height = self._estimate_frame_height(frame, len(frame_nodes), cfg)
            canvas_y_cursor += frame_height + 80.0

        plan.template_bindings = bindings
        plan.frame_ids = [f.frame_id for f in frames]
        plan.workspace_id = intent.source_spec_id[:12] if intent.source_spec_id else ""
        plan.status = "compiled"
        plan.updated_at = datetime.now(UTC)
        logger.info(
            "编译完成 plan_id=%s frames=%d nodes=%d",
            plan.plan_id, len(frames), len(nodes),
        )
        return plan, frames, nodes

    # ── 内部 ──

    def _resolve_frame_keys(self, intent: IntentContext) -> list[str]:
        out = intent.output_types or ["main_image"]
        # 允许 output_types 直接是 frame_key 也可以是 result_type
        keys: list[str] = []
        for o in out:
            if o in _FRAME_KEY_CONFIG:
                keys.append(o)
            elif o in {"main_image"}:
                keys.append("main_image")
            elif o in {"detail", "detail_module", "detail_page"}:
                keys.append("detail")
            elif o in {"video", "video_shot", "video_shots", "first3s"}:
                keys.append("video_shots")
            elif o in {"buyer_show", "ugc"}:
                keys.append("buyer_show")
            elif o in {"competitor", "competitor_ref"}:
                keys.append("competitor")
        return keys or ["main_image"]

    def _select_template(self, category: str, override_id: str) -> ScriptTemplate | None:
        if override_id:
            t = self._lib.get(override_id)
            if t is not None:
                return t
        return self._lib.default_for_category(category)

    def _apply_frame_borrow(
        self,
        *,
        orig_template: ScriptTemplate,
        intent: IntentContext,
        borrow_forced: bool,
    ) -> tuple[ScriptTemplate, str, dict[str, Any] | None]:
        """按 intent 判断是否需要"仅借框架"重参数化。

        返回 (最终使用的模板, binding_reason, adapted_template_snapshot)。
        只在 orig_template.source_kind 是 v2 时启用（骨架化仅支持 v2）。
        """
        base_reason = f"category={orig_template.category}, slots={len(orig_template.slots)}"

        if orig_template.source_kind not in {"yaml_v2"}:
            return orig_template, base_reason, None

        auto_mismatch = self._intent_category_mismatch(intent, orig_template)
        if not (borrow_forced or auto_mismatch):
            return orig_template, base_reason, None

        try:
            skel = skeletonize(orig_template)
            adapted = adapt_skeleton(skel, intent)
        except Exception as exc:  # pragma: no cover - 兜底
            logger.warning("[compiler] borrow_frame 失败，回退原模板：%s", exc)
            return orig_template, base_reason + "（重参数化失败，已回退）", None

        # 把 adapted 注册到 library，保证后续按 template_slot_ref 查找命中
        try:
            self._lib.register(adapted)
        except Exception as exc:
            logger.warning("[compiler] adapted 模板注册失败：%s", exc)

        trigger = "手动勾选" if borrow_forced else "自动判定品类不匹配"
        product = intent.product_name or "新品类"
        reason = f"借用 {orig_template.template_id} 骨架 + 按 {product} 重参数化（{trigger}）"
        snapshot = {
            "original_template_id": orig_template.template_id,
            "original_name": orig_template.name,
            "adapted_template_id": adapted.template_id,
            "adapted_name": adapted.name,
            "trigger": "manual" if borrow_forced else "auto_mismatch",
        }
        return adapted, reason, snapshot

    @staticmethod
    def _intent_category_mismatch(intent: IntentContext, tpl: ScriptTemplate) -> bool:
        product = (intent.product_name or "").strip()
        tpl_cat = ""
        if isinstance(tpl.business_context, dict):
            tpl_cat = str(tpl.business_context.get("product_category") or "").strip()
        if not product or not tpl_cat:
            return False
        # 子串双向包含视为匹配（如"洁面乳"⊂"洁面乳 A"）
        if product in tpl_cat or tpl_cat in product:
            return False
        # 单字重合兜底：若重合字符比例高，也视为相关
        overlap = {c for c in product if c in tpl_cat}
        if overlap and len(overlap) >= max(2, len(tpl_cat) // 3):
            return False
        return True

    def _build_frame(
        self,
        *,
        plan_id: str,
        frame_key: str,
        template: ScriptTemplate,
        cfg: dict[str, Any],
        origin_x: float,
        origin_y: float,
        intent: IntentContext,
    ) -> tuple[Frame, list[ResultNode]]:
        result_type = _FRAME_KEY_TO_RESULT_TYPE.get(frame_key, "main_image")
        frame = Frame(
            plan_id=plan_id,
            frame_key=frame_key,
            template_id=template.template_id,
            title=f"{cfg['title']} · {template.name}",
            canvas_x=origin_x,
            canvas_y=origin_y,
            layout=cfg["layout"],
        )

        nodes: list[ResultNode] = []
        node_w, node_h = cfg["node_size"]
        gap = cfg["gap"]

        padding_left = 20.0
        padding_top = 52.0  # frame header 高度
        cols = max(1, self._cols_for(frame_key, len(template.slots), cfg))

        for i, slot in enumerate(template.slots):
            col = i % cols
            row = i // cols
            node_x = origin_x + padding_left + col * (node_w + gap)
            node_y = origin_y + padding_top + row * (node_h + gap)
            node = ResultNode(
                plan_id=plan_id,
                frame_id=frame.frame_id,
                slot_index=slot.index or (i + 1),
                role=slot.role,
                result_type=result_type,
                title=f"{cfg['title']} · {slot.role}",
                objective=slot.role,
                visual_spec=slot.visual_spec,
                copy_spec=slot.copy_spec,
                aspect_ratio=slot.aspect_ratio or "1:1",
                canvas_x=node_x,
                canvas_y=node_y,
                width=node_w,
                height=node_h,
                template_slot_ref=f"{template.template_id}#{slot.index}",
                intent_ref_fields=self._collect_intent_refs(intent),
                brand_rule_refs=list(template.default_brand_rules),
                status="draft",
            )
            nodes.append(node)

        frame.node_ids = [n.node_id for n in nodes]
        return frame, nodes

    @staticmethod
    def _cols_for(frame_key: str, slot_count: int, cfg: dict[str, Any]) -> int:
        if cfg["layout"] == "column":
            return 1
        if cfg["layout"] == "row":
            return slot_count
        # grid：按每行 4 个排布
        return 4

    @staticmethod
    def _collect_intent_refs(intent: IntentContext) -> list[str]:
        refs: list[str] = []
        if intent.product_name:
            refs.append(f"product:{intent.product_name}")
        if intent.audience:
            refs.append(f"audience:{intent.audience}")
        if intent.style_refs:
            refs.append(f"style:{intent.style_refs[0]}")
        if intent.must_have:
            refs.append(f"must:{';'.join(intent.must_have[:2])}")
        return refs

    @staticmethod
    def _estimate_frame_height(frame: Frame, n_nodes: int, cfg: dict[str, Any]) -> float:
        node_w, node_h = cfg["node_size"]
        gap = cfg["gap"]
        padding = 80.0
        if cfg["layout"] == "column":
            rows = n_nodes
        elif cfg["layout"] == "row":
            rows = 1
        else:
            rows = (n_nodes + 3) // 4
        return padding + rows * node_h + max(0, rows - 1) * gap
