"""标注后的小红书笔记。"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from apps.template_extraction.schemas.labels import LabelResult


class XHSNoteLabeled(BaseModel):
    """四层标签与标注元数据。"""

    note_id: str
    cover_task_labels: list[LabelResult] = Field(default_factory=list)
    gallery_task_labels: list[LabelResult] = Field(default_factory=list)
    visual_structure_labels: list[LabelResult] = Field(default_factory=list)
    business_semantic_labels: list[LabelResult] = Field(default_factory=list)
    risk_labels: list[LabelResult] = Field(default_factory=list)
    labeler_version: str = "v1"
    labeled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
