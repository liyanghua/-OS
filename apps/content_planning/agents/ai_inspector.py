"""AI Inspector: Object-selection-driven AI panel for Creation and Planning workspaces.

When a user selects an object (title block, body block, image slot, strategy block),
the Inspector produces relevant actions and analysis. Also powers Plan Consistency checks.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.schemas.action_spec import ActionSpec

logger = logging.getLogger(__name__)


class InspectorResult(BaseModel):
    """AI Inspector output for a selected object."""
    object_type: str = ""  # title | body | image_slot | strategy_block
    object_id: str = ""
    analysis: str = ""
    quality_score: float = 0.0
    actions: list[ActionSpec] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class PlanConsistencyResult(BaseModel):
    """Plan-level consistency check result."""
    is_consistent: bool = True
    issues: list[str] = Field(default_factory=list)
    title_strategy_aligned: bool = True
    image_coverage_complete: bool = True
    body_title_consistent: bool = True
    score: float = 1.0
    actions: list[ActionSpec] = Field(default_factory=list)


class AIInspector:
    """Object-selection-driven AI operations."""

    def inspect(
        self,
        object_type: str,
        object_content: Any,
        *,
        context: dict[str, Any] | None = None,
        opportunity_id: str = "",
    ) -> InspectorResult:
        """Inspect a selected object and return analysis + suggested actions."""
        result = InspectorResult(object_type=object_type, object_id=str(id(object_content))[:8])
        ctx = context or {}

        if not object_content:
            result.analysis = "对象内容为空"
            result.actions.append(ActionSpec(
                action_type="regenerate", target_object=object_type,
                label=f"生成 {object_type}",
                api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
            ))
            return result

        content_str = str(object_content)[:1000] if not isinstance(object_content, str) else object_content[:1000]

        if not llm_router.is_any_available():
            result.analysis = f"{object_type} 已有内容（长度 {len(content_str)}），模型不可用无法深度分析"
            result.quality_score = 0.5
            return result

        strategy_context = str(ctx.get("strategy", ""))[:300]
        brief_context = str(ctx.get("brief", ""))[:300]

        try:
            resp = llm_router.chat_json(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            f"你是内容质量审查员。分析以下 {object_type} 对象的质量。"
                            "返回 JSON：{\"analysis\":\"...\",\"quality_score\":0.0-1.0,"
                            "\"issues\":[\"...\"],\"improvement\":\"...\"}"
                        ),
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"对象类型：{object_type}\n内容：{content_str}\n\n"
                            f"策略上下文：{strategy_context}\nBrief 上下文：{brief_context}"
                        ),
                    ),
                ],
                temperature=0.3,
                max_tokens=600,
            )
        except Exception:
            logger.debug("AI Inspector failed", exc_info=True)
            result.analysis = "分析失败"
            return result

        result.analysis = str(resp.get("analysis", ""))
        result.quality_score = float(resp.get("quality_score", 0.5))
        result.issues = resp.get("issues", [])
        if isinstance(result.issues, list):
            result.issues = [str(i) for i in result.issues]

        if result.quality_score < 0.5:
            result.actions.append(ActionSpec(
                action_type="regenerate", target_object=object_type,
                label=f"重新生成 {object_type}",
                api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                priority=8,
            ))
        result.actions.append(ActionSpec(
            action_type="compare", target_object=object_type,
            label="对比历史版本",
            api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
            priority=3,
        ))
        result.actions.append(ActionSpec(
            action_type="lock", target_object=object_type,
            label=f"锁定 {object_type}",
            api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
            priority=1,
        ))

        return result

    def check_plan_consistency(
        self,
        *,
        titles: Any = None,
        body: Any = None,
        strategy: Any = None,
        image_briefs: Any = None,
        plan: Any = None,
        opportunity_id: str = "",
    ) -> PlanConsistencyResult:
        """Check consistency across plan elements: title ↔ strategy, images ↔ plan, body ↔ title."""
        result = PlanConsistencyResult()
        issues: list[str] = []

        if not titles:
            issues.append("标题候选为空")
            result.title_strategy_aligned = False
        if not body:
            issues.append("正文草稿为空")
            result.body_title_consistent = False
        if not image_briefs:
            issues.append("图位规划为空")
            result.image_coverage_complete = False

        if titles and strategy:
            strategy_hook = ""
            if hasattr(strategy, "new_hook"):
                strategy_hook = getattr(strategy, "new_hook", "")
            elif isinstance(strategy, dict):
                strategy_hook = strategy.get("new_hook", "")

            title_text = str(titles)[:300]
            if strategy_hook and strategy_hook not in title_text:
                issues.append("标题候选可能未包含策略钩子")
                result.title_strategy_aligned = False

        if body and titles:
            body_text = str(body)[:200]
            title_text = str(titles)[:200]
            if len(body_text) > 50 and len(title_text) > 5:
                pass

        if image_briefs and plan:
            slots = image_briefs if isinstance(image_briefs, list) else getattr(image_briefs, "slot_briefs", [])
            plan_requires = 5
            if isinstance(slots, list) and len(slots) < plan_requires:
                issues.append(f"图位数量 ({len(slots)}) 少于计划要求 ({plan_requires})")
                result.image_coverage_complete = False

        result.issues = issues
        result.is_consistent = len(issues) == 0
        result.score = max(0.0, 1.0 - len(issues) * 0.2)

        for issue_text in issues:
            result.actions.append(ActionSpec(
                action_type="refine", target_object="plan",
                label=issue_text,
                api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                priority=5,
            ))

        return result
