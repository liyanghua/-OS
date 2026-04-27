"""NotePack — 小红书封面 + 内文图 + 文案的多 slot 策略包。

承接「视觉产线分流 + 小红书封面联动」plan。
xhs_cover 场景下，单个 StrategyCandidate 进入视觉工作台时，需要展开为
封面 (1) + 内文图 (N) + 文案 (headline/body_text) 的整篇笔记策略包。

每个 BodyImageSpec 绑定一个 archetype_dim：
- function_demo / scene / before_after / ingredient / lifestyle / texture
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from apps.growth_lab.schemas.prompt_spec import PromptSpec


ArchetypeDim = Literal[
    "cover",
    "function_demo",
    "scene",
    "before_after",
    "ingredient",
    "lifestyle",
    "texture",
]


class BodyImageSpec(BaseModel):
    slot_id: str = ""
    archetype_dim: ArchetypeDim = "function_demo"
    prompt_spec: PromptSpec = Field(default_factory=PromptSpec)
    rationale: str = ""
    rule_refs: list[str] = Field(default_factory=list)


class CopywritingPack(BaseModel):
    headline: str = ""
    body_text: str = ""
    hashtags: list[str] = Field(default_factory=list)
    field_source: dict[str, str] = Field(default_factory=dict)


class NotePack(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    candidate_id: str = ""
    creative_brief_id: str = ""
    scene: str = "xhs_cover"

    cover: PromptSpec = Field(default_factory=PromptSpec)
    cover_rule_refs: list[str] = Field(default_factory=list)
    body: list[BodyImageSpec] = Field(default_factory=list)
    copy: CopywritingPack = Field(default_factory=CopywritingPack)

    field_provenance: dict[str, dict[str, str]] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
