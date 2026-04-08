"""DashboardMetrics：内容策划运营看板指标聚合。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DashboardMetrics:
    """聚合内容策划系统的运营指标。"""

    def __init__(self, review_store: Any = None, plan_store: Any = None) -> None:
        self._review_store = review_store
        self._plan_store = plan_store

    def compute(self) -> dict[str, Any]:
        """计算全部看板指标。"""
        metrics: dict[str, Any] = {}

        if self._review_store is not None:
            try:
                summary = self._review_store.get_review_summary()
                metrics["opportunity_pool"] = {
                    "total": summary.get("total_opportunities", 0),
                    "reviewed": summary.get("reviewed_opportunities", 0),
                    "promoted": summary.get("promoted_opportunities", 0),
                    "promoted_rate": round(
                        summary.get("promoted_opportunities", 0)
                        / max(summary.get("total_opportunities", 1), 1),
                        3,
                    ),
                    "avg_quality_score": summary.get("average_manual_quality_score", 0),
                }
            except Exception:
                logger.debug("Failed to compute opportunity metrics", exc_info=True)
                metrics["opportunity_pool"] = {}

        if self._plan_store is not None:
            try:
                total_sessions = self._plan_store.session_count()
                generated = self._plan_store.list_sessions(status="generated", page_size=1)
                exported = self._plan_store.list_sessions(status="exported", page_size=1)

                metrics["planning_pipeline"] = {
                    "total_sessions": total_sessions,
                    "generated_count": generated.get("total", 0),
                    "exported_count": exported.get("total", 0),
                    "generation_rate": round(
                        generated.get("total", 0) / max(total_sessions, 1), 3
                    ),
                }
            except Exception:
                logger.debug("Failed to compute planning metrics", exc_info=True)
                metrics["planning_pipeline"] = {}

        if self._review_store is not None:
            try:
                type_counts = self._review_store.type_counts()
                metrics["template_distribution"] = type_counts
            except Exception:
                metrics["template_distribution"] = {}

        return metrics
