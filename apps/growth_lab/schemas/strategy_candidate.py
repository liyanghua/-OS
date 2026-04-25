"""StrategyCandidate — 视觉策略候选。

承接 docs/SOP_to_content_plan.md 第 6.5 节。
单个候选包含六大维度变量选择、命中规则引用、评分。
`rule_refs` 必填——每个候选必须能回链触发它的 RuleSpec id。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StrategySelectedVariables(BaseModel):
    visual_core: dict[str, Any] = Field(default_factory=dict)
    people_interaction: dict[str, Any] = Field(default_factory=dict)
    function_selling_point: dict[str, Any] = Field(default_factory=dict)
    pattern_style: dict[str, Any] = Field(default_factory=dict)
    marketing_info: dict[str, Any] = Field(default_factory=dict)
    differentiation: dict[str, Any] = Field(default_factory=dict)


class StrategyScore(BaseModel):
    total: float = 0.0
    brand_fit: float = 0.0
    audience_fit: float = 0.0
    differentiation: float = 0.0
    function_clarity: float = 0.0
    category_recognition: float = 0.0
    generation_control: float = 0.0
    conversion_potential: float = 0.0


class StrategyCandidate(BaseModel):
    """单个策略候选——StrategyCompiler 输出的最小单元。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    visual_strategy_pack_id: str = ""

    name: str = ""
    archetype: str = ""
    hypothesis: str = ""
    target_audience: list[str] = Field(default_factory=list)

    selected_variables: StrategySelectedVariables = Field(default_factory=StrategySelectedVariables)

    rationale: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    score: StrategyScore = Field(default_factory=StrategyScore)

    rule_refs: list[str] = Field(default_factory=list)
    creative_brief_id: str = ""
    prompt_spec_id: str = ""

    status: Literal[
        "generated", "edited", "approved", "rejected", "sent_to_workbench",
    ] = "generated"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
