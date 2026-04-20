下面给你一版**直接贴合你现有 Growth Lab** 的升级稿。
目标不是推翻重来，而是在你已经跑通的：

* Intent → CompilePlan → ResultNode → ObjectNode → Variant
* `/suggest-actions` / `/propose-edit` / `/apply-proposal`
* workspace.html 三栏 + 时间线 + Gate + 导出

基础上，补齐 **“对象对话编辑 runtime”** 这一层。

我按 4 部分给你：

1. `EditContextPack Schema`
2. `propose-edit` 新接口契约
3. 前端右栏重构方案
4. AI-coding Prompt

---

# 一、升级目标

这次升级只解决一件最核心的事：

> 让用户在画布中选中对象/区域后，右侧 Agent 能真正理解“我现在正在改谁、为什么改、受什么约束、该怎么改”，并输出稳定、可执行、可追踪的提案。

所以这不是“再做更多页面”，而是要把你现有的：

* 结构树
* 画布选中
* 右栏 Copilot
* Proposal Card

真正通过一个统一的 runtime 编辑上下文串起来。

---

# 二、EditContextPack Schema

这是本次升级的核心对象。
建议放在：

* `apps/growth_lab/schemas/visual_workspace.py`
* 或拆一个 `workspace_runtime.py`

---

## 2.1 顶层定义

```python
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


SelectionMode = Literal["scene", "object", "region", "multi_object"]
NodeType = Literal["main_image", "detail", "video_shots", "buyer_show", "competitor"]
EditStrength = Literal["subtle", "moderate", "strong"]
ProposalStatus = Literal["draft", "confirmed", "running", "done", "failed"]
```

---

## 2.2 轻量对象摘要

```python
class RuntimeObjectSummary(BaseModel):
    object_id: str
    type: str
    role: str | None = None
    label: str
    locked: bool = False
    editable_actions: list[str] = Field(default_factory=list)
    semantic_description: str | None = None
    bbox: dict[str, float] | None = None
```

---

## 2.3 文案块摘要

```python
class RuntimeCopyBlock(BaseModel):
    object_id: str
    role: str | None = None
    label: str
    text: str
    locked: bool = False
```

---

## 2.4 意图上下文

```python
class EditIntentContext(BaseModel):
    product_name: str | None = None
    category: str | None = None
    audience: str | None = None
    output_goal: str | None = None
    style_refs: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    raw_prompt: str | None = None
```

---

## 2.5 模板上下文

```python
class EditTemplateContext(BaseModel):
    template_id: str | None = None
    template_name: str | None = None
    slot_role: str | None = None
    slot_objective: str | None = None
    adapted_template_snapshot: dict[str, Any] | None = None
    template_constraints: list[str] = Field(default_factory=list)
```

---

## 2.6 策略上下文

```python
class EditStrategyContext(BaseModel):
    core_claim: str | None = None
    supporting_claims: list[str] = Field(default_factory=list)
    visual_goal: str | None = None
    copy_goal: str | None = None
    platform_goal: str | None = None
    brand_rules: list[str] = Field(default_factory=list)
```

---

## 2.7 当前版本上下文

```python
class CurrentVariantContext(BaseModel):
    variant_id: str
    image_url: str | None = None
    revision_index: int = 0
    batch_tag: str | None = None
    batch_size: int | None = None
```

---

## 2.8 选中上下文

这是最关键的一层。

```python
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
```

---

## 2.9 当前视觉状态摘要

```python
class VisualStateSummary(BaseModel):
    object_summaries: list[RuntimeObjectSummary] = Field(default_factory=list)
    copy_blocks: list[RuntimeCopyBlock] = Field(default_factory=list)

    composition_summary: str | None = None
    salience_summary: str | None = None
    current_direction_summary: str | None = None
```

---

## 2.10 最近历史

