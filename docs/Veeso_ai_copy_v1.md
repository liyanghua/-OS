**《仿 Veeso 交互方式的 Growth Lab 升级稿》**

* TemplateLibrary / TemplateBinding
* Intent → CompilePlan → Frame → ResultNode → ObjectNode → Variant
* ws-left / ws-canvas / ws-right
* propose-edit / apply-proposal / session_events
* approved → promote_to_template_asset

基础上，升级成一个更像 **Veeso 风格的 AI-native 多模态视觉策划工作台**。

---

# 一、升级目标

这次升级的核心不是“再做一个画图工具”，而是把工作台升级为：

> **Agent-native Visual Planning Workspace**
> 以结果为中心，以多模态 Agent 为中枢，以模板/策略/技能/资产为可注入上下文，支持 0-prompt 起步、单图精修、多图比较、策略加载、技能执行、记忆继承。

---

# 二、设计原则

先定义这版产品的 6 个核心原则。

## 1）Content-first，而不是 blank-canvas-first

用户进入后先看到一批可用结果和建议，不是空白画布。

## 2）Single-focus editing

中间只聚焦当前 1 张图；左侧负责结果池，右侧负责智能协作。

## 3）Agent-native，不是外挂式 Copilot

右侧 Agent 不是聊天挂件，而是整个工作台的上下文中枢。

## 4）0-prompt 优先

用户可以一句话不说，也能得到“下一步最可能动作”的建议。

## 5）多模态上下文可装配

图、视频、对象、模板、策略包、竞品图、技能，都能被加入当前对话上下文。

## 6）记忆继承

当前轮、当前任务、历史资产三层记忆同时起作用。

---

# 三、整体页面结构图

下面是推荐的页面骨架。

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Topbar                                                                                      │
│ Project / Task / Output Type / Template / Strategy Pack / Status / Export / Version / ...  │
├───────────────────────┬──────────────────────────────────────┬──────────────────────────────┤
│ Left Rail             │ Center Focus Canvas                 │ Right Agent Workspace        │
│ 结果流 / 参考流 /     │ 当前焦点图                          │ 多模态 Agent 中枢            │
│ 记忆流                │ + 编辑 Action Bar                  │ + Attachments / Skills       │
│                       │ + 对象/区域交互层                  │ + 0-prompt Suggestions       │
│ ┌───────────────────┐ │ ┌────────────────────────────────┐ │ ┌──────────────────────────┐ │
│ │ Tab A 当前结果     │ │ │ Action Bar                    │ │ │ Context Header           │ │
│ │ - 图片瀑布流       │ │ │ Generate Replace Remove BG... │ │ │ 当前节点/模板/对象/方向  │ │
│ │ - 版本/评分/状态   │ │ ├────────────────────────────────┤ │ ├──────────────────────────┤ │
│ ├───────────────────┤ │ │                                │ │ │ Attachments Panel        │ │
│ │ Tab B 参考资产     │ │ │        Focus Image            │ │ │ 当前图/参考图/视频/模板  │ │
│ │ - 模板资产         │ │ │   + object overlay            │ │ │ 策略包/竞品/技能         │ │
│ │ - 品牌素材         │ │ │   + region select             │ │ ├──────────────────────────┤ │
│ │ - 竞品图           │ │ │                                │ │ │ Suggestion Cards         │ │
│ ├───────────────────┤ │ ├────────────────────────────────┤ │ │ 0-prompt 下一步建议      │ │
│ │ Tab C 历史记忆     │ │ │ Compare / Versions Strip      │ │ ├──────────────────────────┤ │
│ │ - 最近编辑         │ │ └────────────────────────────────┘ │ │ Chat + Proposal + Result │ │
│ │ - 最近技能         │ │                                      │ └──────────────────────────┘ │
│ └───────────────────┘ │                                      │                              │
├───────────────────────┴──────────────────────────────────────┴──────────────────────────────┤
│ Bottom Timeline / Activity / Revisions / Batch Status / Audit                               │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 四、左中右三栏组件清单

---

## A. 左侧：Result Feed / Asset Feed / Memory Feed

左侧不再只是结构树，而是一个**瀑布流结果池 + 参考资产池 + 历史记忆池**。

---

### A1. Tab：当前结果（Results）

**目标**：展示当前任务下的图片/视频结果，供选择、比较、继续编辑。

#### 组件清单

