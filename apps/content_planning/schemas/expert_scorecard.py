"""ExpertScorecard: 8 维专家升级评分卡，决定机会卡是否值得投入内容生产。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scorecard_weights.yaml"
_CONFIG_CACHE: dict[str, Any] | None = None


def _load_weights_config() -> dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _CONFIG_CACHE = yaml.safe_load(f) or {}
    else:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


class ScorecardDimension(BaseModel):
    """单维度评分。"""

    name: str = ""
    label: str = ""
    score: float = 0.0
    weight: float = 0.0
    inverse: bool = False
    evidence_sources: list[str] = Field(default_factory=list)
    explanation: str = ""


class ExpertScorecard(BaseModel):
    """8 维专家评分卡。"""

    scorecard_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    card_id: str = ""
    opportunity_id: str = ""
    project_id: str = ""

    demand_strength: float = 0.0
    differentiation: float = 0.0
    commerce_fit: float = 0.0
    scalability: float = 0.0
    reusability: float = 0.0
    visual_potential: float = 0.0
    video_potential: float = 0.0
    risk_score: float = 0.0

    dimensions: list[ScorecardDimension] = Field(default_factory=list)

    total_score: float = 0.0
    confidence: float = 0.0
    recommendation: Literal["ignore", "observe", "evaluate", "initiate"] = "observe"

    score_reasons: list[str] = Field(default_factory=list)
    blocking_risks: list[str] = Field(default_factory=list)
    upgrade_advice: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def compute_total_score(self) -> float:
        cfg = _load_weights_config()
        dim_cfg = cfg.get("dimensions", {})

        weighted_sum = 0.0
        weight_total = 0.0
        for dim in self.dimensions:
            w = dim.weight or dim_cfg.get(dim.name, {}).get("weight", 0.1)
            s = (1.0 - dim.score) if dim.inverse else dim.score
            weighted_sum += s * w
            weight_total += w

        self.total_score = round(weighted_sum / weight_total, 3) if weight_total > 0 else 0.0
        return self.total_score

    def compute_recommendation(self) -> str:
        cfg = _load_weights_config()
        thresholds = cfg.get("recommendation_thresholds", {})
        t_initiate = thresholds.get("initiate", 0.7)
        t_evaluate = thresholds.get("evaluate", 0.5)
        t_observe = thresholds.get("observe", 0.3)

        if self.total_score >= t_initiate:
            self.recommendation = "initiate"
        elif self.total_score >= t_evaluate:
            self.recommendation = "evaluate"
        elif self.total_score >= t_observe:
            self.recommendation = "observe"
        else:
            self.recommendation = "ignore"
        return self.recommendation

    def sync_dimension_scores(self) -> None:
        """Keep top-level shortcut fields in sync with dimensions list."""
        for dim in self.dimensions:
            if hasattr(self, dim.name):
                setattr(self, dim.name, dim.score)