```python
class RecentEditHistory(BaseModel):
    last_user_requests: list[str] = Field(default_factory=list)
    last_applied_changes: list[str] = Field(default_factory=list)
    last_proposal_summaries: list[str] = Field(default_factory=list)
```

---

## 2.11 顶层 EditContextPack

```python
class EditContextPack(BaseModel):
    plan_id: str
    frame_id: str
    node_id: str
    node_type: NodeType

    node_title: str | None = None
    node_objective: str | None = None
    node_status: str | None = None

    intent_context: EditIntentContext
    template_context: EditTemplateContext
    strategy_context: EditStrategyContext
    current_variant: CurrentVariantContext
    selection_context: SelectionContext
    visual_state: VisualStateSummary
    recent_history: RecentEditHistory
```

---

## 2.12 给 Proposal 用的解析结果对象

```python
class ResolvedEditReference(BaseModel):
    scope: SelectionMode = "scene"
    primary_targets: list[str] = Field(default_factory=list)
    secondary_targets: list[str] = Field(default_factory=list)
    ambiguous_refs: list[str] = Field(default_factory=list)
    resolution_confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str | None = None
```

---

## 2.13 Proposal v2

建议不要推翻你现在的 proposal 结构，而是增强。

```python
class ProposalStepV2(BaseModel):
    action_type: str
    target_object_ids: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    strength: EditStrength = "subtle"
    reason: str | None = None


class ProposalV2(BaseModel):
    summary: str
    interpretation_basis: list[str] = Field(default_factory=list)

    resolved_reference: ResolvedEditReference
    target_objects: list[str] = Field(default_factory=list)
    locked_objects: list[str] = Field(default_factory=list)

    preserve_rules: list[str] = Field(default_factory=list)
    steps: list[ProposalStepV2] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    requires_confirmation: bool = True
    keep_slot_role: bool = True
    status: ProposalStatus = "draft"
```

---

# 三、对现有域模型的最小补字段建议

你不需要重构，只建议补 3 组字段。

---

## 3.1 ObjectNode 增强

你现有 `ObjectNode` 建议补：

```python
role: str | None = None
semantic_description: str | None = None
editable_actions: list[str] = Field(default_factory=list)
```

### 示例

* `hero_product`
* `before_area`
* `after_area`
* `title_copy`
* `subtitle_copy`
* `trust_badge`
* `lifestyle_bg`

---

## 3.2 ResultNode 增强

建议补：

```python
slot_role: str | None = None
slot_objective: str | None = None
direction_summary: str | None = None
```

### 示例

* `slot_role="pain_contrast"`
* `slot_objective="强化使用前后差异"`
* `direction_summary="降低广告感，增强生活感，保持温和清洁表达"`

---

## 3.3 session_events 增强

建议在 `workspace_session_events` 增加字段或 payload 约定：

```json id="6qj7ra"
{
  "event_type": "proposal_applied",
  "node_id": "...",
  "variant_id": "...",
  "selection_context": {
    "mode": "object",
    "primary_object_id": "obj_after_area",
    "secondary_object_ids": ["obj_hero_product"]
  },
  "direction_summary_after": "..."
}
```

这样后面构建 `recent_history` 很自然。

---

# 四、propose-edit 新接口契约

你现在已经有 `/propose-edit`。
建议保留原路径，但升级请求与返回结构。

---

## 4.1 建议增加一个前置接口

### `GET /growth-lab/api/workspace/node/{id}/edit-context`

用途：

* 前端初始化右栏
* 每次切换 node/variant 时刷新 runtime context
* 让前端不自己拼上下文

### Response

