"""改写策略：将 OpportunityBrief + 模板匹配结果翻译为可执行的内容改造方向。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class RewriteStrategy(BaseModel):
    """从"用哪个模板"到"具体怎么改"的关键翻译层。"""

    strategy_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    brief_id: str = ""
    template_id: str = ""

    positioning_statement: str = ""
    new_hook: str = ""
    new_angle: str = ""
    tone_of_voice: str = ""

    keep_elements: list[str] = Field(default_factory=list)
    replace_elements: list[str] = Field(default_factory=list)
    enhance_elements: list[str] = Field(default_factory=list)
    avoid_elements: list[str] = Field(default_factory=list)

    title_strategy: list[str] = Field(default_factory=list)
    body_strategy: list[str] = Field(default_factory=list)
    image_strategy: list[str] = Field(default_factory=list)

    differentiation_axis: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
