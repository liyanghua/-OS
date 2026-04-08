"""策划链路血缘追踪：记录每个策划对象的来源、版本和派生关系。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pydantic import BaseModel, Field


class PlanLineage(BaseModel):
    """贯穿策划编译链的血缘对象，挂载在 Brief/Strategy/Plan/GenerationResult 上。"""

    pipeline_run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_note_ids: list[str] = Field(default_factory=list)
    opportunity_id: str = ""
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""
    review_id: str | None = None
    brief_id: str = ""
    template_id: str = ""
    strategy_id: str = ""
    plan_id: str = ""
    parent_version_id: str | None = None
    derived_from_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