```json id="4jeieo"
{
  "plan_id": "plan_001",
  "frame_id": "frame_main",
  "node_id": "node_002",
  "node_type": "main_image",
  "node_title": "第2张 痛点对比图",
  "node_objective": "强化使用前后差异",
  "node_status": "generated",
  "intent_context": {
    "product_name": "氨基酸洗面奶",
    "category": "个护",
    "audience": "18-29女性",
    "output_goal": "生成主图",
    "style_refs": ["真实生活感", "都市白领公寓"],
    "must_have": ["产品特写", "使用状态"],
    "avoid": ["过强广告感"],
    "raw_prompt": "..."
  },
  "template_context": {
    "template_id": "tpl_main_5_v2",
    "template_name": "主图5张模板",
    "slot_role": "pain_contrast",
    "slot_objective": "强化使用前后差异",
    "adapted_template_snapshot": {},
    "template_constraints": ["保持对比结构", "避免弱化卖点"]
  },
  "strategy_context": {
    "core_claim": "温和不刺激",
    "supporting_claims": ["洗后不紧绷", "适合敏感肌"],
    "visual_goal": "更真实、更柔和",
    "copy_goal": "标题更短更明确",
    "platform_goal": "主图点击率",
    "brand_rules": ["颜色保真", "logo不可遮挡"]
  },
  "current_variant": {
    "variant_id": "var_003",
    "image_url": "...",
    "revision_index": 3
  },
  "selection_context": {
    "mode": "scene",
    "selected_object_ids": [],
    "primary_object_id": null,
    "secondary_object_ids": [],
    "selected_region": null,
    "selected_labels": [],
    "locked_object_ids": ["obj_logo"],
    "editable_object_ids": ["obj_after_area","obj_hero_product"]
  },
  "visual_state": {
    "object_summaries": [],
    "copy_blocks": [],
    "composition_summary": "左右对比构图，主体居中偏左",
    "salience_summary": "主体商品突出度中等",
    "current_direction_summary": "降低广告感，增强生活感"
  },
  "recent_history": {
    "last_user_requests": ["右边更柔和一点"],
    "last_applied_changes": ["减弱右侧高刺激对比"],
    "last_proposal_summaries": ["优化本品使用后区域表现"]
  }
}
```

---

## 4.2 propose-edit v2 请求

### `POST /growth-lab/api/workspace/propose-edit`

### Request

```json id="2sxxkt"
{
  "node_id": "node_002",
  "variant_id": "var_003",
  "user_message": "右边更柔和一点，同时主体商品再突出一点",
  "selection_context": {
    "mode": "multi_object",
    "selected_object_ids": ["obj_after_area", "obj_hero_product"],
    "primary_object_id": "obj_after_area",
    "secondary_object_ids": ["obj_hero_product"],
    "selected_region": null
  },
  "conversation_state": {
    "recent_user_requests": [
      "降低广告感",
      "让画面更生活化"
    ],
    "recent_applied_changes": [
      "背景元素简化",
      "标题缩短"
    ],
    "direction_summary": "降低广告感，增强生活感，保持温和清洁表达"
  }
}
```

---

## 4.3 propose-edit v2 响应

### Response

```json id="cawps6"
{
  "summary": "你希望当前第2张痛点对比图中，右侧本品效果区看起来更柔和舒适，同时增强主体商品的存在感。",
  "interpretation_basis": [
    "当前主对象是右侧本品效果区",
    "辅助对象是主体商品",
    "当前模板角色为痛点对比图，需要保持对比结构"
  ],
  "resolved_reference": {
    "scope": "multi_object",
    "primary_targets": ["obj_after_area"],
    "secondary_targets": ["obj_hero_product"],
    "ambiguous_refs": [],
    "resolution_confidence": 0.93,
    "needs_clarification": false,
    "clarification_question": null
  },
  "target_objects": ["obj_after_area", "obj_hero_product"],
  "locked_objects": [],
  "preserve_rules": [
    "preserve_brand_color",
    "preserve_logo",
    "preserve_slot_role"
  ],
  "steps": [
    {
      "action_type": "soften_effect_area",
      "target_object_ids": ["obj_after_area"],
      "params": {
        "tone": "gentler",
        "contrast": "slight_down"
      },
      "strength": "moderate",
      "reason": "让本品使用后区域更贴近温和清洁的品牌表达"
    },
    {
      "action_type": "enhance_subject",
      "target_object_ids": ["obj_hero_product"],
      "params": {
        "scale": 1.10,
        "salience": "slight_up"
      },
      "strength": "subtle",
      "reason": "增强主体商品存在感，但不破坏当前构图"
    }
  ],
  "risks": [
    "右侧对比减弱过多可能削弱差异表达"
  ],
  "requires_confirmation": true,
  "keep_slot_role": true,
  "status": "draft"
}
```

