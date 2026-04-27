"""PromptSpec — 视觉策略最终落到生图模型的 Prompt 规格。

承接 docs/SOP_to_content_plan.md 第 6.7 节。
MVP 仅生成中文 positive / negative，预留英文与 workflow_json。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PromptProvider = Literal[
    "midjourney",
    "comfyui",
    "sdxl",
    "flux",
    "jimeng",
    "tongyi",
    "gemini",
    "wan25",
    "seedream",
]


class PromptGenerationParams(BaseModel):
    width: int = 1024
    height: int = 1024
    steps: int = 30
    cfg_scale: float = 7.0
    seed: int | None = None


class PromptSpec(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    creative_brief_id: str = ""

    provider: PromptProvider = "comfyui"

    positive_prompt_zh: str = ""
    negative_prompt_zh: str = ""
    positive_prompt_en: str = ""
    negative_prompt_en: str = ""

    generation_params: PromptGenerationParams = Field(default_factory=PromptGenerationParams)
    workflow_json: dict[str, Any] = Field(default_factory=dict)

    field_provenance: dict[str, str] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
