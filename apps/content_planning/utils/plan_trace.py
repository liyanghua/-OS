"""从 NewNotePlan 提取生成结果所需的回溯字段。"""

from __future__ import annotations

from typing import Any

from apps.content_planning.schemas.note_plan import NewNotePlan


def plan_trace_kwargs(plan: NewNotePlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "opportunity_id": plan.opportunity_id or "",
        "brief_id": plan.brief_id or "",
        "strategy_id": plan.strategy_id or "",
        "template_id": plan.template_id or "",
    }
