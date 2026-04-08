"""BodyGenerator：LLM 驱动的小红书桌布品类正文生成器。"""

from __future__ import annotations

import logging

from apps.content_planning.schemas.content_generation import BodyGenerationResult
from apps.content_planning.schemas.note_plan import NewNotePlan
from apps.content_planning.services.prompt_registry import load_prompt
from apps.content_planning.utils.plan_trace import plan_trace_kwargs
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.intel_hub.extraction.llm_client import (
    call_text_llm,
    is_llm_available,
    parse_json_response,
)

logger = logging.getLogger(__name__)


def _get_system_prompt() -> str:
    return load_prompt("body")["system"]


class BodyGenerator:
    """LLM 优先，规则降级的正文生成器。"""

    def generate(
        self,
        plan: NewNotePlan,
        strategy: RewriteStrategy,
    ) -> BodyGenerationResult:
        if is_llm_available():
            result = self._llm_generate(plan, strategy)
            if result.body_draft:
                return result
            logger.info("BodyGenerator: LLM 返回空结果，降级到规则模式")

        return self._rule_fallback(plan, strategy)

    def _llm_generate(
        self,
        plan: NewNotePlan,
        strategy: RewriteStrategy,
    ) -> BodyGenerationResult:
        user_prompt = self._build_user_prompt(plan, strategy)
        raw = call_text_llm(_get_system_prompt(), user_prompt, temperature=0.7, max_tokens=2000)
        if not raw:
            return BodyGenerationResult(**plan_trace_kwargs(plan), mode="llm_empty")

        data = parse_json_response(raw)
        return BodyGenerationResult(
            **plan_trace_kwargs(plan),
            opening_hook=data.get("opening_hook", ""),
            body_outline=data.get("body_sections", data.get("body_outline", [])),
            body_draft=data.get("body_draft", ""),
            cta_text=data.get("cta", data.get("cta_text", "")),
            tone_check=data.get("tone_check", ""),
            mode="llm",
        )

    @staticmethod
    def _build_user_prompt(plan: NewNotePlan, strategy: RewriteStrategy) -> str:
        parts = [
            f"## 笔记目标\n{plan.note_goal or '种草收藏'}",
            f"## 核心卖点\n{plan.core_selling_point or ''}",
            f"## 目标场景\n{'、'.join(plan.target_scene[:4])}",
            f"## 策划定位\n{strategy.positioning_statement}",
            f"## 语气风格\n{strategy.tone_of_voice}",
        ]

        bp = plan.body_plan
        if bp.opening_hook:
            parts.append(f"## 开头钩子方向\n{bp.opening_hook}")
        if bp.body_outline:
            parts.append(f"## 正文大纲\n" + "\n".join(f"- {line}" for line in bp.body_outline))
        if bp.cta_direction:
            parts.append(f"## CTA 方向\n{bp.cta_direction}")
        if bp.tone_notes:
            parts.append(f"## 语气注意\n{'、'.join(bp.tone_notes)}")

        parts.append("\n" + load_prompt("body")["output_hint"].strip())
        return "\n\n".join(parts)

    @staticmethod
    def _rule_fallback(plan: NewNotePlan, strategy: RewriteStrategy) -> BodyGenerationResult:
        """规则降级：从策划大纲拼接骨架正文。"""
        bp = plan.body_plan
        opening = bp.opening_hook or strategy.new_hook or "最近发现了一块超好看的桌布～"
        sections: list[str] = []
        for line in bp.body_outline:
            sections.append(line)
        if not sections:
            sections = [
                f"核心卖点：{plan.core_selling_point or '高颜值桌布'}",
                f"场景：{'、'.join(plan.target_scene[:2]) or '居家日常'}",
                "总结推荐",
            ]
        cta = "喜欢的姐妹记得收藏+关注哦～" if plan.note_goal == "种草收藏" else "链接放评论区啦，需要的自取！"
        draft = f"{opening}\n\n" + "\n\n".join(sections) + f"\n\n{cta}"

        return BodyGenerationResult(
            **plan_trace_kwargs(plan),
            opening_hook=opening,
            body_outline=sections,
            body_draft=draft,
            cta_text=cta,
            tone_check="规则降级，建议人工润色",
            mode="rule",
        )
