"""四层标签枚举与标注结果模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CoverTaskLabel(str, Enum):
    """首图（封面）任务标签。"""

    hook_click = "hook_click"
    scene_seed = "scene_seed"
    style_anchor = "style_anchor"
    texture_detail = "texture_detail"
    feature_explain = "feature_explain"
    price_value = "price_value"
    gift_event = "gift_event"
    set_combo = "set_combo"
    before_after = "before_after"
    shopping_guide = "shopping_guide"


class GalleryTaskLabel(str, Enum):
    """图组任务标签。"""

    cover_hook = "cover_hook"
    style_expand = "style_expand"
    texture_expand = "texture_expand"
    usage_expand = "usage_expand"
    guide_expand = "guide_expand"


class VisualStructureLabel(str, Enum):
    """视觉结构标签（镜头、构图、主体、桌布露出、文案、色彩与光）。"""

    shot_topdown = "shot_topdown"
    shot_angled = "shot_angled"
    shot_closeup = "shot_closeup"
    shot_wide_scene = "shot_wide_scene"
    composition_centered = "composition_centered"
    composition_diagonal = "composition_diagonal"
    composition_layered = "composition_layered"
    composition_dense = "composition_dense"
    composition_minimal = "composition_minimal"
    has_tablecloth_main = "has_tablecloth_main"
    has_tableware = "has_tableware"
    has_food = "has_food"
    has_flower_vase = "has_flower_vase"
    has_candle = "has_candle"
    has_hand_only = "has_hand_only"
    has_people = "has_people"
    has_chair_or_room_bg = "has_chair_or_room_bg"
    has_gift_box = "has_gift_box"
    has_festival_props = "has_festival_props"
    cloth_full_spread = "cloth_full_spread"
    cloth_partial_visible = "cloth_partial_visible"
    cloth_texture_emphasis = "cloth_texture_emphasis"
    cloth_pattern_emphasis = "cloth_pattern_emphasis"
    cloth_edge_emphasis = "cloth_edge_emphasis"
    cloth_with_other_products = "cloth_with_other_products"
    text_none = "text_none"
    text_light = "text_light"
    text_medium = "text_medium"
    text_heavy = "text_heavy"
    text_style_label = "text_style_label"
    text_price_label = "text_price_label"
    text_transformation_claim = "text_transformation_claim"
    text_scene_claim = "text_scene_claim"
    palette_warm = "palette_warm"
    palette_cool = "palette_cool"
    palette_neutral = "palette_neutral"
    palette_cream = "palette_cream"
    palette_french_vintage = "palette_french_vintage"
    palette_mori = "palette_mori"
    palette_festival_red_green = "palette_festival_red_green"
    lighting_soft = "lighting_soft"
    lighting_natural = "lighting_natural"
    lighting_dramatic = "lighting_dramatic"


class BusinessSemanticLabel(str, Enum):
    """经营语义（命题）标签。"""

    mood_daily_healing = "mood_daily_healing"
    mood_refined_life = "mood_refined_life"
    mood_brunch_afternoontea = "mood_brunch_afternoontea"
    mood_friends_gathering = "mood_friends_gathering"
    mood_festival_setup = "mood_festival_setup"
    mood_anniversary = "mood_anniversary"
    mood_low_cost_upgrade = "mood_low_cost_upgrade"
    mood_small_space_upgrade = "mood_small_space_upgrade"
    mood_photo_friendly = "mood_photo_friendly"
    mood_style_identity = "mood_style_identity"
    mood_giftable = "mood_giftable"
    mood_practical_value = "mood_practical_value"


class RiskLabel(str, Enum):
    """风险与边界标签。"""

    risk_too_generic = "risk_too_generic"
    risk_no_product_focus = "risk_no_product_focus"
    risk_overstyled_low_sellability = "risk_overstyled_low_sellability"
    risk_text_too_ad_like = "risk_text_too_ad_like"
    risk_scene_not_reproducible = "risk_scene_not_reproducible"
    risk_holiday_only = "risk_holiday_only"
    risk_style_too_niche = "risk_style_too_niche"
    risk_cloth_not_visible_enough = "risk_cloth_not_visible_enough"


class LabelResult(BaseModel):
    """单条标签的标注结果（置信度、证据与标注模式）。"""

    label_id: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_snippet: str = ""
    labeler_mode: str = Field(
        default="rule",
        description='标注模式：如 "rule"、"vlm"、"ensemble"。',
    )
    human_override: bool | None = None
