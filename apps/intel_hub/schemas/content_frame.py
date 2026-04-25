"""笔记内容解析帧与经营信号帧。

Layer 1 输出: NoteContentFrame — 笔记多模态结构化
Layer 2 输出: BusinessSignalFrame — 经营信号字段级抽取
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommentFrame(BaseModel):
    """单条评论结构化。"""
    comment_id: str = ""
    user_name: str = ""
    comment_text: str = ""
    like_count: int = 0
    reply_count: int = 0
    sentiment_hint: str = ""
    signal_type_hint: str = ""
    parent_comment_id: str | None = None


class NoteContentFrame(BaseModel):
    """Layer 1: 笔记内容对象化（从原始笔记拆出的标准结构）。"""
    note_id: str
    note_url: str = ""
    author_id: str = ""
    author_name: str = ""
    published_at: str = ""
    crawled_at: str = ""
    platform: str = "xiaohongshu"
    source_type: str = "mediacrawler_xhs"

    title_text: str = ""
    body_text: str = ""
    tag_list: list[str] = Field(default_factory=list)

    like_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    share_count: int = 0

    image_count: int = 0
    cover_image: str = ""
    image_list: list[str] = Field(default_factory=list)

    comments: list[CommentFrame] = Field(default_factory=list)
    top_comments: list[CommentFrame] = Field(default_factory=list)
    neg_comments: list[CommentFrame] = Field(default_factory=list)


class BusinessSignalFrame(BaseModel):
    """Layer 2: 经营信号字段级抽取（从 NoteContentFrame 中提炼）。"""
    note_id: str

    # 标题信号
    title_hook_types: list[str] = Field(default_factory=list)
    title_scene_signals: list[str] = Field(default_factory=list)
    title_style_signals: list[str] = Field(default_factory=list)
    title_result_signals: list[str] = Field(default_factory=list)
    title_problem_signals: list[str] = Field(default_factory=list)

    # 正文信号
    body_scene_signals: list[str] = Field(default_factory=list)
    body_audience_signals: list[str] = Field(default_factory=list)
    body_style_signals: list[str] = Field(default_factory=list)
    body_material_signals: list[str] = Field(default_factory=list)
    body_size_signals: list[str] = Field(default_factory=list)
    body_price_signals: list[str] = Field(default_factory=list)
    body_selling_points: list[str] = Field(default_factory=list)
    body_constraints: list[str] = Field(default_factory=list)
    body_pain_points: list[str] = Field(default_factory=list)
    body_risk_signals: list[str] = Field(default_factory=list)
    body_comparison_signals: list[str] = Field(default_factory=list)

    # 标签信号
    topic_pool_signals: list[str] = Field(default_factory=list)
    distribution_semantics: list[str] = Field(default_factory=list)
    trend_tags: list[str] = Field(default_factory=list)

    # 图片视觉信号
    visual_style_signals: list[str] = Field(default_factory=list)
    visual_scene_signals: list[str] = Field(default_factory=list)
    visual_composition_types: list[str] = Field(default_factory=list)
    visual_color_palette: list[str] = Field(default_factory=list)
    visual_texture_signals: list[str] = Field(default_factory=list)
    visual_expression_patterns: list[str] = Field(default_factory=list)

    # V2.1 类目感知视觉字段（由 visual_analyzer 按 CategoryLens 填充）
    visual_people_state: list[str] = Field(default_factory=list)
    visual_trust_signals: list[str] = Field(default_factory=list)
    visual_trust_risk_flags: list[str] = Field(default_factory=list)
    visual_content_formats: list[str] = Field(default_factory=list)
    visual_product_features: list[str] = Field(default_factory=list)
    visual_insight_notes: str = ""

    # 评论信号
    purchase_intent_signals: list[str] = Field(default_factory=list)
    positive_feedback_signals: list[str] = Field(default_factory=list)
    negative_feedback_signals: list[str] = Field(default_factory=list)
    question_signals: list[str] = Field(default_factory=list)
    comparison_signals: list[str] = Field(default_factory=list)
    unmet_need_signals: list[str] = Field(default_factory=list)
    audience_signals_from_comments: list[str] = Field(default_factory=list)
    trust_gap_signals: list[str] = Field(default_factory=list)

    # 经营信号标准化（归一后）
    normalized_scene_refs: list[str] = Field(default_factory=list)
    normalized_style_refs: list[str] = Field(default_factory=list)
    normalized_need_refs: list[str] = Field(default_factory=list)
    normalized_risk_refs: list[str] = Field(default_factory=list)
    normalized_content_refs: list[str] = Field(default_factory=list)
    normalized_visual_refs: list[str] = Field(default_factory=list)
    normalized_material_refs: list[str] = Field(default_factory=list)
    normalized_audience_refs: list[str] = Field(default_factory=list)
    buying_barrier_refs: list[str] = Field(default_factory=list)
    value_proposition_refs: list[str] = Field(default_factory=list)

    # V2.1 类目透视引擎填充
    lens_id: str | None = None
    body_content_pattern_signals: list[str] = Field(default_factory=list)
    body_user_expression_hits: list[str] = Field(default_factory=list)
    body_emotion_signals: list[str] = Field(default_factory=list)
    comment_classification_counts: dict[str, int] = Field(default_factory=dict)
    comment_trust_barrier_signals: list[str] = Field(default_factory=list)