| 组件                      | 功能                                 |
| ----------------------- | ---------------------------------- |
| `ResultFeedTabs`        | Tab 切换：当前结果 / 参考资产 / 历史记忆          |
| `ResultWaterfallGrid`   | 瀑布流展示图卡                            |
| `ResultCard`            | 单张图片卡                              |
| `ResultQuickActions`    | hover 快捷操作                         |
| `ResultFilters`         | 按 frame / node / score / status 过滤 |
| `ResultCompareLauncher` | 选两张或多张做 compare                    |
| `PinnedCandidatesPanel` | 收藏候选图                              |

#### `ResultCard` 字段建议

* thumbnail
* node_title
* slot_role
* template_name
* version
* score / badge
* status
* source_type（generated / edited / promoted / imported）

#### Hover 操作建议

* `Edit`
* `Add to Chat`
* `Use as Reference`
* `Compare`
* `Set as Current`
* `More`

---

### A2. Tab：参考资产（Assets）

**目标**：让模板资产、品牌素材、竞品图、优秀案例可以随时注入 Agent。

#### 组件清单

| 组件                       | 功能                       |
| ------------------------ | ------------------------ |
| `AssetCategorySwitcher`  | 模板资产 / 品牌素材 / 竞品 / 历史满意版 |
| `AssetSearchBar`         | 搜索资产                     |
| `AssetCard`              | 资产卡                      |
| `AssetPreviewDrawer`     | 资产详情预览                   |
| `AttachToChatButton`     | 加入对话上下文                  |
| `ApplyAsReferenceButton` | 设为参考图                    |

#### 资产类型建议

* Template Asset
* Brand Material
* Competitor Image
* Promoted Main Image
* Buyer-show Example
* Video Shot Reference

---

### A3. Tab：历史记忆（Memory）

**目标**：把“最近编辑链路”显性化，让右侧 Agent 不至于失忆。

#### 组件清单

| 组件                      | 功能               |
| ----------------------- | ---------------- |
| `RecentEditsList`       | 最近编辑请求           |
| `RecentSuggestionsList` | 最近接受/忽略的建议       |
| `RecentSkillsList`      | 最近执行的技能          |
| `RecentAttachmentsList` | 最近加入过的图/视频/模板/策略 |
| `DirectionSummaryCard`  | 当前方向摘要           |
| `SessionReplayEntry`    | 点击回到某次编辑节点       |

---

## B. 中间：Focus Canvas

中间永远只聚焦**当前编辑对象**，不负责管理所有结果。

---

### B1. 顶部 Action Bar

你发的附件那种交互很适合，但要做成**对象语义感知**的。

#### 一级动作

* Generate
* Replace
* Remove Background
* Upscale
* Expand / Crop
* Compare
* More

#### 组件清单

| 组件                              | 功能               |
| ------------------------------- | ---------------- |
| `CanvasActionBar`               | 顶部操作条            |
| `ActionButton`                  | 单个动作按钮           |
| `ContextAwareActionSuggestions` | 根据当前对象/区域给快捷动作   |
| `CanvasModeSwitch`              | 浏览 / 对象编辑 / 区域编辑 |

---

### B2. 焦点画布主体

#### 组件清单

| 组件                      | 功能                     |
| ----------------------- | ---------------------- |
| `FocusCanvasViewport`   | 图片显示 / pan / zoom      |
| `ObjectOverlayLayer`    | 对象 hover / selected 边框 |
| `RegionSelectionLayer`  | 框选区域                   |
| `ObjectFloatingToolbar` | 对象浮层工具                 |
| `CanvasStatusBar`       | 当前模式、当前对象、当前版本         |
| `CanvasCompareStrip`    | 当前图与历史版本/候选图对比         |

#### 对象浮层动作建议

* Add to Chat
* Set as Primary
* Add as Secondary
* Replace
* Remove
* Lock
* View Details

---

### B3. 画布底部版本/比较带

#### 组件清单

| 组件                       | 功能                    |
| ------------------------ | --------------------- |
| `VersionStrip`           | 当前图历史版本               |
| `CompareMiniRail`        | 与其它变体做快速对比            |
| `ApplyFromCompareButton` | 从 compare 里选择一个成为当前版本 |

---

## C. 右侧：Agent Workspace

右侧从“Copilot”升级成“多模态 Agent 中枢”。

---

### C1. Context Header

显示当前最重要的运行时上下文。

#### 组件清单