---

## 4.4 Clarification 场景响应

如果用户没选对象，说“这里更自然一点”。

### Response

```json id="l1gp51"
{
  "summary": "我还不能确定“这里”具体指哪部分。",
  "interpretation_basis": [
    "当前没有明确选中对象或区域",
    "“这里”属于模糊指代"
  ],
  "resolved_reference": {
    "scope": "scene",
    "primary_targets": [],
    "secondary_targets": [],
    "ambiguous_refs": ["这里"],
    "resolution_confidence": 0.21,
    "needs_clarification": true,
    "clarification_question": "请先在画布中选中对象或框选区域，例如主体商品、背景或文案区。"
  },
  "target_objects": [],
  "locked_objects": [],
  "preserve_rules": [],
  "steps": [],
  "risks": [],
  "requires_confirmation": false,
  "keep_slot_role": true,
  "status": "draft"
}
```

---

## 4.5 apply-proposal 建议增强

你现在已有 `/apply-proposal`。
建议请求加上：

```json id="wt1smc"
{
  "node_id": "node_002",
  "variant_id": "var_003",
  "proposal": { ...完整 proposal v2... },
  "apply_mode": "execute", 
  "selection_context_snapshot": {
    "mode": "multi_object",
    "primary_object_id": "obj_after_area"
  }
}
```

### apply_mode 建议支持

* `execute`
* `preview_only`
* `step_by_step`
* `variants_only`

---

# 五、前端右栏重构方案

你现在右栏区块很多，但我建议不是加，而是**重组**。

目标：让右栏从“信息很多”变成“编辑很稳”。

---

## 5.1 新布局结构

建议右栏重构成 5 段：

```text id="tbqu79"
1. 编辑上下文卡
2. 当前方向卡
3. 上下文 chips + 推荐动作
4. 对话区
5. Proposal / 执行结果区
```

---

## 5.2 区块 1：编辑上下文卡

固定置顶，永远可见。

### 展示字段

* 当前节点：第 2 张 痛点对比图
* 当前模板角色：痛点对比
* 当前版本：V3
* 当前主对象：右侧本品效果区
* 当前辅助对象：主体商品
* 当前限制：颜色保真 / logo 锁定 / 保持对比结构

### 作用

让用户和 Agent 都始终知道：
**现在到底在改什么。**

---

## 5.3 区块 2：当前方向卡

这个是你当前实现里很缺的一块。

### 显示

* 当前方向摘要
* 最近 2-3 轮编辑目标

### 示例

```text id="icj0pk"
当前方向：
- 降低广告感
- 增强生活感
- 保持温和清洁表达
```

### 数据来源

* `ResultNode.direction_summary`
* `recent_history`

### 作用

防止多轮编辑方向漂移。

---

## 5.4 区块 3：上下文 chips + 推荐动作

### A. 上下文 chips

显示：

```text id="mwfhdy"
主对象：[右侧本品效果区]
辅助对象：[主体商品]
范围：[当前节点]
```

每个 chip 支持：

* 删除
* 设为主对象
* 替换对象

### B. 推荐动作

推荐动作必须基于：

* 当前模板角色
* 当前对象 role
* 当前方向摘要

例如在 `pain_contrast` 节点里：

* 强化对比
* 右侧更柔和
* 缩短标题
* 主体更突出
* 只出 3 个轻微变体

---

