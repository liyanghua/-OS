"""视觉工作台领域模型。

承接 docs/upgradeV2/visual_workspace.md 的设计，
把主图/详情模块/视频镜头/买家秀/竞品对标统一抽象为 ResultNode，
由 Frame 容纳成组，并由 CompilePlan 描述一次完整的"任务装配"。

与已有 MainImageVariant / First3sVariant 共存：
ResultNode.active_variant_id 指向具体子类型的 variant 记录。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── ScriptTemplate：业务专家模板的结构化编码 ───────────────

TemplateCategory = Literal[
    "main_image",
    "detail_module",
    "brand_detail_report",
    "video_shot_list",
    "buyer_show",
    "competitor_deconstruct",
]


class TemplateSlot(BaseModel):
    """模板中的一个槽位——对应最终结果中的一个节点。"""

    index: int = 0
    role: str = ""  # 如 "人群场景直击" / "模块3 特殊材料" / "镜头5 核心卖点响应"
    visual_spec: str = ""
    copy_spec: str = ""
    aspect_ratio: str = "1:1"  # 1:1 / 3:4 / 16:9 / 9:16
    generation_hints: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    # ── 富 prompt（Schema v2 / MD 解析后可用） ──
    positive_prompt_blocks: list[str] = Field(default_factory=list)
    negative_prompt_blocks: list[str] = Field(default_factory=list)
    headline: str = ""
    subheadline: str = ""
    selling_points: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class ScriptTemplate(BaseModel):
    """一套业务专家策划模板。

    支持两类源文件：
    - 精简模板：apps/growth_lab/templates_lib/*.yaml
    - 完整专家资产（Schema v2 / 专家 MD）：assets/**
    """

    template_id: str = ""
    category: TemplateCategory = "main_image"
    name: str = ""
    description: str = ""
    slots: list[TemplateSlot] = Field(default_factory=list)
    default_brand_rules: list[str] = Field(default_factory=list)
    yaml_source_path: str = ""
    version: str = "v1"
    # ── 富业务上下文（Schema v2 专用；精简模板则为空） ──
    business_context: dict[str, Any] = Field(default_factory=dict)
    strategy_pack: dict[str, Any] = Field(default_factory=dict)
    global_style: dict[str, Any] = Field(default_factory=dict)
    script_asset: dict[str, Any] = Field(default_factory=dict)
    prompt_compile_spec: dict[str, Any] = Field(default_factory=dict)
    review_spec: dict[str, Any] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)
    source_kind: str = "yaml_simple"  # yaml_simple / yaml_v2 / md_table / md_sections
    extra: dict[str, Any] = Field(default_factory=dict)


# ── IntentContext：任务意图上下文 ────────────────────────


class IntentContext(BaseModel):
    """用户意图——驱动整个编译链路的原始输入。"""

    product_id: str = ""
    product_name: str = ""
    audience: str = ""
    output_types: list[str] = Field(default_factory=list)  # main_image / detail / video / buyer_show
    style_refs: list[str] = Field(default_factory=list)
    scenario_refs: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    requested_counts: dict[str, int] = Field(default_factory=dict)
    # 图像模型偏好：auto / wan25 / gemini / seedream / flux
    model_preference: str = "auto"
    # 溯源
    source_spec_id: str = ""
    source_opportunity_ids: list[str] = Field(default_factory=list)


# ── CompilePlan / Frame / ResultNode / Variant ─────────


class TemplateBinding(BaseModel):
    """模板绑定——一次编译里选用了哪套模板及选用理由。"""

    frame_key: str = ""  # 如 "main_image" / "detail" / "video_shots"
    template_id: str = ""
    binding_reason: str = ""
    locked_fields: list[str] = Field(default_factory=list)
    # 当触发"仅借框架"时，保存按 intent 重参数化后的临时模板快照，便于 UI 溯源
    adapted_template_snapshot: dict[str, Any] | None = None


class CompilePlan(BaseModel):
    """一次完整的视觉编译计划。"""

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    intent: IntentContext = Field(default_factory=IntentContext)
    template_bindings: list[TemplateBinding] = Field(default_factory=list)
    frame_ids: list[str] = Field(default_factory=list)
    generation_rules: dict[str, Any] = Field(default_factory=dict)
    evaluation_rules: dict[str, Any] = Field(default_factory=dict)
    workspace_id: str = ""
    brand_id: str = ""
    status: Literal["draft", "compiling", "compiled", "generating", "ready", "archived"] = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Frame(BaseModel):
    """画布上的组容器——代表一套 script（如主图 5 张）。"""

    frame_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    plan_id: str = ""
    frame_key: str = ""  # main_image / detail / video_shots / buyer_show / competitor
    template_id: str = ""
    title: str = ""
    canvas_x: float = 0.0
    canvas_y: float = 0.0
    layout: Literal["grid", "row", "column"] = "row"
    node_ids: list[str] = Field(default_factory=list)
    status: Literal["draft", "generating", "ready", "approved"] = "draft"


class ExpertAnnotation(BaseModel):
    """节点级专家批注——可注入后续生成。"""

    annotation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str = ""
    annotator: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


ObjectType = Literal["product", "background", "copy", "person", "decoration", "logo"]


class ObjectNode(BaseModel):
    """ResultNode 下的对象——画面里的可寻址元素。

    V1 按模板 role 静态生成一组默认对象（产品/背景/文案/人物/装饰/Logo）。
    `prompt_hint` 在 img2img 局部修改时作为目标描述注入。
    `locked=True` 的对象在提案卡中会被标记为 "跳过" 并拒绝 AI 修改。
    """

    object_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    node_id: str = ""
    type: ObjectType = "decoration"
    label: str = ""
    editable: bool = True
    locked: bool = False
    prompt_hint: str = ""
    order: int = 0
    # v2 runtime 增强
    role: str | None = None  # 如 hero_product / before_area / after_area / title_copy
    semantic_description: str | None = None
    editable_actions: list[str] = Field(default_factory=list)
    bbox: dict[str, float] | None = None  # {x,y,w,h} 归一化 0-1；V1 可选


ResultType = Literal[
    "main_image",
    "detail_module",
    "video_shot",
    "buyer_show",
    "competitor_ref",
]


class Variant(BaseModel):
    """节点下的一个版本分支。"""

    variant_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    node_id: str = ""
    prompt_sent: str = ""
    asset_url: str = ""
    asset_type: Literal["image", "video"] = "image"
    provider: str = ""
    score: float | None = None
    notes: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)
    # 关联旧表（过渡期）
    legacy_main_image_variant_id: str = ""
    legacy_first3s_variant_id: str = ""
    status: Literal["pending", "generating", "done", "failed"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResultNode(BaseModel):
    """一个可编辑的结果节点——工作台的一等公民。"""

    node_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    frame_id: str = ""
    plan_id: str = ""
    slot_index: int = 0
    role: str = ""
    result_type: ResultType = "main_image"
    title: str = ""
    objective: str = ""
    visual_spec: str = ""
    copy_spec: str = ""
    aspect_ratio: str = "1:1"
    # 画布几何
    canvas_x: float = 0.0
    canvas_y: float = 0.0
    width: float = 220.0
    height: float = 220.0
    # 生成产物
    active_variant_id: str = ""
    variant_ids: list[str] = Field(default_factory=list)
    # 溯源
    intent_ref_fields: list[str] = Field(default_factory=list)
    template_slot_ref: str = ""
    brand_rule_refs: list[str] = Field(default_factory=list)
    competitor_ref_ids: list[str] = Field(default_factory=list)
    # 编辑
    expert_annotations: list[ExpertAnnotation] = Field(default_factory=list)
    objects: list[ObjectNode] = Field(default_factory=list)
    status: Literal["draft", "generating", "generated", "reviewed", "approved", "failed"] = "draft"
    # 状态机审计
    status_history: list[dict[str, Any]] = Field(default_factory=list)
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    rule_report: dict[str, Any] = Field(default_factory=dict)
    # v2 runtime 增强
    slot_role: str | None = None      # 结构化的 slot role（pain_contrast / lifestyle / tech_highlight …）
    slot_objective: str | None = None  # 针对 slot_role 的短目标
    direction_summary: str | None = None  # 多轮编辑沉淀的方向摘要
    # 节点自由态扩展字段：竞品拆解结果 / 32 维度清单 / 二创 prompt 缓存等
    extra: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EditSession(BaseModel):
    """当前编辑会话——驱动右栏 AI 控制台的上下文。"""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    plan_id: str = ""
    active_node_id: str = ""
    selected_context: dict[str, Any] = Field(default_factory=dict)
    active_constraints: list[str] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


# ── v2 Runtime：EditContextPack / ResolvedEditReference / ProposalV2 ─────

SelectionMode = Literal["scene", "object", "region", "multi_object"]
NodeType = Literal["main_image", "detail", "video_shots", "buyer_show", "competitor"]
EditStrength = Literal["subtle", "moderate", "strong"]
ProposalStatus = Literal["draft", "confirmed", "running", "done", "failed"]


class RuntimeObjectSummary(BaseModel):
    object_id: str
    type: str
    role: str | None = None
    label: str
    locked: bool = False
    editable_actions: list[str] = Field(default_factory=list)
    semantic_description: str | None = None
    bbox: dict[str, float] | None = None


class RuntimeCopyBlock(BaseModel):
    object_id: str
    role: str | None = None
    label: str
    text: str
    locked: bool = False


class EditIntentContext(BaseModel):
    product_name: str | None = None
    category: str | None = None
    audience: str | None = None
    output_goal: str | None = None
    style_refs: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    raw_prompt: str | None = None


class EditTemplateContext(BaseModel):
    template_id: str | None = None
    template_name: str | None = None
    slot_role: str | None = None
    slot_objective: str | None = None
    adapted_template_snapshot: dict[str, Any] | None = None
    template_constraints: list[str] = Field(default_factory=list)


class EditStrategyContext(BaseModel):
    core_claim: str | None = None
    supporting_claims: list[str] = Field(default_factory=list)
    visual_goal: str | None = None
    copy_goal: str | None = None
    platform_goal: str | None = None
    brand_rules: list[str] = Field(default_factory=list)


class CurrentVariantContext(BaseModel):
    variant_id: str = ""
    image_url: str | None = None
    revision_index: int = 0
    batch_tag: str | None = None
    batch_size: int | None = None


class SelectionContext(BaseModel):
    mode: SelectionMode = "scene"
    selected_object_ids: list[str] = Field(default_factory=list)
    primary_object_id: str | None = None
    secondary_object_ids: list[str] = Field(default_factory=list)
    selected_region: dict[str, Any] | None = None
    anchor_object_id: str | None = None
    selected_labels: list[str] = Field(default_factory=list)
    locked_object_ids: list[str] = Field(default_factory=list)
    editable_object_ids: list[str] = Field(default_factory=list)
    resolution_confidence: float | None = None
    needs_clarification: bool = False


class VisualStateSummary(BaseModel):
    object_summaries: list[RuntimeObjectSummary] = Field(default_factory=list)
    copy_blocks: list[RuntimeCopyBlock] = Field(default_factory=list)
    composition_summary: str | None = None
    salience_summary: str | None = None
    current_direction_summary: str | None = None


class RecentEditHistory(BaseModel):
    last_user_requests: list[str] = Field(default_factory=list)
    last_applied_changes: list[str] = Field(default_factory=list)
    last_proposal_summaries: list[str] = Field(default_factory=list)


class EditContextPack(BaseModel):
    plan_id: str
    frame_id: str
    node_id: str
    node_type: NodeType = "main_image"

    node_title: str | None = None
    node_objective: str | None = None
    node_status: str | None = None

    intent_context: EditIntentContext = Field(default_factory=EditIntentContext)
    template_context: EditTemplateContext = Field(default_factory=EditTemplateContext)
    strategy_context: EditStrategyContext = Field(default_factory=EditStrategyContext)
    current_variant: CurrentVariantContext = Field(default_factory=CurrentVariantContext)
    selection_context: SelectionContext = Field(default_factory=SelectionContext)
    visual_state: VisualStateSummary = Field(default_factory=VisualStateSummary)
    recent_history: RecentEditHistory = Field(default_factory=RecentEditHistory)


class ResolvedEditReference(BaseModel):
    scope: SelectionMode = "scene"
    primary_targets: list[str] = Field(default_factory=list)
    secondary_targets: list[str] = Field(default_factory=list)
    ambiguous_refs: list[str] = Field(default_factory=list)
    resolution_confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str | None = None


class ProposalStepV2(BaseModel):
    action_type: str
    target_object_ids: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    strength: EditStrength = "subtle"
    reason: str | None = None


class ProposalV2(BaseModel):
    summary: str = ""
    interpretation_basis: list[str] = Field(default_factory=list)
    resolved_reference: ResolvedEditReference = Field(default_factory=ResolvedEditReference)
    target_objects: list[str] = Field(default_factory=list)
    locked_objects: list[str] = Field(default_factory=list)
    preserve_rules: list[str] = Field(default_factory=list)
    steps: list[ProposalStepV2] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    keep_slot_role: bool = True
    status: ProposalStatus = "draft"
    # 兼容 v1 渲染：保留旧字段冗余
    prompt_delta: str = ""
    copy_delta: str = ""


# ── Onboarding（新建 plan 的对话式引导） ─────────


class ChatTurn(BaseModel):
    """对话历史的一轮消息（onboarding / agent 通用）。"""

    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""


class OnboardingResult(BaseModel):
    """onboarding_chat 的返回——渐进收集意图直到可以一键编译。"""

    draft_intent: IntentContext = Field(default_factory=IntentContext)
    next_question: str | None = None
    assistant_message: str = ""
    ready_to_compile: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