| 组件                       | 功能                       |
| ------------------------ | ------------------------ |
| `WorkspaceContextHeader` | 当前节点 / 模板 / 版本 / 对象 / 约束 |
| `CurrentDirectionCard`   | 当前方向摘要                   |
| `ConstraintBadges`       | 品牌规则 / 锁定对象 / 模板护栏       |
| `NodeRoleCard`           | 当前图位角色说明                 |

#### 推荐展示字段

* 当前任务：氨基酸洗面奶主图生成
* 当前节点：第2张 痛点对比图
* 当前模板：主图 5 张模板 v2
* 当前版本：V3
* 主对象：右侧本品效果区
* 辅助对象：主体商品
* 当前方向：降低广告感、增强生活感、保持温和表达
* 当前约束：logo 锁定 / 颜色保真 / 保持对比结构

---

### C2. Attachments Panel（核心）

这是和普通对话框最大的差异。

#### 组件清单

| 组件                          | 功能                                  |
| --------------------------- | ----------------------------------- |
| `ConversationAttachmentBar` | 当前对话上下文 attachments                 |
| `AttachmentChip`            | 单个上下文项                              |
| `AttachmentPicker`          | 添加更多上下文                             |
| `AttachmentDropZone`        | 支持左侧/画布拖拽                           |
| `AttachmentRoleToggle`      | 设为 primary / secondary / supporting |

#### 可添加的上下文类型

* 当前图
* 参考图
* 参考视频
* 对象引用
* 区域引用
* 模板资产
* 策略包
* 品牌规则
* 竞品拆解图
* 历史满意版
* Skill

---

### C3. 0-prompt Suggestions

这是用户还没写 prompt 时，系统主动给建议的地方。

#### 组件清单

| 组件                       | 功能                     |
| ------------------------ | ---------------------- |
| `SuggestionSection`      | 建议区容器                  |
| `SuggestionCard`         | 单条建议卡                  |
| `SuggestionGroup`        | 下一步动作 / 资产 / 技能 / 模板切换 |
| `QuickAcceptButton`      | 一键采纳                   |
| `RefineSuggestionButton` | 交给 Agent 细化            |

#### 建议分组

* Recommended Next Actions
* Recommended Assets
* Recommended Skills
* Recommended Template / Strategy

---

### C4. Chat + Proposal + Result

#### 组件清单

| 组件                     | 功能             |
| ---------------------- | -------------- |
| `MultimodalChatThread` | 支持文本/图片/视频/对象卡 |
| `ChatInputBar`         | 输入栏            |
| `SkillLauncherTray`    | 快速选技能          |
| `ProposalCardV2`       | 结构化提案          |
| `ExecutionResultCard`  | 执行结果           |
| `ClarificationCard`    | 需要澄清时的选择卡      |
| `MiniCompareGrid`      | 变体比较           |
| `NodeVariantList`      | 节点版本列表         |

---

# 五、页面交互主链路

---

## 场景 1：0-prompt 起步

```text
进入工作台
→ 左侧加载当前任务的结果流
→ 中间默认打开最优候选图
→ 右侧自动生成 Context Header + 0-prompt 建议
→ 用户点“放大主体商品”
→ Agent 出 proposal
→ 用户确认执行
→ 生成新版本
```

---

## 场景 2：加入参考图再编辑

```text
左侧选一张竞品图
→ Add to Chat
→ 中间选中当前图的主体商品
→ 右侧自动形成 attachments：
   [当前图] [主体商品] [竞品图]
→ 用户说：参考这张竞品的高级感，但保持我们温和风格
→ Agent proposal
→ 执行
```

---

## 场景 3：不写 prompt，只点技能

```text
用户不输入
→ 在右侧 Skills 区点 Replace Background
→ Agent 读取当前对象 + 模板 + 方向 + 品牌规则
→ 自动生成替换背景提案
→ 用户确认
→ 执行
```

---

# 六、Schema 设计

下面给你一版直接可落到 `apps/growth_lab/schemas/visual_workspace.py` 的对象模型草案。

---

## 6.1 ConversationAttachment Schema

```python
from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field


AttachmentType = Literal[
    "current_image",
    "reference_image",
    "reference_video",
    "object_ref",
    "region_ref",
    "template_asset",
    "strategy_pack",
    "brand_rule_pack",
    "competitor_asset",
    "historical_variant",
    "skill_ref"
]

AttachmentRole = Literal["primary", "secondary", "supporting"]


class ConversationAttachment(BaseModel):
    id: str
    type: AttachmentType
    ref_id: str
    label: str
    role: AttachmentRole = "supporting"

    preview_url: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    source_scope: str | None = None   # workspace / asset_library / plan / node / external
    pinned: bool = False
    created_by: str | None = None     # user / system / agent
    created_at: str | None = None
```

