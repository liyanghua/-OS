"""三维结构化信号 Schema —— 视觉 / 卖点主题 / 场景。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.evidence import XHSEvidenceRef


class VisualSignals(BaseModel):
    """视觉维度信号。"""

    note_id: str = ""
    visual_style_signals: list[str] = Field(default_factory=list)
    visual_scene_signals: list[str] = Field(default_factory=list)
    visual_composition_type: list[str] = Field(default_factory=list)
    visual_color_palette: list[str] = Field(default_factory=list)
    visual_texture_signals: list[str] = Field(default_factory=list)
    visual_feature_highlights: list[str] = Field(default_factory=list)
    visual_expression_pattern: list[str] = Field(default_factory=list)
    visual_misleading_risk: list[str] = Field(default_factory=list)
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
    """卖点主题维度信号。"""

    note_id: str = ""
    selling_point_signals: list[str] = Field(default_factory=list)
    validated_selling_points: list[str] = Field(default_factory=list)
    selling_point_challenges: list[str] = Field(default_factory=list)
    selling_theme_refs: list[str] = Field(default_factory=list)
    purchase_intent_signals: list[str] = Field(default_factory=list)
    trust_gap_signals: list[str] = Field(default_factory=list)
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
    """场景维度信号。"""

    note_id: str = ""
    scene_signals: list[str] = Field(default_factory=list)
    scene_goal_signals: list[str] = Field(default_factory=list)
    scene_constraints: list[str] = Field(default_factory=list)
    scene_style_value_combos: list[str] = Field(default_factory=list)
    audience_signals: list[str] = Field(default_factory=list)
    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any([
            self.scene_signals,
            self.scene_goal_signals,
            self.scene_style_value_combos,
        ])
