"""两阶段聚类中，单条笔记的簇归属与摘要挂载。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClusterSample(BaseModel):
    """封面簇 / 策略簇 ID、代表位、互动代理与簇级摘要文本。"""

    note_id: str
    cover_cluster_id: str | None = None
    strategy_cluster_id: str | None = None
    is_cover_representative: bool = False
    is_strategy_representative: bool = False
    engagement_proxy_score: float = 0.0
    cover_cluster_summary: str = ""
    strategy_cluster_pattern: str = ""
    dominant_title_keywords: list[str] = Field(default_factory=list)
    template_candidate_hint: str = ""
