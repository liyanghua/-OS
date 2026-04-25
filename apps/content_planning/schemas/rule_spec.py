"""RuleSpec — 视觉策略规则的可审核单元。

承接 docs/SOP_to_content_plan.md 第 6.2 节。
关键设计点：
- `category_scope` + `scene_scope` 是扩品类 / 扩场景的扩展位
- `evidence.source_quote` 必填，所有 LLM 抽取规则都必须能回链 MD 原文
- 字段使用 snake_case 与仓库其它 schema 一致
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.content_planning.schemas.source_document import SOPDimension


RuleReviewStatus = Literal["draft", "approved", "rejected", "needs_edit"]
RuleLifecycleStatus = Literal["candidate", "active", "deprecated"]


class RuleTrigger(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    required_context: list[str] = Field(default_factory=list)


class RuleRecommendation(BaseModel):
    variable_selection: dict[str, Any] = Field(default_factory=dict)
    creative_direction: dict[str, Any] = Field(default_factory=dict)
    copywriting_direction: dict[str, Any] = Field(default_factory=dict)
    prompt_direction: dict[str, Any] = Field(default_factory=dict)


class RuleConstraints(BaseModel):
    must_follow: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    conflict_rules: list[str] = Field(default_factory=list)


class RuleScoring(BaseModel):
    base_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    boost_factors: list[str] = Field(default_factory=list)
    penalty_factors: list[str] = Field(default_factory=list)


class RuleEvidence(BaseModel):
    source_document_id: str = ""
    source_file: str = ""
    source_quote: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RuleReview(BaseModel):
    status: RuleReviewStatus = "draft"
    reviewer: str = ""
    comments: str = ""
    reviewed_at: datetime | None = None


class RuleLifecycle(BaseModel):
    version: str = "v1"
    status: RuleLifecycleStatus = "candidate"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RuleSpec(BaseModel):
    """单条专家规则——经审核后即可加入 RulePack。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    rule_pack_id: str = ""

    dimension: SOPDimension = "visual_core"
    variable_category: str = ""
    variable_name: str = ""
    option_name: str = ""

    category_scope: list[str] = Field(default_factory=list)
    scene_scope: list[str] = Field(default_factory=lambda: ["taobao_main_image"])

    trigger: RuleTrigger = Field(default_factory=RuleTrigger)
    recommendation: RuleRecommendation = Field(default_factory=RuleRecommendation)
    constraints: RuleConstraints = Field(default_factory=RuleConstraints)
    scoring: RuleScoring = Field(default_factory=RuleScoring)
    evidence: RuleEvidence = Field(default_factory=RuleEvidence)
    review: RuleReview = Field(default_factory=RuleReview)
    lifecycle: RuleLifecycle = Field(default_factory=RuleLifecycle)
