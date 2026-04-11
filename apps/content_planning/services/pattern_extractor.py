"""PatternExtractor: 从发布反馈中自动提取 WinningPattern / FailedPattern。"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.schemas.feedback import FailedPattern, WinningPattern
from apps.content_planning.schemas.unified_feedback import UnifiedFeedback

logger = logging.getLogger(__name__)


class PatternExtractor:
    """从高/低表现反馈中提取可复用的模式或反模式。"""

    def __init__(self, plan_store=None):
        self._store = plan_store

    def evaluate(self, feedback: UnifiedFeedback) -> WinningPattern | FailedPattern | None:
        if feedback.performance_tier == "excellent":
            return self._extract_winning(feedback)
        elif feedback.performance_tier == "poor":
            return self._extract_failed(feedback)
        return None

    def _extract_winning(self, fb: UnifiedFeedback) -> WinningPattern:
        strategy_data = self._load_strategy(fb)
        pattern_type = self._infer_pattern_type(strategy_data)
        label = self._build_winning_label(fb, strategy_data)
        description = self._build_winning_description(fb, strategy_data)

        pattern = WinningPattern(
            workspace_id=fb.workspace_id,
            brand_id=fb.brand_id,
            pattern_type=pattern_type,
            label=label,
            description=description,
            source_opportunity_ids=[fb.opportunity_id],
            source_asset_bundle_ids=[fb.asset_bundle_id],
            avg_engagement_proxy=fb.engagement_score,
            sample_count=1,
            extra={
                "template_id": fb.template_id,
                "strategy_id": fb.strategy_id,
                "platform": fb.platform,
                "metrics": {
                    "like": fb.like_count,
                    "collect": fb.collect_count,
                    "comment": fb.comment_count,
                    "share": fb.share_count,
                },
            },
        )

        if self._store:
            try:
                self._store.save_winning_pattern(pattern)
                logger.info("Saved winning pattern %s for %s", pattern.pattern_id, fb.opportunity_id)
            except Exception:
                logger.warning("Failed to save winning pattern", exc_info=True)

        return pattern

    def _extract_failed(self, fb: UnifiedFeedback) -> FailedPattern:
        strategy_data = self._load_strategy(fb)
        pattern_type = self._infer_pattern_type(strategy_data)

        root_cause = "unknown"
        if fb.human_notes:
            root_cause = fb.human_notes[:200]
        elif fb.engagement_score < 0.05:
            root_cause = "互动极低，可能标题/封面吸引力不足"
        elif fb.collect_count == 0 and fb.like_count > 0:
            root_cause = "有赞无藏，内容可能缺乏实用收藏价值"

        pattern = FailedPattern(
            workspace_id=fb.workspace_id,
            brand_id=fb.brand_id,
            pattern_type=pattern_type,
            label=f"低效模式: {fb.template_id or 'unknown'}",
            description=f"engagement_score={fb.engagement_score:.2f}, tier={fb.performance_tier}",
            source_opportunity_ids=[fb.opportunity_id],
            source_asset_bundle_ids=[fb.asset_bundle_id],
            avg_engagement_proxy=fb.engagement_score,
            sample_count=1,
            root_cause=root_cause,
            extra={
                "template_id": fb.template_id,
                "strategy_id": fb.strategy_id,
                "human_edits": fb.human_edits_summary,
            },
        )

        if self._store:
            try:
                self._store.save_failed_pattern(pattern)
                logger.info("Saved failed pattern %s for %s", pattern.pattern_id, fb.opportunity_id)
            except Exception:
                logger.warning("Failed to save failed pattern", exc_info=True)

        return pattern

    def _load_strategy(self, fb: UnifiedFeedback) -> dict[str, Any]:
        if not self._store or not fb.opportunity_id:
            return {}
        try:
            session = self._store.load_session(fb.opportunity_id)
            return session.get("strategy", {}) if session else {}
        except Exception:
            return {}

    @staticmethod
    def _infer_pattern_type(strategy: dict[str, Any]) -> str:
        if strategy.get("hook_strategy"):
            return "hook"
        if strategy.get("scene_emphasis"):
            return "scene"
        if strategy.get("tone_of_voice"):
            return "tone"
        return "strategy"

    @staticmethod
    def _build_winning_label(fb: UnifiedFeedback, strategy: dict[str, Any]) -> str:
        parts = []
        if fb.template_id:
            parts.append(fb.template_id)
        if strategy.get("positioning_statement"):
            parts.append(strategy["positioning_statement"][:20])
        return " + ".join(parts) if parts else f"高效模式 ({fb.engagement_score:.0%})"

    @staticmethod
    def _build_winning_description(fb: UnifiedFeedback, strategy: dict[str, Any]) -> str:
        lines = [f"engagement_score={fb.engagement_score:.2f}, tier={fb.performance_tier}"]
        if strategy.get("new_hook"):
            lines.append(f"hook: {strategy['new_hook'][:50]}")
        if strategy.get("tone_of_voice"):
            lines.append(f"tone: {strategy['tone_of_voice'][:30]}")
        if fb.human_notes:
            lines.append(f"notes: {fb.human_notes[:80]}")
        return "; ".join(lines)
