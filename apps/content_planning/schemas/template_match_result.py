"""模板匹配结构化结果，用于 content_planning 链路。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateMatchEntry(BaseModel):
    """单个模板匹配条目。"""

    template_id: str = ""
    template_name: str = ""
    score: float = 0.0
    reason: str = ""
    matched_dimensions: dict[str, float] | None = None


class TemplateMatchResult(BaseModel):
    """结构化的模板匹配结果，含回溯字段与 top-N 候选。"""

    opportunity_id: str = ""
    brief_id: str = ""
    primary_template: TemplateMatchEntry = Field(default_factory=TemplateMatchEntry)
    secondary_templates: list[TemplateMatchEntry] = Field(default_factory=list)
    rejected_templates: list[TemplateMatchEntry] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
