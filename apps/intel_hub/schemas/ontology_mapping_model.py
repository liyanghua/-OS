"""本体映射结果 Schema —— 三维信号到 canonical ontology refs 的映射。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.evidence import XHSEvidenceRef


class XHSOntologyMapping(BaseModel):
    """一篇笔记经本体映射后的 canonical refs 集合。"""

    note_id: str = ""
    category_refs: list[str] = Field(default_factory=list)
    scene_refs: list[str] = Field(default_factory=list)
    style_refs: list[str] = Field(default_factory=list)
    need_refs: list[str] = Field(default_factory=list)
    risk_refs: list[str] = Field(default_factory=list)
    audience_refs: list[str] = Field(default_factory=list)
    visual_pattern_refs: list[str] = Field(default_factory=list)
    content_pattern_refs: list[str] = Field(default_factory=list)
    value_proposition_refs: list[str] = Field(default_factory=list)
    source_signal_summary: str | None = None
    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)
