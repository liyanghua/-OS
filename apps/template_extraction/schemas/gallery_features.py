"""图组侧结构、一致性与互动特征（D、E 及前若干张图 embedding），供图组策略聚类等使用。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GalleryFeaturePack(BaseModel):
    """图组骨架、一致性、功能覆盖与后验互动，及语义标签向量（阶段二聚类）。"""

    img_embedding_top3_mean: list[float] | None = None
    image_count: int = 0
    cover_role: str = ""
    role_seq_top5: list[str] = Field(default_factory=list)
    style_consistency_score: float = 0.0
    color_consistency_score: float = 0.0
    scene_consistency_score: float = 0.0
    text_density_variance: float = 0.0
    has_scene_image: bool = False
    has_texture_closeup: bool = False
    has_buying_guide: bool = False
    has_before_after: bool = False
    has_set_combo: bool = False
    like_count: int = 0
    save_count: int = 0
    comment_count: int = 0
    engagement_proxy_score: float = 0.0
    save_like_ratio: float = 0.0
    comment_like_ratio: float = 0.0
    semantic_label_vector: list[float] = Field(default_factory=list)