## 5.5 区块 4：对话区

对话区重点升级 3 点。

### 1）输入框 placeholder 动态化

根据主对象变化：

#### 主对象 = 主体商品

“描述你希望如何修改主体商品，例如：更突出一点 / 放大10% / 保持真实质感”

#### 主对象 = 文案区

“描述你希望如何调整文案，例如：更短 / 更克制 / 更突出卖点”

#### 未选对象

“你当前未选中对象，将按整图编辑。也可以先在画布中选中对象或区域。”

### 2）发送前自动插入隐式上下文

前端不要只发文本，发送时附带：

* 当前主对象
* 辅助对象
* 当前方向摘要
* 当前 variant

### 3）当需要澄清时，插入 Clarification Card

不是普通文本回复，而是一个可操作卡片：

* 去画布选对象
* 直接按整图处理
* 从常见对象中选择

---

## 5.6 区块 5：Proposal / 执行结果区

Proposal Card 建议升级为 6 段：

### 1. 理解摘要

### 2. 解析依据

### 3. 修改对象

### 4. 执行动作

### 5. 风险

### 6. 按钮组

按钮组建议保留：

* 直接执行
* 分步执行
* 只生成预览
* 取消

### 执行结果卡建议新增

* revision id
* 变更摘要
* 方向是否保持
* 下一步建议

---

# 六、前端交互补点：画布与右栏如何真正串起来

---

## 6.1 选中对象后的浮层动作建议

当前你应该已经能选中。
建议浮层按钮升级为：

* 设为主对象
* 添加为辅助对象
* 加入对话
* 锁定对象
* 查看对象说明

推荐默认入口：`设为主对象`

---

## 6.2 区域框选后的轻确认

如果用户框选区域，弹出小卡：

系统检测该区域可能包含：

* 文案区
* 背景局部
* 装饰元素

用户可选：

* 主编辑对象
* 辅助影响对象

再进入右栏。

---

## 6.3 当用户点击结构树时，也要能进入主对象状态

结构树不应只是定位画布。
建议：

* 点击 object 节点 = 设为主对象
* shift+点击 = 添加为辅助对象

这样左栏和中间画布行为一致。

---

# 七、AI-coding Prompt

下面这部分你可以直接喂给 Codex / Cursor。

---

## Prompt 1：新增 EditContextPack 与后端接口

```text id="bh7eb2"
你正在升级现有 Growth Lab 的 Visual Workspace runtime。当前系统已经有：

- IntentContext
- CompilePlan
- TemplateBinding
- Frame
- ResultNode
- ObjectNode
- Variant
- workspace_session_events
- /propose-edit
- /apply-proposal

现在请不要推翻现有实现，而是在此基础上新增“运行时编辑上下文层”。

【目标】
新增一个 EditContextPack，用于：
1. 前端右栏初始化
2. 每次切换 node / variant 时获取完整编辑上下文
3. 每次 /propose-edit 时给 LLM 足够的上下文
4. 支持对象级、区域级、整图级对话编辑

【请实现】
1. 在 `apps/growth_lab/schemas/visual_workspace.py` 中新增：
   - RuntimeObjectSummary
   - RuntimeCopyBlock
   - EditIntentContext
   - EditTemplateContext
   - EditStrategyContext
   - CurrentVariantContext
   - SelectionContext
   - VisualStateSummary
   - RecentEditHistory
   - EditContextPack
   - ResolvedEditReference
   - ProposalV2 / ProposalStepV2

2. 在现有 store / service 层中新增：
   - `build_edit_context_pack(node_id, variant_id, selection_context=None)`
   - 从 ResultNode / ObjectNode / Variant / session_events 拼装完整上下文

3. 新增接口：
   - `GET /growth-lab/api/workspace/node/{id}/edit-context`
   - 支持 query 参数 `variant_id`
   - 返回完整 EditContextPack

4. 升级 `POST /growth-lab/api/workspace/propose-edit`
   - 接收：
     - node_id
     - variant_id
     - user_message
     - selection_context
     - conversation_state
   - 返回 ProposalV2

【要求】
- 尽量复用现有模型与 service，不要大改已有 compile/generate/export 流程
- 保持与现有 workspace_session_events 兼容
- 新增字段要对现有主图 5 张工作流友好
- 代码清晰，可继续扩展到 detail/video/buyer_show
```

