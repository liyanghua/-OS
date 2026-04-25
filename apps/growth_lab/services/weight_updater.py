"""规则权重更新器 v0.1。

承接 docs/SOP_to_content_plan.md 第 13 节。

MVP 范围（v0.1）：
- 仅根据 FeedbackRecord.expert_score.overall 调整 RuleSpec.scoring.base_weight。
- CTR / 业务指标的回流路径预留 update_from_business_metrics() 空函数，Phase 5 接入。
- 每次调整都写入 rule_weight_history，便于审计。

调权公式（保守版）：
    delta = LR * ((expert_overall / 10.0) - 0.5)
其中 LR=0.05，expert_overall ∈ [0, 10]。
- 评分 5 分以上 → 加权（最多 +0.025/次）。
- 评分 5 分以下 → 减权（最多 -0.025/次）。
- 调权后裁剪到 [0.05, 1.0]。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.content_planning.storage.rule_store import RuleStore

logger = logging.getLogger(__name__)


LEARNING_RATE = 0.05
MIN_WEIGHT = 0.05
MAX_WEIGHT = 1.0


class WeightUpdater:
    """v0.1：仅由 expert_score.overall 调权。"""

    def __init__(self, rule_store: RuleStore | None = None) -> None:
        self.rule_store = rule_store or RuleStore()

    # ── 公开接口 ────────────────────────────────────────────────

    def update_from_expert_score(
        self,
        *,
        feedback_record: dict[str, Any],
        rule_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """根据一条 FeedbackRecord 调整命中规则的 base_weight。

        Args:
            feedback_record: FeedbackRecord.model_dump() 结构。
            rule_ids: 若传入则覆盖 feedback_record.rule_ids；用于编译时回填。

        Returns:
            list[RuleWeightHistory]（dict 化），便于 API 层回显。
        """
        expert = feedback_record.get("expert_score") or {}
        overall = float(expert.get("overall", 0.0) or 0.0)
        if overall <= 0.0:
            logger.debug("expert.overall=0，跳过权重更新")
            return []

        ids = rule_ids if rule_ids is not None else list(feedback_record.get("rule_ids") or [])
        if not ids:
            logger.debug("FeedbackRecord 未携带 rule_ids，跳过权重更新")
            return []

        feedback_id = feedback_record.get("id", "")
        delta = self._compute_delta(overall)
        records: list[dict[str, Any]] = []
        for rule_id in ids:
            history = self._apply_delta(
                rule_id=rule_id,
                delta=delta,
                reason=f"expert_overall={overall:.1f}",
                feedback_record_id=feedback_id,
            )
            if history is not None:
                records.append(history)
        return records

    def update_from_business_metrics(
        self,
        *,
        feedback_record: dict[str, Any],
        rule_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Phase 5 占位：CTR / 转化率回流。

        v0.1 不实现，始终返回 []。Phase 5 接 [`docs/SOP_to_content_plan.md`](docs/SOP_to_content_plan.md) 13.3。
        """
        _ = (feedback_record, rule_ids)
        logger.debug("update_from_business_metrics: Phase 5 reserved, no-op in v0.1")
        return []

    # ── 内部辅助 ────────────────────────────────────────────────

    def _compute_delta(self, overall: float) -> float:
        normalized = max(0.0, min(1.0, overall / 10.0)) - 0.5
        return LEARNING_RATE * normalized

    def _apply_delta(
        self,
        *,
        rule_id: str,
        delta: float,
        reason: str,
        feedback_record_id: str,
    ) -> dict[str, Any] | None:
        rule = self.rule_store.get_rule_spec(rule_id)
        if rule is None:
            logger.warning("WeightUpdater: rule %s 不存在，跳过", rule_id)
            return None

        scoring = rule.get("scoring") or {}
        old_weight = float(scoring.get("base_weight", 0.5) or 0.5)
        new_weight = max(MIN_WEIGHT, min(MAX_WEIGHT, old_weight + delta))
        actual_delta = round(new_weight - old_weight, 6)

        scoring["base_weight"] = new_weight
        rule["scoring"] = scoring
        lifecycle = rule.get("lifecycle") or {}
        lifecycle["last_review_at"] = _now_iso()
        rule["lifecycle"] = lifecycle
        self.rule_store.save_rule_spec(rule)

        history = {
            "id": uuid.uuid4().hex[:16],
            "rule_id": rule_id,
            "feedback_record_id": feedback_record_id,
            "old_weight": old_weight,
            "new_weight": new_weight,
            "delta": actual_delta,
            "reason": reason,
            "created_at": _now_iso(),
        }
        self.rule_store.save_rule_weight_history(history)
        logger.info(
            "WeightUpdater: rule=%s %.4f → %.4f (Δ=%+.4f, %s)",
            rule_id,
            old_weight,
            new_weight,
            actual_delta,
            reason,
        )
        return history


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
