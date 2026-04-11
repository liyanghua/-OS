"""ImageExecutionBrief: 单张图位的结构化执行指令（独立 schema）。

从 AssetBundle.image_execution_briefs (list[dict]) 升级为强类型模型，
支持完整追溯链和前端对象化渲染。
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ImageExecutionBrief(BaseModel):
    """单张图位的结构化执行指令。"""

    brief_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    slot_index: int = 0
    opportunity_id: str = ""
    plan_id: str = ""
    strategy_id: str = ""
    template_id: str = ""

    role: str = ""
    intent: str = ""
    subject: str = ""
    composition: str = ""
    visual_brief: str = ""
    copy_hints: str = ""
    props: list[str] = Field(default_factory=list)
    text_overlay: str = ""
    color_mood: str = ""
    avoid_items: list[str] = Field(default_factory=list)

    status: Literal["draft", "approved", "locked", "regenerating"] = "draft"