---

## 6.2 SkillRef Schema

```python
SkillCategory = Literal[
    "image_edit",
    "planning",
    "copy",
    "brand_guard",
    "variant",
    "template",
    "asset",
    "video_edit"
]

SkillTriggerMode = Literal["manual", "recommended", "auto"]


class SkillRef(BaseModel):
    id: str
    name: str
    category: SkillCategory
    description: str

    applicable_node_roles: list[str] = Field(default_factory=list)
    applicable_object_roles: list[str] = Field(default_factory=list)

    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)

    trigger_mode: SkillTriggerMode = "manual"
    confidence_hint: float | None = None
    enabled: bool = True
```

---

## 6.3 StrategyPackRef Schema

```python
class StrategyPackRef(BaseModel):
    id: str
    name: str
    description: str | None = None

    category: str | None = None
    source: str | None = None

    core_claim: str | None = None
    supporting_claims: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

    payload: dict[str, Any] = Field(default_factory=dict)
```

---

## 6.4 SuggestionCard Schema

```python
SuggestionType = Literal[
    "next_action",
    "asset",
    "skill",
    "template_switch",
    "strategy_pack",
    "compare_hint"
]


class SuggestionCard(BaseModel):
    id: str
    type: SuggestionType
    title: str
    reason: str

    target_refs: list[str] = Field(default_factory=list)
    score: float = 0.0
    priority: int = 0

    suggested_skill_id: str | None = None
    suggested_attachment_ids: list[str] = Field(default_factory=list)
    suggested_params: dict[str, Any] = Field(default_factory=dict)

    dismissible: bool = True
    accepted: bool = False
```

---

## 6.5 AgentSessionMemory Schema

```python
class AgentSessionMemory(BaseModel):
    session_id: str
    plan_id: str
    frame_id: str | None = None
    node_id: str | None = None
    active_variant_id: str | None = None

    current_direction_summary: str | None = None

    primary_object_id: str | None = None
    secondary_object_ids: list[str] = Field(default_factory=list)

    active_attachment_ids: list[str] = Field(default_factory=list)
    recent_skill_ids: list[str] = Field(default_factory=list)

    last_user_requests: list[str] = Field(default_factory=list)
    last_applied_changes: list[str] = Field(default_factory=list)
    last_suggestion_ids: list[str] = Field(default_factory=list)
```

---

# 七、0-prompt 推荐器设计

这一块是整版升级的“灵魂”。

---

## 7.1 推荐器目标

在用户**没有输入 prompt**，甚至没有明确下一步动作时，系统能基于当前上下文自动给出：

1. 下一步最可能操作
2. 最适合加载的资产
3. 最适合调用的技能
4. 最值得切换的模板/策略包

---

## 7.2 推荐器输入信号

建议从 6 类信号构建。

### A. 意图信号

* output_type（主图 / 详情 / 视频）
* 用户原始 prompt
* 当前任务目标
* 业务目标（点击率 / 转化 / 风格统一）

### B. 模板信号

* 当前 template_id
* slot_role
* slot_objective
* template constraints

### C. 视觉信号

* 当前图像分析结果
* salience / clutter / copy density / subject size
* object roles
* 当前对象分布

### D. 编辑历史信号

* 最近 3 次用户请求
* 最近 3 次 proposal
* 最近 3 次 applied changes
* 当前 direction_summary

### E. 资产信号

* 最近常用参考图
* 当前品牌素材
* 历史满意版本
* promoted assets

### F. 技能信号

* 当前 node / object 适用的 skill
* 历史同类任务最常调用 skill
* 品类/模板下高命中 skill

---

## 7.3 推荐器输出分层

推荐器不要只吐一堆 suggestions，而要分四层。

---

### Layer 1：Next Action Suggestions

**输出示例：**

* 放大主体商品
* 让背景更生活化
* 缩短标题文案
* 生成 3 个轻微变体

### Layer 2：Asset Suggestions

**输出示例：**

* 加载品牌策略包：敏感肌温和表达
* 加载竞品参考：高端洁面场景图
* 加载历史满意版：主图第2张最佳版

