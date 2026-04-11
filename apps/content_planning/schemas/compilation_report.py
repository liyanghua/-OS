"""编译报告：记录全链路编译质量、降级状态与优化建议。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.content_planning.schemas.evaluation import StageEvaluation


class ImprovementItem(BaseModel):
    """单条改进说明。"""

    dimension: str = ""
    before_label: str = ""
    after_label: str = ""
    explanation: str = ""
    impact: str = ""


class QualityExplanation(BaseModel):
    """生成结果 vs 源笔记的差异化解释。"""

    vs_source_improvements: list[ImprovementItem] = Field(default_factory=list)
    strategy_alignment_score: float = 0.0
    predicted_engagement_factors: list[str] = Field(default_factory=list)
    optimization_suggestions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class CompilationReport(BaseModel):
    """全链路编译报告，附带每阶段质量评分与可执行建议。"""

    report_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    pipeline_run_id: str = ""
    stage_scores: dict[str, StageEvaluation] = Field(default_factory=dict)
    pipeline_score: float = 0.0
    quality_gate_passed: bool = True
    degraded_stages: list[str] = Field(default_factory=list)
    total_time_seconds: float = 0.0
    stage_times: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    quality_explanation: QualityExplanation | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def compute_pipeline_score(self) -> float:
        stage_weights = {
            "brief": 0.25, "strategy": 0.25, "plan": 0.20, "asset": 0.30,
        }
        total = 0.0
        weight_sum = 0.0
        for stage, evaluation in self.stage_scores.items():
            w = stage_weights.get(stage, 0.2)
            total += evaluation.overall_score * w
            weight_sum += w
        self.pipeline_score = total / weight_sum if weight_sum > 0 else 0.0
        self.quality_gate_passed = all(
            ev.overall_score >= 0.5 for ev in self.stage_scores.values()
        )
        return self.pipeline_score


class PublishReadyPackage(BaseModel):
    """可直接发布的内容包，从 AssetBundle 格式化而来。"""

    package_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_bundle_id: str = ""
    platform: str = "xhs"

    selected_title: str = ""
    title_rationale: str = ""
    final_body: str = ""
    cover_image_prompt: str = ""
    image_prompts: list[str] = Field(default_factory=list)

    hashtags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    character_count: int = 0

    compilation_report: CompilationReport | None = None

    source_opportunity_id: str = ""
    template_id: str = ""
    strategy_id: str = ""
    plan_id: str = ""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    extra: dict[str, Any] = Field(default_factory=dict)
