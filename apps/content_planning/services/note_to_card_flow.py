"""NoteToCardFlow: 上游编排 — RawNote -> Card(enriched) -> Scorecard -> (auto-promote)。"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.content_planning.evaluation.stage_evaluator import evaluate_stage
from apps.content_planning.schemas.evaluation import StageEvaluation
from apps.content_planning.schemas.expert_scorecard import ExpertScorecard
from apps.content_planning.services.expert_scorer import ExpertScorer
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard

logger = logging.getLogger(__name__)


class GateResult(BaseModel):
    """单阶段门控结果。"""

    stage: str = ""
    passed: bool = True
    status: Literal["pass", "warn", "block"] = "pass"
    evaluation: StageEvaluation | None = None
    suggestions: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """整条链路的结果汇总。"""

    opportunity_id: str = ""
    card: dict[str, Any] | None = None
    scorecard: ExpertScorecard | None = None
    gates: list[GateResult] = Field(default_factory=list)
    promoted: bool = False
    blocked: bool = False
    block_reason: str = ""


class NoteToCardFlow:
    """
    编排链路:
      run_ingest_eval(parsed_note)
        -> compile_enriched_card(parsed_note, pipeline_result)
        -> run_card_eval(card)
        -> score_card(card, note_context)
        -> run_scorecard_eval(scorecard)
        -> if recommendation in {evaluate, initiate}: auto_promote
    """

    def __init__(self) -> None:
        self._scorer = ExpertScorer()

    def run(
        self,
        card: XHSOpportunityCard,
        parsed_note: dict[str, Any] | None = None,
        pipeline_details: dict[str, Any] | None = None,
        benchmarks: list[dict] | None = None,
        auto_promote: bool = True,
    ) -> PipelineResult:
        opp_id = card.opportunity_id
        result = PipelineResult(opportunity_id=opp_id)
        note_ctx = parsed_note or {}
        pipe_ctx = pipeline_details or {}

        # Step 1: ingest evaluation
        ingest_gate = self._run_ingest_eval(opp_id, note_ctx, pipe_ctx, benchmarks or [])
        result.gates.append(ingest_gate)
        if ingest_gate.status == "block":
            result.blocked = True
            result.block_reason = f"Ingest blocked: {'; '.join(ingest_gate.suggestions)}"
            return result

        # Step 2: enrich card with V6 fields
        enriched_card = self._enrich_card(card, note_ctx, pipe_ctx)
        result.card = enriched_card.model_dump()

        # Step 3: card evaluation
        card_gate = self._run_card_eval(opp_id, enriched_card)
        result.gates.append(card_gate)
        if card_gate.status == "block":
            result.blocked = True
            result.block_reason = f"Card blocked: {'; '.join(card_gate.suggestions)}"
            return result

        # Step 4: expert scoring
        note_engagement = self._extract_engagement(note_ctx)
        scorecard = self._scorer.score(enriched_card, note_engagement)
        result.scorecard = scorecard

        # Step 5: scorecard evaluation
        sc_gate = self._run_scorecard_eval(opp_id, scorecard)
        result.gates.append(sc_gate)

        # Step 6: promotion decision
        if scorecard.recommendation == "ignore":
            result.promoted = False
        elif auto_promote and scorecard.recommendation in ("evaluate", "initiate"):
            result.promoted = True
            enriched_card.card_status = "ready_for_score"
            result.card = enriched_card.model_dump()

        return result

    # ── 内部方法 ────────────────────────────────────────

    def _run_ingest_eval(
        self, opp_id: str, note_ctx: dict, pipe_ctx: dict, benchmarks: list
    ) -> GateResult:
        eval_result = evaluate_stage("ingest", opp_id, {
            "parsed_note": note_ctx,
            "pipeline_details": pipe_ctx,
            "benchmarks": benchmarks,
        })
        gate = GateResult(stage="ingest", evaluation=eval_result)
        gate.suggestions = self._extract_optimization_suggestions(eval_result)

        if eval_result.overall_score < 0.25:
            gate.status = "block"
            gate.passed = False
        elif eval_result.overall_score < 0.45:
            gate.status = "warn"
        else:
            gate.status = "pass"
        return gate

    def _run_card_eval(self, opp_id: str, card: XHSOpportunityCard) -> GateResult:
        card_dict = card.model_dump()
        eval_result = evaluate_stage("card", opp_id, {"card": card_dict})
        gate = GateResult(stage="card", evaluation=eval_result)
        gate.suggestions = self._extract_optimization_suggestions(eval_result)

        if eval_result.overall_score < 0.25:
            gate.status = "block"
            gate.passed = False
        elif eval_result.overall_score < 0.45:
            gate.status = "warn"
        return gate

    def _run_scorecard_eval(self, opp_id: str, scorecard: ExpertScorecard) -> GateResult:
        eval_result = evaluate_stage("scorecard", opp_id, {
            "scorecard": scorecard.model_dump(),
        })
        gate = GateResult(stage="scorecard", evaluation=eval_result)
        gate.suggestions = self._extract_optimization_suggestions(eval_result)

        if eval_result.overall_score < 0.3:
            gate.status = "warn"
        return gate

    @staticmethod
    def _enrich_card(
        card: XHSOpportunityCard,
        note_ctx: dict[str, Any],
        pipe_ctx: dict[str, Any],
    ) -> XHSOpportunityCard:
        """Fill V6 semantic fields from note context if not already set."""
        if not card.audience and note_ctx.get("audience_refs"):
            refs = note_ctx["audience_refs"]
            card.audience = refs[0] if isinstance(refs, list) and refs else str(refs)

        if not card.scene and card.scene_refs:
            card.scene = card.scene_refs[0] if card.scene_refs else ""

        if not card.pain_point and card.need_refs:
            card.pain_point = card.need_refs[0] if card.need_refs else ""

        if not card.hook and card.summary:
            card.hook = card.summary[:80]

        if not card.selling_points and card.value_proposition_refs:
            card.selling_points = list(card.value_proposition_refs[:5])

        if not card.why_worth_doing and card.insight_statement:
            card.why_worth_doing = card.insight_statement

        return card

    @staticmethod
    def _extract_engagement(note_ctx: dict[str, Any]) -> dict[str, Any]:
        """Extract engagement metrics from note context for ExpertScorer."""
        eng = note_ctx.get("engagement_summary", {})
        note_context = note_ctx.get("note_context", {})
        merged = {**note_context, **eng}
        return {
            "like_count": merged.get("like_count", merged.get("liked_count", 0)),
            "collect_count": merged.get("collect_count", merged.get("collected_count", 0)),
            "comment_count": merged.get("comment_count", merged.get("comments_count", 0)),
            "share_count": merged.get("share_count", 0),
            "type": note_ctx.get("type", note_ctx.get("note_type", "")),
        }

    @staticmethod
    def _extract_optimization_suggestions(eval_result: StageEvaluation) -> list[str]:
        suggestions: list[str] = []
        for dim in eval_result.dimensions:
            if dim.score < 0.4:
                suggestions.append(f"{dim.name_zh or dim.name}: {dim.explanation}")
        return suggestions[:5]
