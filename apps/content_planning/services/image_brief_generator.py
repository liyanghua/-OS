"""ImageBriefGenerator：LLM 驱动的小红书桌布品类图片执行指令生成器。"""

from __future__ import annotations

import logging

from apps.content_planning.schemas.content_generation import (
    ImageBriefGenerationResult,
    ImageSlotBrief,
)
from apps.content_planning.schemas.note_plan import NewNotePlan
from apps.content_planning.services.prompt_registry import load_prompt
from apps.content_planning.utils.plan_trace import plan_trace_kwargs
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.intel_hub.extraction.llm_client import (
    call_text_llm,
    is_llm_available,
    parse_json_response,
)
from apps.template_extraction.schemas.agent_plan import ImageSlotPlan

logger = logging.getLogger(__name__)


def _get_system_prompt() -> str:
    return load_prompt("image_brief")["system"]


class ImageBriefGenerator:
    """LLM 优先，规则降级的图片执行指令生成器。"""

    def generate(
        self,
        plan: NewNotePlan,
        strategy: RewriteStrategy,
    ) -> ImageBriefGenerationResult:
        if plan.image_plan is None or not plan.image_plan.image_slots:
            return ImageBriefGenerationResult(**plan_trace_kwargs(plan), mode="no_image_plan")

        if is_llm_available():
            result = self._llm_generate(plan, strategy)
            if result.slot_briefs:
                return result
            logger.info("ImageBriefGenerator: LLM 返回空结果，降级到规则模式")

        return self._rule_fallback(plan, strategy)

    def _llm_generate(
        self,
        plan: NewNotePlan,
        strategy: RewriteStrategy,
    ) -> ImageBriefGenerationResult:
        user_prompt = self._build_user_prompt(plan, strategy)
        raw = call_text_llm(_get_system_prompt(), user_prompt, temperature=0.5, max_tokens=3000)
        if not raw:
            return ImageBriefGenerationResult(**plan_trace_kwargs(plan), mode="llm_empty")

        data = parse_json_response(raw)
        slot_data = data.get("slot_briefs", [])
        briefs: list[ImageSlotBrief] = []
        for item in slot_data:
            if isinstance(item, dict):
                briefs.append(ImageSlotBrief(
                    slot_index=item.get("slot_index", 0),
                    role=item.get("role", ""),
                    subject=item.get("subject", ""),
                    composition=item.get("composition", ""),
                    props=item.get("props", []),
                    text_overlay=item.get("text_overlay", ""),
                    color_mood=item.get("color_mood", ""),
                    avoid_items=item.get("avoid", item.get("avoid_items", [])),
                ))
        return ImageBriefGenerationResult(**plan_trace_kwargs(plan), slot_briefs=briefs, mode="llm")

    @staticmethod
    def _build_user_prompt(plan: NewNotePlan, strategy: RewriteStrategy) -> str:
        assert plan.image_plan is not None
        parts = [
            f"## 笔记目标\n{plan.note_goal or '种草收藏'}",
            f"## 核心卖点\n{plan.core_selling_point or ''}",
            f"## 策略定位\n{strategy.positioning_statement}",
            f"## 图组总体说明\n{plan.image_plan.global_notes[:300]}",
            f"## 图片策略方向\n" + "\n".join(f"- {s}" for s in strategy.image_strategy[:4]),
        ]

        parts.append("## 各槽位信息")
        for slot in plan.image_plan.image_slots:
            parts.append(
                f"### 第{slot.slot_index}张 - 角色: {slot.role}\n"
                f"意图: {slot.intent}\n"
                f"视觉指令: {slot.visual_brief[:200]}\n"
                f"必含元素: {'、'.join(slot.must_include_elements[:4])}\n"
                f"规避: {'、'.join(slot.avoid_elements[:4])}"
            )

        parts.append(
            "\n"
            + load_prompt("image_brief")["output_hint"].format(
                slot_count=len(plan.image_plan.image_slots)
            ).strip()
        )
        return "\n\n".join(parts)

    @staticmethod
    def _rule_fallback(plan: NewNotePlan, strategy: RewriteStrategy) -> ImageBriefGenerationResult:
        """规则降级：从 ImageSlotPlan 直接结构化提取。"""
        assert plan.image_plan is not None
        briefs: list[ImageSlotBrief] = []
        for slot in plan.image_plan.image_slots:
            briefs.append(_slot_to_brief(slot))
        return ImageBriefGenerationResult(**plan_trace_kwargs(plan), slot_briefs=briefs, mode="rule")


def _slot_to_brief(slot: ImageSlotPlan) -> ImageSlotBrief:
    return ImageSlotBrief(
        slot_index=slot.slot_index,
        role=slot.role,
        subject=slot.intent,
        composition=slot.visual_brief[:80] if slot.visual_brief else "",
        props=list(slot.must_include_elements[:5]),
        text_overlay="、".join(slot.copy_hints[:2]) if slot.copy_hints else "",
        color_mood="",
        avoid_items=list(slot.avoid_elements[:5]),
    )