### Layer 3：Skill Suggestions

**输出示例：**

* Replace Background
* Rewrite Copy
* Remove Background
* Generate Variants

### Layer 4：Template / Strategy Suggestions

**输出示例：**

* 当前卖点更适合“核心需求满足图”
* 当前图建议切换到“场景直击图”
* 建议加载“都市白领生活化风格包”

---

## 7.4 推荐器实现方式：规则 + 轻模型 + LLM 解释

不建议一开始就完全用 LLM 端到端做推荐。
建议三层。

---

### 第 1 层：Rule Engine（必须有）

适合做明确规则：

* 若 `slot_role = pain_contrast` 且 `subject_salience < threshold`
  → 推荐“放大主体商品”
* 若 `copy_density > threshold`
  → 推荐“缩短标题文案”
* 若当前无 attachments
  → 推荐“加载品牌策略包”或“加载参考图”
* 若最近 2 次都在改背景
  → 推荐 skill = `Replace Background`

---

### 第 2 层：Ranker（可规则先行）

用简单打分做排序。

推荐分数可先用：

```text
score = context_match * 0.35
      + history_match * 0.20
      + template_fit * 0.20
      + skill_applicability * 0.15
      + asset_relevance * 0.10
```

---

### 第 3 层：LLM Reasoner（用于解释）

LLM 不负责乱想，而是负责：

* 把 rule/ranker 的结果整理成人能懂的建议文案
* 给出 reason
* 给出可能的执行参数

比如把：

* action = enhance_subject
* score = 0.92
* because = subject_salience_low + pain_contrast_template

转成：

> 主体商品当前存在感偏弱，而这张图承担“痛点对比图”角色，建议轻微放大主体商品，增强核心卖点承接。

---

## 7.5 推荐器服务层设计

建议新增：

* `workspace_suggestion_service.py`

### 核心函数

```python
def build_suggestion_context(plan_id: str, node_id: str, variant_id: str | None) -> dict: ...
def generate_next_action_suggestions(ctx: dict) -> list[SuggestionCard]: ...
def generate_asset_suggestions(ctx: dict) -> list[SuggestionCard]: ...
def generate_skill_suggestions(ctx: dict) -> list[SuggestionCard]: ...
def generate_template_strategy_suggestions(ctx: dict) -> list[SuggestionCard]: ...
def merge_and_rank_suggestions(...) -> list[SuggestionCard]: ...
```

---

## 7.6 推荐器 API

### 1）获取建议

`GET /growth-lab/api/workspace/node/{id}/suggestions?variant_id=...`

返回：

```json
{
  "next_actions": [...],
  "assets": [...],
  "skills": [...],
  "template_strategy": [...]
}
```

### 2）接受建议

`POST /growth-lab/api/workspace/suggestion/{id}/accept`

### 3）忽略建议

`POST /growth-lab/api/workspace/suggestion/{id}/dismiss`

### 4）基于建议发起 proposal

`POST /growth-lab/api/workspace/suggestion/{id}/propose`

---

# 八、与现有 Growth Lab 的映射关系

下面这部分是为了让你更容易落地。

---

## 8.1 现有模块怎么复用

| 现有模块                        | 升级后角色                             |
| --------------------------- | --------------------------------- |
| `TemplateLibrary`           | 左侧资产池 + 右侧模板 attachment 来源        |
| `TemplateBinding`           | 右侧 Context Header / Strategy 来源   |
| `ResultNode`                | 左侧结果流 / 中间焦点图基础对象                 |
| `ObjectNode`                | 中间对象交互层 / 右侧 object attachment 来源 |
| `Variant`                   | 版本条 / compare strip / 当前图         |
| `workspace_session_events`  | 右侧记忆区 / 推荐器历史信号                   |
| `suggest-actions`           | 可升级为 suggestion service 的一部分      |
| `propose-edit`              | 接收建议、对话、技能触发后的统一提案出口              |
| `apply-proposal`            | 最终执行口                             |
| `promote_to_template_asset` | 资产池回流                             |

---

## 8.2 V1 优先覆盖范围

建议先只做 **main_image** 深度升级，其它类型只做“可注入 / 可展示”。

### 深度支持

* 主图 5 张
* 单图编辑
* 参考图 attachment
* 技能推荐
* 策略包加载
* 0-prompt 建议

### 轻支持

* 详情图
* 视频脚本 / shot
* 买家秀
* 竞品图

