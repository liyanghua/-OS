"""direction_summary — 从最近的编辑事件聚合"当前方向"，写回 ResultNode.direction_summary。

规则优先，LLM fallback 失败时仅靠规则也能给出一个方向。
"""

from __future__ import annotations

import logging
from typing import Iterable

from apps.growth_lab.schemas.visual_workspace import (
    EditStrategyContext,
    EditTemplateContext,
    RecentEditHistory,
    ResultNode,
)
from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)


def build_recent_edit_history(
    store: GrowthLabStore, plan_id: str, node_id: str, *, limit: int = 5,
) -> RecentEditHistory:
    try:
        events = store.list_workspace_session_events(
            plan_id=plan_id, node_id=node_id, limit=200,
        )
    except Exception:  # noqa: BLE001
        events = []
    last_user: list[str] = []
    last_applied: list[str] = []
    last_proposals: list[str] = []
    for ev in reversed(events):
        t = ev.get("type") or ""
        p = ev.get("payload") or {}
        if t == "user_message" and p.get("text"):
            last_user.append(str(p["text"])[:160])
        if t in {"proposal_applied", "variant_done"} and p.get("summary"):
            last_applied.append(str(p["summary"])[:160])
        if t == "proposal_proposed" and p.get("summary"):
            last_proposals.append(str(p["summary"])[:160])
        if len(last_user) >= limit and len(last_applied) >= limit and len(last_proposals) >= limit:
            break
    return RecentEditHistory(
        last_user_requests=list(reversed(last_user))[-limit:],
        last_applied_changes=list(reversed(last_applied))[-limit:],
        last_proposal_summaries=list(reversed(last_proposals))[-limit:],
    )


def _rule_direction(
    history: RecentEditHistory,
    node: ResultNode,
    strategy: EditStrategyContext | None,
) -> str:
    """规则法：把最近 2-3 条修改意图压成一段短句。"""
    recent = list(history.last_user_requests[-3:]) + list(history.last_applied_changes[-2:])
    recent = [r for r in recent if r]
    base = (strategy.core_claim if strategy and strategy.core_claim else node.slot_objective) or ""
    if not recent:
        return base and f"围绕「{base}」出一版"
    tail = "；".join(r[:30] for r in recent[-3:])
    prefix = f"以「{base}」为主目标，" if base else ""
    return f"{prefix}最近方向：{tail}"


def infer_direction_summary(
    history: RecentEditHistory,
    node: ResultNode,
    template_ctx: EditTemplateContext | None = None,
    strategy_ctx: EditStrategyContext | None = None,
) -> str:
    """规则优先；LLM fallback（可选）。V1 只用规则。"""
    direction = _rule_direction(history, node, strategy_ctx)
    return direction.strip()[:200]


def refresh_direction_summary(
    store: GrowthLabStore, plan_id: str, node: ResultNode,
) -> str:
    """读取 session_events，计算方向摘要并回写 node。"""
    history = build_recent_edit_history(store, plan_id, node.node_id)
    summary = infer_direction_summary(history, node)
    node.direction_summary = summary
    try:
        store.save_workspace_node(node.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("refresh_direction_summary save failed: %s", exc)
    return summary
