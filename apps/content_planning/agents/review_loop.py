"""Review Loop: Post-publish feedback → memory → skill/strategy evolution.

Closes the loop: publish → performance feedback → lessons → memory → next-cycle improvement.
Implements D1 (Skill Version Evolution), D2 (Cross-session Preference Model),
and D3 (Strategy/Template Evolution).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.content_planning.agents.memory import AgentMemory, MemoryEntry
from apps.content_planning.agents.skill_registry import SkillDefinition, skill_registry

logger = logging.getLogger(__name__)


class PerformanceFeedback(BaseModel):
    """Post-publish performance data for an asset."""
    opportunity_id: str = ""
    asset_id: str = ""
    brand_id: str = ""
    publish_date: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)  # views, likes, saves, comments
    performance_tier: str = "average"  # top | good | average | poor
    human_notes: str = ""


class ReviewInsight(BaseModel):
    """Extracted insight from review."""
    insight_type: str = ""  # lesson | pattern | preference
    content: str = ""
    applicable_to: list[str] = Field(default_factory=list)  # stage tags


class EvolutionAction(BaseModel):
    """Proposed evolution action for skills/strategies/templates."""
    action_type: str = ""  # update_prompt | adjust_weight | create_variant | deprecate
    target_type: str = ""  # skill | strategy_template | brand_preference
    target_id: str = ""
    description: str = ""
    priority: int = 0


class ReviewLoopResult(BaseModel):
    """Full review loop processing result."""
    insights: list[ReviewInsight] = Field(default_factory=list)
    memories_stored: int = 0
    evolution_actions: list[EvolutionAction] = Field(default_factory=list)
    brand_preferences_updated: bool = False


class ReviewLoop:
    """Close the review → memory → evolution loop."""

    def __init__(self, memory: AgentMemory | None = None) -> None:
        self._memory = memory or AgentMemory()

    def process_feedback(self, feedback: PerformanceFeedback) -> ReviewLoopResult:
        """Process post-publish feedback and close the loop."""
        result = ReviewLoopResult()

        # 1. Extract insights
        insights = self._extract_insights(feedback)
        result.insights = insights

        # 2. Store to memory
        stored = self._store_feedback_memory(feedback, insights)
        result.memories_stored = stored

        # 3. Update brand preferences (D2)
        if feedback.performance_tier in ("top", "good"):
            self._update_brand_preferences(feedback)
            result.brand_preferences_updated = True

        # 4. Propose evolution actions (D1 + D3)
        result.evolution_actions = self._propose_evolutions(feedback, insights)

        # 5. Execute immediate evolutions
        self._execute_immediate_evolutions(result.evolution_actions)

        return result

    def track_skill_adoption(
        self,
        skill_id: str,
        adopted: bool,
        *,
        human_rating: float = 0.0,
    ) -> None:
        """D1: Track skill execution adoption and rating."""
        skill = skill_registry.get(skill_id)
        if skill is None:
            return
        if adopted:
            skill.success_count += 1
        else:
            skill.fail_count += 1

        if skill.success_rate < 0.3 and (skill.success_count + skill.fail_count) >= 5:
            logger.warning("Skill %s needs prompt version update (rate=%.1f%%)",
                          skill_id, skill.success_rate * 100)
            skill.last_updated = "needs_prompt_update"

    def _extract_insights(self, feedback: PerformanceFeedback) -> list[ReviewInsight]:
        insights: list[ReviewInsight] = []
        metrics = feedback.metrics
        tier = feedback.performance_tier

        if tier == "poor":
            views = metrics.get("views", 0)
            saves = metrics.get("saves", 0)
            if views > 1000 and saves < 10:
                insights.append(ReviewInsight(
                    insight_type="lesson",
                    content="高曝光但低收藏，标题吸引但内容种草力不足",
                    applicable_to=["strategy", "plan"],
                ))
            else:
                insights.append(ReviewInsight(
                    insight_type="lesson",
                    content=f"效果不佳 (tier={tier})，需审视整体策略方向",
                    applicable_to=["brief", "strategy"],
                ))

        if tier in ("top", "good"):
            insights.append(ReviewInsight(
                insight_type="pattern",
                content=f"高效果内容模式 (tier={tier})，可提取为可复用策略",
                applicable_to=["strategy", "template"],
            ))

        if feedback.human_notes:
            insights.append(ReviewInsight(
                insight_type="preference",
                content=feedback.human_notes[:300],
                applicable_to=["brand_preference"],
            ))

        return insights

    def _store_feedback_memory(
        self, feedback: PerformanceFeedback, insights: list[ReviewInsight],
    ) -> int:
        count = 0
        self._memory.store(MemoryEntry(
            opportunity_id=feedback.opportunity_id,
            brand_id=feedback.brand_id,
            category="performance_feedback",
            content=f"[{feedback.performance_tier}] metrics={feedback.metrics}",
            source_agent="review_loop",
            relevance_score=0.9 if feedback.performance_tier == "top" else 0.6,
            tags=[feedback.performance_tier, "feedback"],
        ))
        count += 1

        for insight in insights:
            self._memory.store(MemoryEntry(
                opportunity_id=feedback.opportunity_id,
                brand_id=feedback.brand_id,
                category=f"review_{insight.insight_type}",
                content=insight.content,
                source_agent="review_loop",
                relevance_score=0.8,
                tags=insight.applicable_to,
            ))
            count += 1

        return count

    def _update_brand_preferences(self, feedback: PerformanceFeedback) -> None:
        """D2: Update brand-level preferences from successful content."""
        if not feedback.brand_id:
            return
        self._memory.store(MemoryEntry(
            opportunity_id=feedback.opportunity_id,
            brand_id=feedback.brand_id,
            category="brand_preference",
            content=f"[{feedback.performance_tier}] 高效果内容 asset={feedback.asset_id}",
            source_agent="review_loop",
            relevance_score=0.85,
            tags=["brand_preference", feedback.performance_tier],
        ))

    def _propose_evolutions(
        self, feedback: PerformanceFeedback, insights: list[ReviewInsight],
    ) -> list[EvolutionAction]:
        actions: list[EvolutionAction] = []

        # D1: Skill evolution
        if feedback.performance_tier == "poor":
            actions.append(EvolutionAction(
                action_type="update_prompt",
                target_type="skill",
                target_id="",
                description="低效果内容相关 skill 需要 prompt 版本更新",
                priority=5,
            ))

        # D3: Strategy/template evolution
        if feedback.performance_tier in ("top", "good"):
            actions.append(EvolutionAction(
                action_type="create_variant",
                target_type="strategy_template",
                target_id="",
                description="高效果内容的策略模式可提取为可复用模板",
                priority=8,
            ))

        for insight in insights:
            if insight.insight_type == "lesson":
                actions.append(EvolutionAction(
                    action_type="adjust_weight",
                    target_type="skill",
                    description=f"基于教训调整：{insight.content[:100]}",
                    priority=3,
                ))

        return actions

    def _execute_immediate_evolutions(self, actions: list[EvolutionAction]) -> None:
        """Execute evolutions that can be applied immediately."""
        for action in actions:
            if action.action_type == "update_prompt" and action.target_id:
                skill = skill_registry.get(action.target_id)
                if skill:
                    skill.last_updated = f"flagged_{datetime.now(UTC).isoformat()}"
                    logger.info("Flagged skill %s for prompt update", action.target_id)