---

# 九、页面状态机建议

为了不让交互乱，建议明确几个页面态。

---

## 左侧状态

* `result_feed`
* `asset_feed`
* `memory_feed`

## 中间状态

* `browse_mode`
* `object_edit_mode`
* `region_edit_mode`
* `compare_mode`

## 右侧状态

* `idle_with_suggestions`
* `attachments_ready`
* `chatting`
* `proposal_ready`
* `executing`
* `result_ready`
* `clarification_needed`

---

# 十、AI-coding Prompt

下面给你一组可直接喂给 Cursor / Codex 的 prompt，按 batch 拆开。

---

## Prompt 1：重构页面骨架

```text
请基于现有 Growth Lab 的 `apps/growth_lab/templates/workspace.html` 做一次仿 Veeso 交互方式的升级，但不要推翻现有工作台结构。

【目标】
把现有工作台升级成三栏结构：
1. 左侧：Result Feed / Asset Feed / Memory Feed
2. 中间：Focus Canvas（单图编辑）
3. 右侧：Agent Workspace（多模态 Agent 中枢）

【要求】
- 顶部保留现有 topbar 能力，但增强显示：task / template / strategy / status / export / version
- 左侧新增 tab：
  - 当前结果
  - 参考资产
  - 历史记忆
- 当前结果用瀑布流图片卡展示，不再只是树结构
- 中间只显示当前焦点图，并新增 action bar：
  - Generate
  - Replace
  - Remove Background
  - Upscale
  - Expand / Crop
  - Compare
  - More
- 右侧改为 4 段：
  1）Context Header
  2）Conversation Attachments
  3）0-prompt Suggestions
  4）Chat + Proposal + Result

【注意】
- 不破坏现有 ws-left / ws-canvas / ws-right 的整体布局逻辑，尽量在原 DOM 基础上重组
- 保持现有 timeline / proposal / compare grid / variant list 兼容
- 先实现 HTML 结构和 mock 数据渲染，再逐步接真接口
```

---

## Prompt 2：新增 ConversationAttachment / SkillRef / SuggestionCard Schema

```text
请在现有 `apps/growth_lab/schemas/visual_workspace.py` 中新增以下运行时对象模型，用于支持多模态 Agent 工作台：

1. ConversationAttachment
2. SkillRef
3. StrategyPackRef
4. SuggestionCard
5. AgentSessionMemory

【字段要求】
ConversationAttachment:
- id
- type: current_image / reference_image / reference_video / object_ref / region_ref / template_asset / strategy_pack / brand_rule_pack / competitor_asset / historical_variant / skill_ref
- ref_id
- label
- role: primary / secondary / supporting
- preview_url
- payload
- source_scope
- pinned
- created_by
- created_at

SkillRef:
- id
- name
- category
- description
- applicable_node_roles
- applicable_object_roles
- input_contract
- output_contract
- trigger_mode
- enabled

SuggestionCard:
- id
- type: next_action / asset / skill / template_switch / strategy_pack / compare_hint
- title
- reason
- target_refs
- score
- priority
- suggested_skill_id
- suggested_attachment_ids
- suggested_params
- dismissible
- accepted

AgentSessionMemory:
- session_id
- plan_id
- node_id
- active_variant_id
- current_direction_summary
- primary_object_id
- secondary_object_ids
- active_attachment_ids
- recent_skill_ids
- last_user_requests
- last_applied_changes
- last_suggestion_ids

【要求】
- 代码使用 Pydantic
- 尽量与现有 ResultNode / ObjectNode / Variant 兼容
- 不破坏现有 compile / generate / approve 流程
```

---

## Prompt 3：实现 0-prompt 推荐器

