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
    status: Literal["draft", "generating", "generated", "reviewed", "approved", "failed"] = "draft"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EditSession(BaseModel):
    """当前编辑会话——驱动右栏 AI 控制台的上下文。"""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    plan_id: str = ""
    active_node_id: str = ""
    selected_context: dict[str, Any] = Field(default_factory=dict)
    active_constraints: list[str] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