---

## Prompt 2：实现 resolve-edit-reference 和 propose-edit v2

```text id="8eu0r2"
请基于现有 Growth Lab Visual Workspace 实现对象对话编辑的 runtime 解析层。

【背景】
当前已有：
- ObjectNode
- ResultNode
- 结构树选中
- /propose-edit 返回 summary / target_objects / locked_objects / steps / risks

当前问题：
- “这里”“右边”“主体”“背景”等模糊指代无法稳定绑定到真实对象
- 多轮编辑缺少方向继承
- 对话编辑精度不够

【请实现两层能力】

一、Reference Resolver
新增 service：
- `resolve_edit_reference(edit_context_pack, user_message) -> ResolvedEditReference`

规则：
1. 如果 selection_context 已指定 primary_object_id，则优先绑定该对象
2. 如果 selection_context 有 selected_region，优先按 region 解析
3. 识别语言中的：
   - 这里 / 那里
   - 右边 / 左边 / 中间
   - 主体 / 背景 / 文案 / logo
4. 输出：
   - scope
   - primary_targets
   - secondary_targets
   - ambiguous_refs
   - resolution_confidence
   - needs_clarification
   - clarification_question

二、Edit Planner v2
升级 propose-edit 的 planner：
- 输入 EditContextPack + ResolvedEditReference + user_message
- 输出 ProposalV2

要求：
1. 提案必须包含 interpretation_basis
2. 必须输出 preserve_rules
3. 必须显式说明 keep_slot_role=true/false
4. 若 resolution_confidence 太低，则不要生成具体 steps，而是返回 clarification_question
5. 默认最小改动，不轻易整图重做

【请输出】
- service 代码
- planner 逻辑
- route 改造代码
- 单元测试样例
```

---

## Prompt 3：重构 workspace.html 右栏

```text id="56h6nh"
请重构现有 `apps/growth_lab/templates/workspace.html` 的右栏 Copilot 区，不改变整体页面框架，但提升“对象对话编辑”的清晰度和稳定性。

【当前右栏已有】
1. 当前上下文
2. 为什么长这样
3. AI 建议
4. 对话编辑（提案卡、mini compare grid、节点变体列表、状态机按钮）

【重构目标】
让右栏变成一个稳定的 AI 编辑控制台，核心围绕：
- 当前编辑对象
- 当前方向
- 上下文 chips
- 对话输入
- Proposal
- 执行结果

【请改成以下结构】
1. 编辑上下文卡
   - 当前节点
   - 模板角色
   - 当前版本
   - 主对象
   - 辅助对象
   - 当前限制

2. 当前方向卡
   - direction_summary
   - 最近 2-3 轮编辑摘要

3. 上下文 chips + 推荐动作
   - 主对象 chip
   - 辅助对象 chip
   - 当前范围 chip
   - chips 可删除/切主对象
   - 推荐动作根据当前 node role + object role + eval/direction 生成

4. 对话区
   - placeholder 根据主对象动态变化
   - 发送消息时附带 selection_context + direction_summary
   - 支持 clarification card

5. Proposal / 执行结果区
   - ProposalCard 显示：
     - 理解摘要
     - 解析依据
     - 修改对象
     - 执行动作
     - 风险
     - 按钮
   - ExecutionResultCard 显示：
     - 生成的新 revision
     - 变更摘要
     - 下一步建议

【要求】
- 尽量复用现有 DOM 结构和 JS
- 如果已有 propose 卡片组件逻辑，则在此基础上扩展，不要全删
- 保持与现有状态机按钮兼容
- 保持 mini compare grid 和节点变体列表可继续显示，但放在 Proposal/结果区下方
```