```text
请为现有 Growth Lab Visual Workspace 实现一个 0-prompt 推荐器，用于在用户未输入 prompt 时，主动给出下一步操作建议。

【目标】
推荐器输出四类建议：
1. next_actions
2. assets
3. skills
4. template_strategy

【输入信号】
- 当前任务 intent
- 当前 template / slot_role / slot_objective
- 当前 ResultNode / active Variant
- 当前图的 visual_state（主体突出度、文案密度、背景复杂度等）
- recent_history（最近用户请求、最近 applied changes、direction summary）
- 当前已有 attachments
- 当前适用 skills
- 品牌规则与模板约束

【实现方式】
- 新增 `workspace_suggestion_service.py`
- 先用规则 + 简单打分实现
- 保留后续引入 LLM reasoner 的扩展点

【请实现】
1. `build_suggestion_context(plan_id, node_id, variant_id)`
2. `generate_next_action_suggestions(ctx)`
3. `generate_asset_suggestions(ctx)`
4. `generate_skill_suggestions(ctx)`
5. `generate_template_strategy_suggestions(ctx)`
6. `merge_and_rank_suggestions(...)`

【API】
新增：
- `GET /growth-lab/api/workspace/node/{id}/suggestions`
- `POST /growth-lab/api/workspace/suggestion/{id}/accept`
- `POST /growth-lab/api/workspace/suggestion/{id}/dismiss`
- `POST /growth-lab/api/workspace/suggestion/{id}/propose`

【要求】
- 先实现主图 main_image 场景
- 规则要可解释
- 输出结构使用 SuggestionCard
```

---

## Prompt 4：右侧 Agent Workspace 重构

```text
请重构现有 workspace 右栏，使其从普通 Copilot 升级为多模态 Agent Workspace。

【新结构】
1. Context Header
   - 当前节点
   - 当前模板
   - 当前版本
   - 主对象 / 辅助对象
   - 当前方向摘要
   - 当前约束

2. Conversation Attachments
   - 显示当前图 / 参考图 / 视频 / 对象 / 区域 / 模板 / 策略包 / 技能
   - 支持删除、切 role、拖拽加入

3. 0-prompt Suggestions
   - 推荐下一步动作
   - 推荐参考资产
   - 推荐技能
   - 推荐模板/策略包

4. Chat + Proposal + Result
   - 输入框支持多模态对话
   - ProposalCardV2
   - ExecutionResultCard
   - ClarificationCard
   - 保持 mini compare grid 和 variant list 兼容

【交互要求】
- 左侧图卡可 Add to Chat
- 中间对象可 Add to Chat / Set as Primary / Add as Secondary
- 右侧 attachment chips 要显示 role：primary / secondary / supporting
- 点击 suggestion 可直接转 proposal，不要求用户先写 prompt

【要求】
- 尽量复用现有 propose-edit / apply-proposal 流程
- 不破坏现有状态机按钮
- 先实现 mock 交互，再接后端真数据
```

---

## Prompt 5：左侧瀑布流与拖拽注入上下文

```text
请升级现有 Growth Lab Workspace 左侧区域，使其支持图片瀑布流 + 参考资产注入 + 历史记忆展示。

【目标】
左侧包含三个 tab：
1. 当前结果
2. 参考资产
3. 历史记忆

【当前结果】
- 用瀑布流展示当前任务下的图片结果
- ResultCard 显示 thumbnail / node_title / slot_role / version / score / status
- hover 操作：
  - Edit
  - Add to Chat
  - Use as Reference
  - Compare
  - Set as Current

【参考资产】
- 展示模板资产、品牌素材、竞品图、promoted_main_images
- 支持 Add to Chat / Apply as Reference

【历史记忆】
- 展示 recent edits / recent skills / direction summary / recent attachments

【拖拽】
- 支持把左侧任意图卡/资产拖到右侧 Conversation Attachments 区
- 拖入后生成 ConversationAttachment，默认 role = supporting

【要求】
- 尽量使用现有 gallery / tree / history 数据
- 如果没有真实拖拽，可先用点击“Add to Chat”模拟
- 不破坏现有 node 定位与选中逻辑
```

---

# 十一、推荐的实施顺序

建议按 4 个 batch 来，不要一次全做。

---

## Batch 1：页面骨架升级

* 左侧三个 tab
* 中间 action bar
* 右侧四段结构
* mock suggestions

## Batch 2：Schema + Attachments

* ConversationAttachment
* SkillRef
* SuggestionCard
* AgentSessionMemory
* 前端 attachment chips

## Batch 3：0-prompt 推荐器

* suggestion service
* suggestions API
* accept/dismiss/propose

## Batch 4：完整交互闭环

* 左侧 Add to Chat
* 中间对象 Add to Chat
* 右侧 skill launcher
* suggestion → proposal → apply

---

# 十二、最终一句话总结


> **借鉴 Veeso 的结果优先 + 单图聚焦 + 集成编辑的交互方式，升级你现有 Growth Lab 成为一个以多模态 Agent 为中枢、可装配模板/策略/技能/资产、支持 0-prompt 建议的视觉策划工作台。**


