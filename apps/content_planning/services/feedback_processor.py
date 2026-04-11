"""FeedbackProcessor: 统一反馈处理入口，触发 Pattern 提取 + 模板权重 + 记忆写入。"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.agents.memory import MemoryEntry
from apps.content_planning.schemas.unified_feedback import UnifiedFeedback

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """单一入口处理发布反馈，派发到三路下游。"""

    def __init__(self, plan_store=None, memory=None):
        self._plan_store = plan_store
        self._memory = memory

    def process(self, feedback: UnifiedFeedback) -> dict[str, Any]:
        feedback.compute_engagement_score()
        feedback.auto_tier()

        result: dict[str, Any] = {
            "feedback_id": feedback.feedback_id,
            "performance_tier": feedback.performance_tier,
            "engagement_score": feedback.engagement_score,
            "downstream": {},
        }

        pattern_result = self._run_pattern_extraction(feedback)
        result["downstream"]["pattern"] = pattern_result

        template_result = self._run_template_update(feedback)
        result["downstream"]["template"] = template_result

        memory_result = self._run_memory_write(feedback)
        result["downstream"]["memory"] = memory_result

        if self._plan_store:
            try:
                from apps.content_planning.schemas.feedback import FeedbackRecord

                fb_record = FeedbackRecord(
                    opportunity_id=feedback.opportunity_id,
                    asset_bundle_id=feedback.asset_bundle_id,
                    workspace_id=feedback.workspace_id,
                    brand_id=feedback.brand_id,
                    campaign_id=feedback.campaign_id,
                    engagement_proxy=feedback.engagement_score,
                    feedback_quality=feedback.performance_tier,
                    notes=feedback.human_notes,
                    approval_rounds=feedback.approval_rounds,
                    manual_edits_count=feedback.manual_edits_count,
                    time_to_ready=feedback.time_to_ready_seconds,
                )
                self._plan_store.save_feedback_record(fb_record)
            except Exception:
                logger.warning("Failed to save FeedbackRecord", exc_info=True)

        return result

    def _run_pattern_extraction(self, fb: UnifiedFeedback) -> dict[str, Any]:
        try:
            from apps.content_planning.services.pattern_extractor import PatternExtractor

            extractor = PatternExtractor(plan_store=self._plan_store)
            pattern = extractor.evaluate(fb)
            if pattern:
                return {"extracted": True, "pattern_id": pattern.pattern_id, "type": type(pattern).__name__}
            return {"extracted": False}
        except Exception as exc:
            logger.warning("Pattern extraction failed: %s", exc)
            return {"extracted": False, "error": str(exc)}

    def _run_template_update(self, fb: UnifiedFeedback) -> dict[str, Any]:
        if not fb.template_id:
            return {"updated": False, "reason": "no_template_id"}
        try:
            from apps.content_planning.schemas.feedback import EngagementResult, TemplateEffectivenessRecord

            record = TemplateEffectivenessRecord(
                template_id=fb.template_id,
                opportunity_id=fb.opportunity_id,
                asset_bundle_id=fb.asset_bundle_id,
                performance_label=fb.performance_tier,
                engagement=EngagementResult(
                    total_engagement=fb.like_count + fb.collect_count + fb.comment_count + fb.share_count,
                    collect_like_ratio=fb.collect_count / max(fb.like_count, 1),
                    comment_rate=fb.comment_count / max(fb.view_count, 1) if fb.view_count else 0,
                    performance_label=fb.performance_tier,
                ),
            )
            if self._plan_store and hasattr(self._plan_store, "save_template_effectiveness"):
                self._plan_store.save_template_effectiveness(record)
            return {"updated": True, "record_id": record.record_id}
        except Exception as exc:
            logger.warning("Template effectiveness update failed: %s", exc)
            return {"updated": False, "error": str(exc)}

    def _run_memory_write(self, fb: UnifiedFeedback) -> dict[str, Any]:
        if not self._memory:
            return {"written": False, "reason": "no_memory_instance"}
        try:
            tags = [fb.performance_tier, fb.platform]
            if fb.template_id:
                tags.append(f"tpl:{fb.template_id}")

            self._memory.store(
                MemoryEntry(
                    memory_id=f"publish_feedback_{fb.feedback_id}",
                    opportunity_id=fb.opportunity_id,
                    brand_id=fb.brand_id,
                    campaign_id=fb.campaign_id,
                    category="publish_feedback",
                    content=(
                        f"[{fb.performance_tier}] engagement={fb.engagement_score:.2f} "
                        f"like={fb.like_count} collect={fb.collect_count} "
                        f"comment={fb.comment_count} share={fb.share_count}. "
                        f"{fb.human_notes[:100] if fb.human_notes else ''}"
                    ),
                    relevance_score=0.9 if fb.performance_tier in ("excellent", "poor") else 0.6,
                    tags=tags,
                )
            )

            if fb.performance_tier == "excellent":
                self._memory.store(
                    MemoryEntry(
                        memory_id=f"winning_note_{fb.feedback_id}",
                        opportunity_id=fb.opportunity_id,
                        brand_id=fb.brand_id,
                        campaign_id=fb.campaign_id,
                        category="winning_pattern",
                        content=(
                            f"高效笔记 template={fb.template_id} strategy={fb.strategy_id} "
                            f"engagement={fb.engagement_score:.2f}"
                        ),
                        relevance_score=1.0,
                        tags=["winning", fb.platform],
                    )
                )
            elif fb.performance_tier == "poor":
                self._memory.store(
                    MemoryEntry(
                        memory_id=f"failed_note_{fb.feedback_id}",
                        opportunity_id=fb.opportunity_id,
                        brand_id=fb.brand_id,
                        campaign_id=fb.campaign_id,
                        category="failed_pattern",
                        content=(
                            f"低效笔记 template={fb.template_id} root_cause={fb.human_notes[:80]}"
                        ),
                        relevance_score=0.9,
                        tags=["failed", fb.platform],
                    )
                )

            return {"written": True}
        except Exception as exc:
            logger.warning("Memory write failed: %s", exc)
            return {"written": False, "error": str(exc)}
