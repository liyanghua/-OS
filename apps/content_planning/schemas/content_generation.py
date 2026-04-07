"""LLM 内容生成结果：标题 / 正文 / 图片执行指令。"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class TitleCandidate(BaseModel):
    """单条标题候选。"""

    title_text: str = ""
    axis: str = ""
    rationale: str = ""


class TitleGenerationResult(BaseModel):
    """标题生成结果。"""

    plan_id: str = ""
    opportunity_id: str = ""
    brief_id: str = ""
    strategy_id: str = ""
    template_id: str = ""
    titles: list[TitleCandidate] = Field(default_factory=list)
    mode: str = "rule"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BodyGenerationResult(BaseModel):
    """正文生成结果。"""

    plan_id: str = ""
    opportunity_id: str = ""
    brief_id: str = ""
    strategy_id: str = ""
    template_id: str = ""
    opening_hook: str = ""
    body_outline: list[str] = Field(default_factory=list)
    body_draft: str = ""
    cta_text: str = ""
    tone_check: str = ""
    mode: str = "rule"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ImageSlotBrief(BaseModel):
    """单张图片的详细执行指令。"""

    slot_index: int = 0
    role: str = ""
    subject: str = ""
    composition: str = ""
    props: list[str] = Field(default_factory=list)
    text_overlay: str = ""
    color_mood: str = ""
    avoid_items: list[str] = Field(default_factory=list)


class ImageBriefGenerationResult(BaseModel):
    """图片执行指令生成结果。"""

    plan_id: str = ""
    opportunity_id: str = ""
    brief_id: str = ""
    strategy_id: str = ""
    template_id: str = ""
    slot_briefs: list[ImageSlotBrief] = Field(default_factory=list)
    mode: str = "rule"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
