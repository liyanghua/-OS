"""Opportunity Readiness Checker: Evidence completeness, review consensus, history comparison.

Powers the Opportunity Workspace with readiness score, blockers, and historical memory injection.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from apps.content_planning.agents.memory import AgentMemory
from apps.content_planning.schemas.action_spec import ActionSpec

logger = logging.getLogger(__name__)


class ReadinessBlocker(BaseModel):
    """Single blocker preventing promotion."""
    dimension: str = ""
    message: str = ""
    severity: str = "warning"  # error | warning


class OpportunityReadinessResult(BaseModel):
    """Readiness assessment for promoting an opportunity."""
    readiness_score: float = 0.0
    is_ready: bool = False
    blockers: list[ReadinessBlocker] = Field(default_factory=list)
    evidence_completeness: float = 0.0
    review_consensus_exists: bool = False
    similar_history_count: int = 0
    similar_history_summary: str = ""
    actions: list[ActionSpec] = Field(default_factory=list)
    explanation: str = ""


class OpportunityReadinessChecker:
    """Assess whether an opportunity is ready for promotion to Brief."""

    def __init__(self, memory: AgentMemory | None = None) -> None:
        self._memory = memory or AgentMemory()

    def check(
        self,
        opportunity_id: str,
        card: Any = None,
        review_summary: dict[str, Any] | None = None,
        source_notes: list[Any] | None = None,
        *,
        brand_id: str = "",
    ) -> OpportunityReadinessResult:
        """Full readiness check: evidence + review + history."""
        result = OpportunityReadinessResult()

        # Evidence completeness
        evidence_score = self._check_evidence(card, source_notes)
        result.evidence_completeness = evidence_score

        # Review consensus
        if review_summary and review_summary.get("consensus"):
            result.review_consensus_exists = True
        else:
            result.blockers.append(ReadinessBlocker(
                dimension="review", message="尚无 Review 共识",
                severity="warning",
            ))

        # Historical similarity
        history = self._inject_history(opportunity_id, brand_id=brand_id)
        result.similar_history_count = history["count"]
        result.similar_history_summary = history["summary"]

        # Compute readiness score
        score = evidence_score * 0.5
        if result.review_consensus_exists:
            score += 0.3
        if result.similar_history_count > 0:
            score += 0.2
        result.readiness_score = min(score, 1.0)
        result.is_ready = result.readiness_score >= 0.6 and evidence_score >= 0.5

        # Build actions
        if not result.is_ready:
            if evidence_score < 0.5:
                result.actions.append(ActionSpec(
                    action_type="refine", target_object="brief",
                    label="补充机会证据",
                    description="证据完整度不足，请补充更多源笔记或市场信号",
                    api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                    priority=10,
                ))
            if not result.review_consensus_exists:
                result.actions.append(ActionSpec(
                    action_type="discuss", target_object="brief",
                    label="发起 Council 讨论",
                    description="通过多角色讨论建立共识",
                    api_endpoint=f"/content-planning/discussion/{opportunity_id}",
                    priority=8,
                ))
        else:
            result.actions.append(ActionSpec(
                action_type="apply", target_object="brief",
                label="进入 Brief 编译",
                description="机会就绪，可进入 Brief 阶段",
                api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                priority=10,
            ))

        cond_parts: list[str] = []
        if evidence_score < 0.5:
            cond_parts.append("证据不足")
        if not result.review_consensus_exists:
            cond_parts.append("缺少 Review 共识")
        result.explanation = "、".join(cond_parts) if cond_parts else "机会就绪"

        return result

    def _check_evidence(self, card: Any, source_notes: list[Any] | None) -> float:
        """Check evidence completeness of the opportunity card."""
        if card is None:
            return 0.0

        score = 0.3  # Base: card exists
        has_title = bool(getattr(card, "title", None) or (card.get("title") if isinstance(card, dict) else ""))
        has_category = bool(getattr(card, "category", None) or (card.get("category") if isinstance(card, dict) else ""))
        has_source = bool(getattr(card, "signal_source", None) or (card.get("signal_source") if isinstance(card, dict) else ""))

        if has_title:
            score += 0.2
        if has_category:
            score += 0.1
        if has_source:
            score += 0.1
        if source_notes and len(source_notes) >= 1:
            score += 0.2
        if source_notes and len(source_notes) >= 3:
            score += 0.1

        return min(score, 1.0)

    def _inject_history(self, opportunity_id: str, *, brand_id: str = "") -> dict[str, Any]:
        """Inject cross-opportunity lessons from project memory."""
        history_text = self._memory.inject_cross_opportunity_lessons(
            opportunity_id, brand_id=brand_id, limit=5,
        )
        if not history_text:
            return {"count": 0, "summary": ""}
        lines = [l for l in history_text.strip().split("\n") if l.strip()]
        return {
            "count": len(lines),
            "summary": history_text[:500],
        }
