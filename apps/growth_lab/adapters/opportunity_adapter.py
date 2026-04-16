"""XHSOpportunityCard -> TrendOpportunity 映射适配器。

不修改原 XHSOpportunityCard，通过 adapter 将现有机会卡
转入新链路的 TrendOpportunity 对象。
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from apps.growth_lab.schemas.trend_opportunity import TrendOpportunity
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard

logger = logging.getLogger(__name__)


def xhs_card_to_trend_opportunity(
    card: XHSOpportunityCard,
    *,
    workspace_id: str = "",
    brand_id: str = "",
    campaign_id: str = "",
) -> TrendOpportunity:
    """将 XHSOpportunityCard 映射为 TrendOpportunity。"""

    freshness = _compute_freshness(card)
    actionability = _compute_actionability(card)

    suggested_actions = []
    if card.selling_points:
        suggested_actions.append("卖点升级")
    if card.opportunity_type == "visual":
        suggested_actions.append("主图裂变")
    if card.hook:
        suggested_actions.append("前3秒裂变")
    if not suggested_actions:
        suggested_actions.append("标品打法分析")

    rich_context: dict = {}
    if card.pain_point:
        rich_context["pain_point"] = card.pain_point
    if card.desire:
        rich_context["desire"] = card.desire
    if card.hook:
        rich_context["hook"] = card.hook
    if card.selling_points:
        rich_context["selling_points"] = card.selling_points
    if card.content_angle:
        rich_context["content_angle"] = card.content_angle
    if card.why_now:
        rich_context["why_now"] = card.why_now
    if card.why_worth_doing:
        rich_context["why_worth_doing"] = card.why_worth_doing
    if card.audience:
        rich_context["audience"] = card.audience
    if card.scene:
        rich_context["scene"] = card.scene
    if card.format_suggestion:
        rich_context["format_suggestion"] = card.format_suggestion
    if card.insight_statement:
        rich_context["insight_statement"] = card.insight_statement
    if card.engagement_insight:
        rich_context["engagement_insight"] = card.engagement_insight
    if card.action_recommendation:
        rich_context["action_recommendation"] = card.action_recommendation
    if card.benchmark_refs:
        rich_context["benchmark_refs"] = card.benchmark_refs[:5]
    if card.need_refs:
        rich_context["need_refs"] = card.need_refs[:5]
    if card.style_refs:
        rich_context["style_refs"] = card.style_refs[:5]
    if card.visual_pattern_refs:
        rich_context["visual_pattern_refs"] = card.visual_pattern_refs[:5]

    return TrendOpportunity(
        opportunity_id=card.opportunity_id,
        title=card.title or card.summary[:60],
        summary=card.summary,
        source_platform="xiaohongshu",
        source_type="xhs_opportunity",
        freshness_score=freshness,
        relevance_score=card.confidence,
        actionability_score=actionability,
        linked_topics=card.entity_refs[:10],
        linked_people=card.audience_refs[:5],
        linked_scenarios=card.scene_refs[:5],
        suggested_actions=suggested_actions,
        evidence_refs=[e.evidence_id for e in card.evidence_refs[:10]],
        source_note_ids=card.source_note_ids,
        rich_context=rich_context,
        source_opportunity_id=card.opportunity_id,
        source_opportunity_type=card.opportunity_type,
        workspace_id=workspace_id,
        brand_id=brand_id,
        campaign_id=campaign_id,
        status=_map_status(card.opportunity_status),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _compute_freshness(card: XHSOpportunityCard) -> float:
    """基于 pipeline_run_id 时间戳估算新鲜度（简化版）。"""
    if card.pipeline_run_id:
        try:
            ts_hex = card.pipeline_run_id[:8]
            ts = int(ts_hex, 16)
            age_hours = (time.time() - ts) / 3600
            if age_hours < 24:
                return 0.9
            if age_hours < 72:
                return 0.7
            return 0.4
        except (ValueError, OverflowError):
            pass
    return 0.5


def _compute_actionability(card: XHSOpportunityCard) -> float:
    """基于卡片丰富度评估可执行度。"""
    score = 0.3
    if card.composite_review_score and card.composite_review_score > 0.6:
        score += 0.2
    if card.selling_points:
        score += 0.15
    if card.evidence_refs:
        score += 0.1
    if card.qualified_opportunity:
        score += 0.15
    if card.hook:
        score += 0.1
    return min(score, 1.0)


def _map_status(opp_status: str) -> str:
    mapping = {
        "pending_review": "new",
        "reviewed": "new",
        "promoted": "promoted",
        "rejected": "rejected",
    }
    return mapping.get(opp_status, "new")
