"""CategoryLens / 类目透视引擎的一等公民对象。

CategoryLens 是"看一个类目"的框架：包含该类目的人群、场景、痛点、
信任障碍、商品特征词库、内容模式、用户话术→商品特征映射、VLM 提示
词片段、打分权重等。它驱动 VLM 图片洞察、文本统计抽取、机会卡装配。

LensInsightBundle 是一次透视运行的产物，承载 Category.md "五层机会卡
模型" 的结构化数据，作为 compiler 的输入。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UserExpressionMap(BaseModel):
    """用户话术 ↔ 商品特征 ↔ 需要拍什么镜头 的三元映射。

    对应 Category.md 维度 5「商品技术点」和维度 7「证据强度」。
    """

    user_phrase: str
    product_features: list[str] = Field(default_factory=list)
    proof_shots: list[str] = Field(default_factory=list)


class PriceBand(BaseModel):
    """类目价格带 + 对应策略（Category.md 维度 6）。"""

    band: str
    range_cny: list[float] = Field(default_factory=list)
    user_mindset: str = ""
    strategy: str = ""


class LensScoringWeights(BaseModel):
    """机会卡五维打分权重。按类目不同（假发重 pain/trust_gap，桌布重 scene/style）。

    所有权重之和建议为 1.0；compiler 会做归一化以容忍配置不一致。
    """

    pain_score: float = 0.20
    heat_score: float = 0.20
    trust_gap_score: float = 0.15
    product_fit_score: float = 0.20
    execution_score: float = 0.10
    competition_gap_score: float = 0.05
    scene_heat_score: float = 0.00
    style_trend_score: float = 0.00


class VisualPromptHints(BaseModel):
    """类目感知的 VLM prompt 片段。

    注入到 visual_analyzer._SYSTEM_PROMPT_TEMPLATE 动态渲染。
    """

    focus: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    people_state_taxonomy: list[str] = Field(default_factory=list)
    trust_signal_taxonomy: list[str] = Field(default_factory=list)
    content_format_taxonomy: list[str] = Field(default_factory=list)
    sample_strategy: dict = Field(default_factory=dict)


class TextLexicons(BaseModel):
    """类目文本统计词库。

    signal_extractor 按 lens 注入时优先使用此处的词库，未配置时回退到
    signal_extractor 内置桌布向词库。
    """

    pain_words: list[str] = Field(default_factory=list)
    emotion_words: list[str] = Field(default_factory=list)
    trust_barrier_words: list[str] = Field(default_factory=list)
    scene_words: dict[str, list[str]] = Field(default_factory=dict)
    style_words: dict[str, list[str]] = Field(default_factory=dict)
    audience_words: dict[str, list[str]] = Field(default_factory=dict)
    product_feature_words: dict[str, list[str]] = Field(default_factory=dict)
    content_pattern_words: dict[str, list[str]] = Field(default_factory=dict)
    comment_question_words: list[str] = Field(default_factory=list)
    comment_trust_barrier_words: list[str] = Field(default_factory=list)


class CategoryLens(BaseModel):
    """类目透镜配置。

    对应 docs/knowledge_base/Category.md 第六节「类目透镜」。
    每个类目一份 YAML，放在 ``config/category_lenses/<lens_id>.yaml``。
    """

    lens_id: str
    category_cn: str
    version: str = "1.0.0"
    core_consumption_logic: str = ""
    keyword_aliases: list[str] = Field(default_factory=list)
    primary_user_jobs: list[str] = Field(default_factory=list)
    key_pain_dimensions: list[str] = Field(default_factory=list)
    trust_barriers: list[str] = Field(default_factory=list)
    product_feature_taxonomy: list[str] = Field(default_factory=list)
    content_patterns: list[str] = Field(default_factory=list)
    audience_personas: list[str] = Field(default_factory=list)
    scene_tasks: list[str] = Field(default_factory=list)
    price_bands: list[PriceBand] = Field(default_factory=list)
    visual_prompt_hints: VisualPromptHints = Field(default_factory=VisualPromptHints)
    text_lexicons: TextLexicons = Field(default_factory=TextLexicons)
    user_expression_map: list[UserExpressionMap] = Field(default_factory=list)
    scoring_weights: LensScoringWeights = Field(default_factory=LensScoringWeights)
    linked_prompt_profile: str | None = None


# ── LensInsightBundle: 透视运行产物 ─────────────────────────────────


class Layer1Signals(BaseModel):
    """第 1 层：内容信号层 —— Category.md 第 451 节。"""

    hot_keywords: list[dict] = Field(default_factory=list)
    note_patterns: list[str] = Field(default_factory=list)
    comment_signals: list[str] = Field(default_factory=list)
    emotion_words: list[str] = Field(default_factory=list)
    scene_words: list[str] = Field(default_factory=list)
    trust_barrier_hits: list[str] = Field(default_factory=list)
    visual_insight_summary: dict = Field(default_factory=dict)


class UserJob(BaseModel):
    """第 3 层：用户任务层 —— Category.md 第 488 节。"""

    who: str = ""
    when: str = ""
    problem: str = ""
    desired_outcome: str = ""
    current_alternative: str = ""
    frustration: str = ""


class ProductMappingItem(BaseModel):
    """第 4 层：商品映射层 —— Category.md 第 521 节。"""

    user_need: str = ""
    product_features: list[str] = Field(default_factory=list)
    sku_actions: list[str] = Field(default_factory=list)
    detail_page_actions: list[str] = Field(default_factory=list)


class ContentExecutionItem(BaseModel):
    """第 5 层：内容执行层 —— Category.md 第 545 节。"""

    content_angle: str = ""
    hooks: list[str] = Field(default_factory=list)
    script_structure: list[str] = Field(default_factory=list)
    required_assets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)


class EvidenceScore(BaseModel):
    """机会卡五维证据分（+ competition_gap, total）。"""

    heat: float = 0.0
    pain: float = 0.0
    trust_gap: float = 0.0
    product_fit: float = 0.0
    execution: float = 0.0
    competition_gap: float = 0.0
    total: float = 0.0


class RecommendedAction(BaseModel):
    """机会卡推荐动作。"""

    decision: Literal["进入测试", "补充证据", "暂缓"] = "补充证据"
    next_steps: list[str] = Field(default_factory=list)


class LensInsightBundle(BaseModel):
    """Category Lens Engine 单次透视运行的产物。"""

    lens_id: str
    lens_version: str
    source_note_ids: list[str] = Field(default_factory=list)
    layer1_signals: Layer1Signals = Field(default_factory=Layer1Signals)
    layer2_ontology: dict = Field(default_factory=dict)
    layer3_user_jobs: list[UserJob] = Field(default_factory=list)
    layer4_product_mapping: list[ProductMappingItem] = Field(default_factory=list)
    layer5_content_execution: list[ContentExecutionItem] = Field(default_factory=list)
    evidence_score: EvidenceScore = Field(default_factory=EvidenceScore)
    recommended_action: RecommendedAction = Field(default_factory=RecommendedAction)


__all__ = [
    "UserExpressionMap",
    "PriceBand",
    "LensScoringWeights",
    "VisualPromptHints",
    "TextLexicons",
    "CategoryLens",
    "Layer1Signals",
    "UserJob",
    "ProductMappingItem",
    "ContentExecutionItem",
    "EvidenceScore",
    "RecommendedAction",
    "LensInsightBundle",
]