---

## Prompt 4：增加画布选中到右栏的主/辅对象机制

```text id="9b0j8r"
请升级现有 Growth Lab Visual Workspace 的画布交互，使对象选中不再只是“同步右栏”，而是进入真正的 runtime 编辑上下文。

【目标】
支持：
- Focused object
- Primary object
- Secondary objects
- Pinned-to-chat context

【请实现】
1. 在前端状态中新增：
   - focusedObjectId
   - primaryObjectId
   - secondaryObjectIds
   - pinnedContextChips

2. 中间画布对象点击后，出现浮层工具：
   - 设为主对象
   - 添加为辅助对象
   - 加入对话
   - 锁定对象
   - 查看对象说明

3. 左栏“结构树”中点击对象节点：
   - 普通点击：设为主对象
   - shift + 点击：添加为辅助对象

4. 右栏输入框上方显示 chips：
   - 主对象：[...]
   - 辅助对象：[...]
   - 范围：[当前节点]
   - 支持删除 / 重新设主对象

5. 用户发送消息时，把 selection_context 一起发给 /propose-edit

【要求】
- 不破坏现有画布 pan/zoom/节点选中逻辑
- 不破坏现有右栏 Copilot 流
- 尽量使用最小改动补齐这层运行时交互
```

---

## Prompt 5：用现有 session_events 构建 direction_summary

```text id="qm08gh"
请基于现有 Growth Lab SQLite 表 `workspace_session_events`，实现每个 ResultNode 的 direction_summary 和 recent_history 构建逻辑。

【目标】
解决多轮编辑后 Copilot 容易丢方向的问题。

【请实现】
1. 新增 service：
   - `build_recent_edit_history(plan_id, node_id, limit=5)`
   - 返回：
     - last_user_requests
     - last_applied_changes
     - last_proposal_summaries

2. 新增 service：
   - `infer_direction_summary(recent_history, node, template_context, strategy_context)`
   - 输出简短方向摘要，例如：
     - “降低广告感，增强生活感，保持温和清洁表达”
     - “强化对比结构，突出本品优势，避免标题过长”

3. 在以下时机更新：
   - proposal_applied
   - mark_reviewed
   - approve
   - variant_done

4. 把 direction_summary 回写到 ResultNode 或单独缓存层

【要求】
- 不影响现有 timeline 展示
- 尽量复用现有 session_events
- 输出逻辑优先规则化，可少量 LLM 辅助，但需要 fallback
```

---

# 八、建议的落地顺序

为了不打断你现有主图闭环，我建议这样上。

---

## Batch 1：先上后端上下文层

* `EditContextPack`
* `GET /node/{id}/edit-context`
* `propose-edit` 请求增强
* `ObjectNode.role` / `ResultNode.direction_summary`

这批上完，后端语义就稳了。

---

## Batch 2：再上右栏重构

* 编辑上下文卡
* 当前方向卡
* 主/辅对象 chips
* Proposal v2 渲染

这批上完，用户会明显感觉“Agent 更懂我在改什么”。

---

## Batch 3：最后上画布主/辅对象机制

* 浮层按钮
* 结构树 shift+click
* 区域轻确认

这批上完，对象对话编辑体验才真正成立。

---

# 九、这版升级后的预期效果

做完后，你的工作台会从现在的：

> “我能看懂节点、能出 proposal、能走审批闭环”

升级到：

> “我能在当前模板角色下，明确指定我要改哪个对象，Agent 也能稳定理解并给出可控提案，多轮修改方向不会漂。”

这一步对你后面扩到：

* 详情模块
* 视频镜头
* 买家秀
* 竞品图改写

都非常关键，因为这些都依赖同一个 runtime 编辑语义层。

