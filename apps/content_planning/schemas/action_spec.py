"""ActionSpec: 统一的 AI 动作规格模型。

所有 AI 输出（run-agent / council / health_checker / advisor）统一产出 ActionSpec[]，
前端渲染为可点击的 action chips。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ActionType = Literal["regenerate", "refine", "lock", "compare", "apply", "discuss", "evaluate", "export"]
TargetObject = Literal["brief", "strategy", "template", "plan", "asset", "image_slot", "title", "body"]


class ActionSpec(BaseModel):
    """单个 AI 推荐动作，前端渲染为 action chip。"""

    action_type: ActionType = "refine"
    target_object: TargetObject | str = "brief"
    target_field: str = ""  # e.g. target_user, image_slot_3
    label: str = ""  # 显示文案
    description: str = ""
    preview_diff: dict[str, Any] = Field(default_factory=dict)
    confirmation_required: bool = True
    api_endpoint: str = ""  # /content-planning/...
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0  # higher = more prominent


class ActionSpecBundle(BaseModel):
    """A set of suggested actions from a single AI invocation."""

    source: str = ""  # health_checker | council | run-agent | advisor
    stage: str = ""
    opportunity_id: str = ""
    actions: list[ActionSpec] = Field(default_factory=list)


def actions_from_health_issues(
    issues: list[Any],
    opportunity_id: str,
    stage: str,
) -> list[ActionSpec]:
    """Convert HealthIssue[] from HealthChecker into ActionSpec[]."""
    actions: list[ActionSpec] = []
    for issue in issues:
        severity = getattr(issue, "severity", "info")
        target_field = getattr(issue, "target_field", "")
        suggestion = getattr(issue, "suggestion", "")
        dimension = getattr(issue, "dimension", "")

        if severity == "error":
            action_type: ActionType = "regenerate"
            priority = 10
        elif severity == "warning":
            action_type = "refine"
            priority = 5
        else:
            action_type = "refine"
            priority = 1

        actions.append(ActionSpec(
            action_type=action_type,
            target_object=stage,
            target_field=target_field or dimension,
            label=suggestion or f"修复 {dimension}",
            description=getattr(issue, "message", ""),
            api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
            payload={"stage": stage, "target_field": target_field, "action": action_type},
            priority=priority,
        ))
    return sorted(actions, key=lambda a: a.priority, reverse=True)


def actions_from_council_synthesis(
    proposed_updates: dict[str, Any],
    recommended_next_steps: list[str | dict[str, Any]],
    opportunity_id: str,
    stage: str,
) -> list[ActionSpec]:
    """Convert Council synthesis output into ActionSpec[]."""
    actions: list[ActionSpec] = []

    if proposed_updates:
        actions.append(ActionSpec(
            action_type="apply",
            target_object=stage,
            label="应用 Council 建议",
            description=f"将 {len(proposed_updates)} 个字段变更应用为草稿",
            preview_diff=proposed_updates,
            api_endpoint=f"/content-planning/council/{opportunity_id}/apply-as-draft",
            payload={"stage": stage, "updates": proposed_updates},
            priority=10,
        ))

    for step in recommended_next_steps:
        if isinstance(step, dict):
            label = step.get("label", "")
            action_type_str = step.get("action_type", "refine")
        else:
            label = str(step)
            action_type_str = "refine"

        if action_type_str not in ("regenerate", "refine", "lock", "compare", "apply", "discuss", "evaluate", "export"):
            action_type_str = "refine"

        actions.append(ActionSpec(
            action_type=action_type_str,  # type: ignore[arg-type]
            target_object=stage,
            label=label,
            api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
            priority=5,
        ))

    return actions
