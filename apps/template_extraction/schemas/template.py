"""桌布主图策略模板，字段与 `TableclothMainImageStrategyTemplate.json` 实例一致。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VisualRules(BaseModel):
    """镜头、元素、文案覆盖与色彩/光线偏好。"""

    preferred_shots: list[str] = Field(default_factory=list)
    required_elements: list[str] = Field(default_factory=list)
    optional_elements: list[str] = Field(default_factory=list)
    text_overlay_level: str = ""
    color_direction: list[str] = Field(default_factory=list)
    lighting_direction: list[str] = Field(default_factory=list)


class CopyRules(BaseModel):
    """标题风格、封面文案长度、推荐与禁用话术。"""

    title_style: list[str] = Field(default_factory=list)
    cover_copy_style: str = ""
    recommended_phrases: list[str] = Field(default_factory=list)
    avoid_phrases: list[str] = Field(default_factory=list)


class SceneRules(BaseModel):
    """是否必须有场景、场景类型与规避场景。"""

    must_have_scene: bool = False
    scene_types: list[str] = Field(default_factory=list)
    avoid_scenes: list[str] = Field(default_factory=list)


class ProductVisibilityRules(BaseModel):
    """桌布可见度下限与纹理/遮挡约束。"""

    tablecloth_visibility_min: float = 0.0
    must_show_pattern_or_texture: bool = False
    avoid_over_occlusion: bool = False


class ClusterFeatures(BaseModel):
    """模板对应簇的主导任务 / 视觉 / 语义标签。"""

    dominant_task_labels: list[str] = Field(default_factory=list)
    dominant_visual_labels: list[str] = Field(default_factory=list)
    dominant_semantic_labels: list[str] = Field(default_factory=list)


class EvaluationMetrics(BaseModel):
    """收藏点击代理、场景可见度等目标阈值。"""

    target_save_like_ratio: float = 0.0
    target_click_proxy_score: float = 0.0
    scene_visibility_score_min: float = 0.0


class DerivationRules(BaseModel):
    """向标题、详情、短视频大纲等衍生的能力与提示风格。"""

    can_extend_to: list[str] = Field(default_factory=list)
    prompt_style: str = ""


class TableclothMainImageStrategyTemplate(BaseModel):
    """可被 Visual / 策划 Agent 消费的桌布主图策略模板 JSON 结构。"""

    template_id: str
    template_name: str
    template_version: str
    template_goal: str
    fit_platform: list[str] = Field(default_factory=list)
    fit_category: list[str] = Field(default_factory=list)
    fit_scenarios: list[str] = Field(default_factory=list)
    fit_styles: list[str] = Field(default_factory=list)
    fit_price_band: list[str] = Field(default_factory=list)
    core_user_motive: list[str] = Field(default_factory=list)
    hook_mechanism: list[str] = Field(default_factory=list)
    cover_role: str
    image_sequence_pattern: list[str] = Field(default_factory=list)
    visual_rules: VisualRules
    copy_rules: CopyRules
    scene_rules: SceneRules
    product_visibility_rules: ProductVisibilityRules
    risk_rules: list[str] = Field(default_factory=list)
    best_for: list[str] = Field(default_factory=list)
    avoid_when: list[str] = Field(default_factory=list)
    seed_examples: list[str] = Field(default_factory=list)
    cluster_features: ClusterFeatures
    evaluation_metrics: EvaluationMetrics
    derivation_rules: DerivationRules
