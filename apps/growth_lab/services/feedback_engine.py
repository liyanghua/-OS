"""FeedbackEngine — 评分回流编排层。

承接 docs/SOP_to_content_plan.md 第 13 节。

职责：
- 接收 FeedbackRecord（来自前端评分按钮 / Phase 5 业务指标抓取）。
- 写入 visual_feedback_records。
- 调用 WeightUpdater 触发规则权重更新（v0.1 仅 expert_score.overall）。

设计原则：
- 路由层只负责入参校验与调用本类，不直接操作 store。
- 调权失败不影响 feedback 落库（warn 不抛）。
- 自动从 StrategyCandidate.rule_refs 回填 FeedbackRecord.rule_ids，避免前端漏填。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.storage.rule_store import RuleStore
from apps.growth_lab.schemas.feedback_record import FeedbackRecord
from apps.growth_lab.services.weight_updater import WeightUpdater
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore

logger = logging.getLogger(__name__)


class FeedbackEngine:
    """统一处理评分回流，组合 store 写入 + 权重更新。"""

    def __init__(
        self,
        *,
        visual_strategy_store: VisualStrategyStore | None = None,
        rule_store: RuleStore | None = None,
        weight_updater: WeightUpdater | None = None,
    ) -> None:
        self.vs_store = visual_strategy_store or VisualStrategyStore()
        self.rule_store = rule_store or RuleStore()
        self.weight_updater = weight_updater or WeightUpdater(self.rule_store)

    def submit(self, record: FeedbackRecord) -> dict[str, Any]:
        """落库 + 触发权重回流，返回 dict 用于 API 响应。"""
        record = self._fill_rule_ids(record)
        payload = record.model_dump(mode="json")
        self.vs_store.save_feedback_record(payload)

        weight_history: list[dict[str, Any]] = []
        try:
            weight_history = self.weight_updater.update_from_expert_score(
                feedback_record=payload,
                rule_ids=list(record.rule_ids),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("权重回流失败：%s", exc)

        return {
            "feedback_record": payload,
            "weight_history": weight_history,
        }

    # ── 内部辅助 ────────────────────────────────────────────────

    def _fill_rule_ids(self, record: FeedbackRecord) -> FeedbackRecord:
        """若 FeedbackRecord.rule_ids 为空，从 StrategyCandidate.rule_refs 回填。"""
        if record.rule_ids or not record.strategy_candidate_id:
            return record
        candidate = self.vs_store.get_strategy_candidate(record.strategy_candidate_id)
        if not candidate:
            return record
        rule_refs = candidate.get("rule_refs") or []
        if rule_refs:
            record.rule_ids = list(rule_refs)
        return record
