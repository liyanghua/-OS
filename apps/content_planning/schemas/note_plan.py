"""新笔记策划：标题 + 正文 + 图片三维策划方案。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from apps.template_extraction.schemas.agent_plan import MainImagePlan


class TitlePlan(BaseModel):
    """标题策划方案。"""

    title_axes: list[str] = Field(default_factory=list)
    candidate_titles: list[str] = Field(default_factory=list)
    do_not_use_phrases: list[str] = Field(default_factory=list)


class BodyPlan(BaseModel):
    """正文策划方案。"""

    opening_hook: str | None = None
    body_outline: list[str] = Field(default_factory=list)
    cta_direction: str | None = None
    tone_notes: list[str] = Field(default_factory=list)


class NewNotePlan(BaseModel):
    """完整的新笔记策划对象，整合标题 / 正文 / 图片三维策划。"""

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    brief_id: str = ""
    strategy_id: str = ""
    template_id: str = ""
    template_name: str = ""

    note_goal: str | None = None
    target_user: list[str] = Field(default_factory=list)
    target_scene: list[str] = Field(default_factory=list)
    core_selling_point: str | None = None
    theme: str | None = None
    tone_of_voice: str | None = None

    title_plan: TitlePlan = Field(default_factory=TitlePlan)
    body_plan: BodyPlan = Field(default_factory=BodyPlan)
    image_plan: MainImagePlan | None = None

    publish_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
