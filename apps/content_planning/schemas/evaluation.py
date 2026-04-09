"""评价体系 Schema：端到端管线质量评分。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    """单维度评分。"""

    name: str = ""
    name_zh: str = ""
    score: float = 0.0  # 0-1
    weight: float = 1.0
    explanation: str = ""


class StageEvaluation(BaseModel):
    """单环节评价结果。"""

    evaluation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage: Literal["card", "brief", "match", "strategy", "content"] = "card"
    dimensions: list[DimensionScore] = Field(default_factory=list)
    overall_score: float = 0.0
    evaluator: str = "llm_judge"  # llm_judge / rule / human
    model_used: str = ""
    explanation: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def compute_overall(self) -> float:
        if not self.dimensions:
            return 0.0
        total_weight = sum(d.weight for d in self.dimensions)
        if total_weight == 0:
            return 0.0
        self.overall_score = sum(d.score * d.weight for d in self.dimensions) / total_weight
        return self.overall_score


class PipelineMetrics(BaseModel):
    """管线级聚合指标。"""

    opportunity_id: str = ""
    pipeline_completion_rate: float = 0.0  # card -> asset_bundle
    human_edit_ratio: float = 0.0
    locked_field_count: int = 0
    version_count: dict[str, int] = Field(default_factory=dict)  # stage -> count
    stage_transition_times: dict[str, float] = Field(default_factory=dict)  # stage -> seconds


class PipelineEvaluation(BaseModel):
    """全链路评价。"""

    evaluation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage_scores: dict[str, StageEvaluation] = Field(default_factory=dict)
    pipeline_score: float = 0.0
    metrics: PipelineMetrics = Field(default_factory=PipelineMetrics)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def compute_pipeline_score(self) -> float:
        stage_weights = {
            "card": 0.15,
            "brief": 0.25,
            "match": 0.15,
            "strategy": 0.25,
            "content": 0.20,
        }
        total = 0.0
        weight_sum = 0.0
        for stage, evaluation in self.stage_scores.items():
            w = stage_weights.get(stage, 0.2)
            total += evaluation.overall_score * w
            weight_sum += w
        self.pipeline_score = total / weight_sum if weight_sum > 0 else 0.0
        return self.pipeline_score
