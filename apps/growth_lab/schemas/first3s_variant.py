"""First3sVariant — 前3秒裂变版本对象。

围绕短视频前3秒做爆款拆解、钩子编译、混剪计划和口播脚本生成。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HookPattern(BaseModel):
    """钩子模式——从爆款视频中提取的前3秒结构化模式。"""

    pattern_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    hook_type: Literal[
        "question", "shock", "contrast", "pain_point",
        "benefit", "curiosity", "authority", "social_proof",
        "urgency", "storytelling",
    ] = "contrast"
    conflict_type: str = ""
    visual_contrast: str = ""
    opening_sentence_pattern: str = ""
    suitable_platforms: list[str] = Field(default_factory=list)
    ai_suitability: Literal["ai_only", "live_only", "mixed", "any"] = "any"
    source_video_ids: list[str] = Field(default_factory=list)
    effectiveness_score: float | None = None


class HookScript(BaseModel):
    """口播/字幕脚本——前3秒的文案层。"""

    script_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    hook_pattern_id: str = ""
    opening_line: str = ""
    supporting_line: str = ""
    cta_line: str = ""
    tone: str = ""
    platform: str = ""
    duration_hint_seconds: float = 3.0


class ClipAssemblyPlan(BaseModel):
    """混剪计划——描述如何组装前3秒视频素材。"""

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    segments: list[dict[str, Any]] = Field(default_factory=list)
    transition_style: str = "cut"
    bgm_suggestion: str = ""
    subtitle_style: str = ""
    total_duration_seconds: float = 3.0
    notes: str = ""


class First3sVariant(BaseModel):
    """前3秒裂变版本——First 3s Lab 的核心产出对象。"""

    variant_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_selling_point_id: str = ""
    source_video_ids: list[str] = Field(default_factory=list)
    source_opportunity_id: str = ""

    platform: str = ""

    key_hook_type: str = ""
    key_conflict_type: str = ""
    hook_script: HookScript | None = None
    hook_pattern: HookPattern | None = None
    clip_assembly_plan: ClipAssemblyPlan | None = None
    pattern_refs: list[str] = Field(default_factory=list)

    expected_goal: str = ""
    quality_score: float | None = None

    # B2B 上下文
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""

    status: Literal[
        "draft", "scripted", "assembled", "selected",
        "in_test", "archived",
    ] = "draft"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
