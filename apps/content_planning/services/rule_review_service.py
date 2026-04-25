"""rule_review_service — 规则审核台业务服务。

支持的操作：
- approve: 通过 → review.status = approved
- reject: 拒绝 → review.status = rejected
- request_edit: 标注需修改 → review.status = needs_edit
- update_weight: 调整 baseWeight（不改 review status）
- patch: 自由修改 RuleSpec 字段（如 must_avoid 增删）
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from apps.content_planning.schemas.rule_spec import RuleReviewStatus, RuleSpec
from apps.content_planning.storage.rule_store import RuleStore

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class RuleReviewService:
    def __init__(self, store: RuleStore | None = None) -> None:
        self.store = store or RuleStore()

    def list_rules(
        self,
        *,
        category: str | None = None,
        dimension: str | None = None,
        review_status: RuleReviewStatus | None = None,
        rule_pack_id: str | None = None,
        limit: int = 500,
    ) -> list[RuleSpec]:
        rows = self.store.list_rule_specs(
            category=category,
            dimension=dimension,
            review_status=review_status,
            rule_pack_id=rule_pack_id,
            limit=limit,
        )
        return [RuleSpec(**row) for row in rows]

    def get(self, rule_id: str) -> RuleSpec | None:
        raw = self.store.get_rule_spec(rule_id)
        return RuleSpec(**raw) if raw else None

    def review(
        self,
        rule_id: str,
        *,
        action: str,
        reviewer: str = "",
        comments: str = "",
        new_weight: float | None = None,
        patch: dict[str, Any] | None = None,
    ) -> RuleSpec | None:
        """执行单条审核动作。"""
        raw = self.store.get_rule_spec(rule_id)
        if not raw:
            return None
        rule = RuleSpec(**raw)

        new_status: RuleReviewStatus | None = None
        if action == "approve":
            new_status = "approved"
            rule.lifecycle.status = "active"
        elif action == "reject":
            new_status = "rejected"
            rule.lifecycle.status = "deprecated"
        elif action == "request_edit":
            new_status = "needs_edit"
        elif action == "update_weight":
            pass
        elif action == "patch":
            pass
        else:
            raise ValueError(f"unsupported review action: {action}")

        if new_status is not None:
            rule.review.status = new_status
        rule.review.reviewer = reviewer or rule.review.reviewer
        rule.review.comments = comments or rule.review.comments
        rule.review.reviewed_at = _now()

        if new_weight is not None:
            rule.scoring.base_weight = max(0.0, min(1.0, float(new_weight)))

        if patch:
            self._apply_patch(rule, patch)

        rule.lifecycle.updated_at = _now()
        self.store.save_rule_spec(rule.model_dump())
        return rule

    @staticmethod
    def _apply_patch(rule: RuleSpec, patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if key == "must_avoid":
                rule.constraints.must_avoid = list(value or [])
            elif key == "must_follow":
                rule.constraints.must_follow = list(value or [])
            elif key == "boost_factors":
                rule.scoring.boost_factors = list(value or [])
            elif key == "penalty_factors":
                rule.scoring.penalty_factors = list(value or [])
            elif key == "trigger_conditions":
                rule.trigger.conditions = list(value or [])
            elif key == "source_quote":
                rule.evidence.source_quote = str(value or "")
            elif key == "scene_scope":
                rule.scene_scope = list(value or [])
            elif key == "category_scope":
                rule.category_scope = list(value or [])
            elif key == "variable_category":
                rule.variable_category = str(value or "")
            elif key == "variable_name":
                rule.variable_name = str(value or "")
            elif key == "option_name":
                rule.option_name = str(value or "")
