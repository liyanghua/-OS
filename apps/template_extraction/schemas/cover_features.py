"""封面侧多视角特征（图像 A、文本 B、标签 C），供封面原型聚类等使用。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoverFeaturePack(BaseModel):
    """单条笔记封面图像、规则文本与 multi-hot 标签向量。"""

    img_embedding_cover: list[float] | None = None
    dominant_color_vector: list[float] | None = None
    brightness_score: float = 0.0
    contrast_score: float = 0.0
    text_area_ratio: float = 0.0
    object_count_estimate: float = 0.0
    tablecloth_area_ratio: float = 0.0
    food_area_ratio: float = 0.0
    tableware_area_ratio: float = 0.0
    festival_prop_ratio: float = 0.0
    is_topdown: bool = False
    is_closeup: bool = False
    is_full_table_scene: bool = False
    is_room_context: bool = False
    is_texture_focused: bool = False
    is_style_focused: bool = False
    has_food_visible: bool = False
    has_flower_vase_visible: bool = False
    has_tableware_visible: bool = False
    has_festival_element_visible: bool = False
    title_embedding: list[float] | None = None
    title_keyword_vector: list[float] | None = None
    body_intro_embedding: list[float] | None = None
    kw_style: bool = False
    kw_scene: bool = False
    kw_price: bool = False
    kw_event: bool = False
    kw_upgrade: bool = False
    kw_gift: bool = False
    kw_aesthetic: bool = False
    task_label_vector: list[float] = Field(default_factory=list)
    visual_label_vector: list[float] = Field(default_factory=list)
    semantic_label_vector: list[float] = Field(default_factory=list)
    risk_label_vector: list[float] = Field(default_factory=list)
