"""三维结构化信号 Schema V2 —— 视觉 / 卖点主题 / 场景。

V2 在 V1 基础上新增优先级、评分、分类等结构化字段，
所有新字段均有默认值，向后兼容 V1 使用方。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.evidence import XHSEvidenceRef


class VisualSignals(BaseModel):
    """视觉维度信号 V2。"""

    note_id: str = ""

    # V1 字段
    visual_style_signals: list[str] = Field(default_factory=list)
    visual_scene_signals: list[str] = Field(default_factory=list)
    visual_composition_type: list[str] = Field(default_factory=list)
    visual_color_palette: list[str] = Field(default_factory=list)
    visual_texture_signals: list[str] = Field(default_factory=list)
    visual_feature_highlights: list[str] = Field(default_factory=list)
    visual_expression_pattern: list[str] = Field(default_factory=list)
    visual_misleading_risk: list[str] = Field(default_factory=list)

    # V2 新增: 风格优先级
    primary_style: str | None = None
    secondary_styles: list[str] = Field(default_factory=list)
    style_confidence: float | None = None

    # V2 新增: 构图与信息密度
    hero_image_pattern: str | None = None
    information_density: str | None = None

    # V2 新增: 卖点视觉化缺失
    missing_feature_visualization: list[str] = Field(default_factory=list)

    # V2 新增: 差异化与评分
    visual_differentiation_points: list[str] = Field(default_factory=list)
    click_differentiation_score: float | None = None
    conversion_alignment_score: float | None = None
    visual_risk_score: float | None = None

    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any([
            self.visual_style_signals,
            self.visual_scene_signals,
            self.visual_composition_type,
            self.visual_color_palette,
            self.visual_texture_signals,
            self.visual_feature_highlights,
            self.visual_expression_pattern,
        ])


class SellingThemeSignals(BaseModel):
    """卖点主题维度信号 V2。"""

    note_id: str = ""

    # V1 字段
    selling_point_signals: list[str] = Field(default_factory=list)
    validated_selling_points: list[str] = Field(default_factory=list)
    selling_point_challenges: list[str] = Field(default_factory=list)
    selling_theme_refs: list[str] = Field(default_factory=list)
    purchase_intent_signals: list[str] = Field(default_factory=list)
    trust_gap_signals: list[str] = Field(default_factory=list)

    # V2 新增: 卖点优先级
    primary_selling_points: list[str] = Field(default_factory=list)
    secondary_selling_points: list[str] = Field(default_factory=list)
    selling_point_priority: list[str] = Field(default_factory=list)

    # V2 新增: 卖点分类
    click_oriented_points: list[str] = Field(default_factory=list)
    conversion_oriented_points: list[str] = Field(default_factory=list)
    productizable_points: list[str] = Field(default_factory=list)
    content_only_points: list[str] = Field(default_factory=list)

    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any([
            self.selling_point_signals,
            self.validated_selling_points,
            self.selling_point_challenges,
            self.purchase_intent_signals,
        ])


class SceneSignals(BaseModel):
    """场景维度信号 V2。"""

    note_id: str = ""

    # V1 字段
    scene_signals: list[str] = Field(default_factory=list)
    scene_goal_signals: list[str] = Field(default_factory=list)
    scene_constraints: list[str] = Field(default_factory=list)
    scene_style_value_combos: list[str] = Field(default_factory=list)
    audience_signals: list[str] = Field(default_factory=list)

    # V2 新增: 隐式场景
    inferred_scene_signals: list[str] = Field(default_factory=list)
    inference_confidence: float | None = None

    # V2 新增: 机会提示
    scene_opportunity_hints: list[str] = Field(default_factory=list)

    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any([
            self.scene_signals,
            self.scene_goal_signals,
            self.scene_style_value_combos,
        ])
