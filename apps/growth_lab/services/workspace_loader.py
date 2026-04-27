"""WorkspaceLoader — 把 StrategyCandidate / CreativeBrief / PromptSpec
装载到无限画布（Growth Lab Workspace）。

承接「视觉产线分流 + 小红书封面联动」plan 第 3 节。

主图（taobao_main_image）/详情首屏/视频首帧三类候选进入
/growth-lab/workspace 时，需要在 GrowthLabStore 创建一个 Plan，
让无限画布拿到 plan_id 后渲染候选概览（左栏）+ 模板节点。

本次范围：plan + frames + nodes 创建 + candidate metadata 嵌入
generation_rules（不实现多节点拖拽推演 UI）。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.growth_lab.schemas.creative_brief import CreativeBrief
from apps.growth_lab.schemas.prompt_spec import PromptSpec
from apps.growth_lab.schemas.strategy_candidate import StrategyCandidate
from apps.growth_lab.schemas.visual_workspace import IntentContext
from apps.growth_lab.services.visual_plan_compiler import VisualPlanCompiler
from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)


_SCENE_TO_OUTPUT_TYPE: dict[str, str] = {
    "taobao_main_image": "main_image",
    "detail_first_screen": "detail",
    "video_first_frame": "video_shots",
}


class WorkspaceLoader:
    """主图候选 → /growth-lab/workspace plan_id。"""

    def __init__(self, store: GrowthLabStore | None = None) -> None:
        self.store = store or GrowthLabStore()

    def load_candidate(
        self,
        *,
        candidate: StrategyCandidate,
        brief: CreativeBrief,
        prompt_spec: PromptSpec,
        scene: str,
        opportunity_id: str = "",
        notes: str = "",
        workspace_id: str = "",
        brand_id: str = "",
    ) -> dict[str, Any]:
        """编译一个最小可用的 plan，并把 candidate metadata 嵌入。

        返回 {plan_id, frame_count, node_count, candidate_meta}。
        """
        intent = self._build_intent(
            candidate=candidate, brief=brief, scene=scene
        )
        compiler = VisualPlanCompiler()
        try:
            plan, frames, nodes = compiler.compile(intent)
        except Exception as exc:  # noqa: BLE001
            # 模板库可能没有对应类目模板时退化为空 plan，保证联动可见。
            logger.warning("VisualPlanCompiler 编译失败，退化为占位 plan：%s", exc)
            plan, frames, nodes = self._fallback_plan(intent)

        candidate_meta = {
            "candidate_id": candidate.id,
            "creative_brief_id": brief.id,
            "prompt_spec_id": prompt_spec.id,
            "archetype": candidate.archetype,
            "score": candidate.score.model_dump() if hasattr(candidate.score, "model_dump") else {},
            "rule_refs": list(candidate.rule_refs),
            "scene": scene,
            "opportunity_id": opportunity_id,
            "notes": notes,
            "loaded_at": datetime.now(UTC).isoformat(),
        }

        plan_dict = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else dict(plan)
        plan_dict["workspace_id"] = workspace_id
        plan_dict["brand_id"] = brand_id

        # 把 candidate metadata 写到 generation_rules 子键，方便 workspace.html
        # 通过 /api/workspace/plan/{plan_id} 一次取齐。
        gen_rules = dict(plan_dict.get("generation_rules") or {})
        gen_rules["visual_strategy_candidate"] = candidate_meta
        plan_dict["generation_rules"] = gen_rules

        # 持久化
        self.store.save_workspace_plan(plan_dict)
        for f in frames:
            f_dict = f.model_dump(mode="json") if hasattr(f, "model_dump") else dict(f)
            self.store.save_workspace_frame(f_dict)
        for n in nodes:
            n_dict = n.model_dump(mode="json") if hasattr(n, "model_dump") else dict(n)
            self.store.save_workspace_node(n_dict)

        return {
            "plan_id": plan_dict.get("plan_id", ""),
            "frame_count": len(frames),
            "node_count": len(nodes),
            "candidate_meta": candidate_meta,
        }

    def _build_intent(
        self,
        *,
        candidate: StrategyCandidate,
        brief: CreativeBrief,
        scene: str,
    ) -> IntentContext:
        product_name = ""
        if brief.product.visible_features:
            product_name = brief.product.visible_features[0][:24]
        if not product_name and candidate.name:
            product_name = candidate.name[:24]

        audience = ""
        if candidate.target_audience:
            audience = "、".join(candidate.target_audience[:2])

        must_have: list[str] = []
        must_have.extend(brief.product.visible_features[:3])
        must_have.extend(brief.copywriting.selling_points[:2])

        avoid: list[str] = list(brief.scene.forbidden_props[:3])
        avoid.extend([n for n in brief.negative if isinstance(n, str)][:5])

        style_refs: list[str] = []
        if brief.style.tone:
            style_refs.append(brief.style.tone)
        style_refs.extend(brief.style.color_palette[:3])

        scenario_refs: list[str] = []
        if brief.scene.background:
            scenario_refs.append(brief.scene.background)
        if brief.scene.environment:
            scenario_refs.append(brief.scene.environment)

        output_type = _SCENE_TO_OUTPUT_TYPE.get(scene, "main_image")

        return IntentContext(
            product_name=product_name,
            audience=audience,
            output_types=[output_type],
            style_refs=style_refs,
            scenario_refs=scenario_refs,
            must_have=[m for m in must_have if m],
            avoid=[a for a in avoid if a],
            requested_counts={output_type: 4},
            model_preference="auto",
            source_spec_id=candidate.id,
        )

    def _fallback_plan(self, intent: IntentContext):
        """模板库不命中时的兜底：手工合成一个空骨架 plan，无 frame/node。"""
        from apps.growth_lab.schemas.visual_workspace import CompilePlan

        plan = CompilePlan(
            plan_id=uuid.uuid4().hex[:16],
            intent=intent,
            template_bindings=[],
            frame_ids=[],
            generation_rules={},
            evaluation_rules={},
            status="draft",
        )
        return plan, [], []
