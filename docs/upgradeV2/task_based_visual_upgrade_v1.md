下面给你一版可直接用于产品/设计/AI-coding 开工的正式稿：

# 《带 Task Rail 的 Growth Lab 四栏工作台：页面结构图 + 顶层对象模型 + 状态机 + AI-coding Prompt》

---

# 0. 文档定位

本文档用于把你当前的 Growth Lab 视觉工作台，从：

* 模板中心
* 编译台
* Visual Result Workspace
* 多模态 Agent 工作台

进一步升级为一个真正的：

> **Task-first / Agent-native / Multi-output 的四栏工作台**

它面向三类主任务：

1. **主图策划**
2. **视频策划**
3. **详情页策划**

并满足以下能力：

* 多任务并行
* 任务管理与状态跟踪
* 任务上下文隔离
* 任务内结果流 / 资产流 / 记忆流
* 焦点结果编辑
* 原生多模态 Agent 协作
* 模板 / 策略包 / 技能 / 资产统一装配
* 0-prompt 智能建议
* 结果沉淀为资产

---

# 1. 产品目标与核心设计原则

---

## 1.1 产品目标

把 Growth Lab 升级为一个围绕“用户主任务”组织的内容策划与视觉结果工作台：

* 用户先进入“任务”
* 任务下面承载模板、编译计划、结果节点、编辑链路、审批链路
* Agent 负责在当前任务上下文中辅助用户高效完成结果生产
* 主图 / 视频 / 详情页三类任务共享统一框架，但拥有各自专属的焦点编辑视图

---

## 1.2 核心设计原则

### 原则 1：Task-first

工作台的第一层不是“图”或“节点”，而是“任务”。

### 原则 2：Current-task scoped

所有结果、资产、建议、记忆都绑定当前任务，不跨任务污染。

### 原则 3：Single-focus editing

中间工作区永远只聚焦当前任务中的一个焦点对象（某张图 / 某个镜头 / 某个详情模块）。

### 原则 4：Agent-native

右侧不是外挂聊天框，而是带上下文记忆、附件装配、技能调用、建议系统的原生 Agent 工作区。

### 原则 5：0-prompt first

用户进入任务后，即使一句话不说，系统也能给出最可能的下一步建议。

### 原则 6：Unified framework, specialized rendering

主图 / 视频 / 详情页共用同一工作台骨架，但中间焦点区按任务类型渲染不同编辑视图。

---

# 2. 四栏工作台总览

---

## 2.1 总体结构

建议采用：

```text
Task Rail | Feed Rail | Focus Workspace | Agent Workspace
```

即：

1. **Task Rail**：任务栏
2. **Feed Rail**：当前任务的结果/资产/记忆/结构
3. **Focus Workspace**：当前焦点结果编辑区
4. **Agent Workspace**：当前任务上下文下的多模态 Agent

---

## 2.2 页面结构图（总图）

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Topbar                                                                                                       │
│ Brand / Product / Workspace / Current Task / Current Node / Template / Strategy / Status / Export / More   │
├──────────────┬─────────────────────────┬────────────────────────────────────┬───────────────────────────────┤
│ Task Rail    │ Feed Rail               │ Focus Workspace                    │ Agent Workspace               │
│              │                         │                                    │                               │
│ + New Task   │ Current Task Header     │ Focus Header                       │ Context Header                │
│ Search       │ Task Info / Progress    │ Action Bar                         │ Active Context Summary        │
│ Filter       │ Tabs:                   │                                    │                               │
│              │ - Results               │ [main_image] Focus Canvas          │ Attachments Panel             │
│ Task Types   │ - Assets                │ [video_plan] Shot/Storyboard View  │ - current image/video/module  │
│ - All        │ - Memory                │ [detail_page] Module Layout View   │ - refs / template / strategy  │
│ - Main Img   │ - Structure             │                                    │ - skills / rules              │
│ - Video      │                         │ Compare Strip / Version Strip      │                               │
│ - Detail     │ Waterfall / Tree /      │                                    │ 0-prompt Suggestions          │
│ - Done       │ Asset Cards / Memory    │                                    │ - next actions                │
│              │                         │                                    │ - assets                      │
│ Task List    │                         │                                    │ - skills                      │
│ - Task Card  │                         │                                    │ - template/strategy           │
│ - status     │                         │                                    │                               │
│ - progress   │                         │                                    │ Chat / Proposal / Result      │
│ - unread     │                         │                                    │ Skills Tray                   │
├──────────────┴─────────────────────────┴────────────────────────────────────┴───────────────────────────────┤
│ Bottom Timeline / Activity / Batch Status / Audit / Approvals                                               │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 3. 四栏详细设计

---

## 3.1 第一栏：Task Rail（任务栏）

任务栏是整个工作台的入口层，承载用户的主任务。

---

### 3.1.1 任务栏职责

任务栏解决四件事：

1. 当前在做哪些任务
2. 任务怎么分类与筛选
3. 每个任务当前进行到哪里
4. 切换任务时如何恢复现场

---

### 3.1.2 任务栏页面结构

```text
Task Rail
├── Header
│   ├── + New Task
│   ├── Search
│   └── Filter
├── Working Set
│   ├── 最近活跃任务
│   ├── Pinned Tasks
│   └── 执行中任务
├── Task Categories
│   ├── 全部任务
│   ├── 主图策划
│   ├── 视频策划
│   ├── 详情页策划
│   ├── 待审核
│   ├── 已完成
│   └── 已归档
└── Task List
    ├── TaskCard
    ├── TaskCard
    └── ...
```

---

### 3.1.3 TaskCard 字段建议

每个任务卡展示：

* `title`
* `task_type`
* `status`
* `progress_summary`
* `updated_at`
* `unread_hint_count`
* `running_batch_count`
* `pending_review_count`

#### 示例

```text
[主图] 氨基酸洗面奶主图
编辑中 · 3/5 已生成 · 5m前

[视频] 氨基酸洗面奶视频
待补镜头 · 11m前

[详情] 氨基酸洗面奶详情页
待审核 · 1h前
```

---

### 3.1.4 任务栏交互

#### 基本交互

* 点击任务卡：切换当前任务
* hover：显示快捷操作
* 右键 / 更多：

  * Open
  * Rename
  * Duplicate
  * Archive
  * Delete
  * Pin

#### 新建任务

点击 `+ New Task` 弹窗：

* 任务类型：主图 / 视频 / 详情
* 商品
* 目标
* 可选模板
* 可选策略包

创建后进入该任务并触发编译。

---

## 3.2 第二栏：Feed Rail（当前任务的信息流）

Feed Rail 只服务于**当前选中的任务**。

---

### 3.2.1 Feed Rail 职责

1. 展示当前任务下的结果集合
2. 展示可用的参考资产
3. 展示当前任务的工作记忆
4. 展示当前任务的结构树

---

### 3.2.2 Feed Rail 顶部

展示当前任务摘要：

* 任务名称
* 任务类型
* 商品 / 品牌
* 当前状态
* 进度条
* 当前目标

例如：

```text
当前任务：氨基酸洗面奶主图策划
类型：Main Image
状态：Editing
进度：3 / 5 slots generated，1 approved
目标：高点击率、生活感、突出温和不刺激
```

---

### 3.2.3 Feed Rail 四个 Tab

---

#### Tab A：Results（结果）

显示当前任务下所有结果：

* 主图任务：5 张主图 + 变体
* 视频任务：shot list + shot variants
* 详情任务：模块列表 + 模块版本

支持展示方式：

* 瀑布流
* 列表
* 按 frame / node 分组

##### 图卡 hover 操作

* Set as Current
* Add to Chat
* Use as Reference
* Compare
* Pin
* More

---

#### Tab B：Assets（资产）

显示当前任务可用资产：

* 模板资产
* 品牌素材
* 竞品参考
* 历史优秀案例
* promoted assets
* 策略包引用素材

##### 资产操作

* Preview
* Add to Chat
* Use as Reference
* Apply Template
* Load Strategy Context

---

#### Tab C：Memory（记忆）

显示当前任务的工作记忆：

* 最近编辑请求
* 最近建议与采纳情况
* 最近执行的技能
* 最近加入过的附件
* 当前方向摘要
* 最近节点切换记录

---

#### Tab D：Structure（结构）

显示任务内部结构树：

* 主图任务：`frame -> 5 slots -> variants`
* 视频任务：`frame -> shot list -> variants`
* 详情任务：`frame -> detail modules -> variants`

这对主图 5 张、视频分镜、详情模块化都非常重要。

---

## 3.3 第三栏：Focus Workspace（焦点工作区）

中间工作区永远只聚焦当前任务中的一个“焦点节点”。

---

### 3.3.1 焦点工作区职责

* 主图：编辑某一张焦点图
* 视频：编辑某一个镜头 / 分镜节点
* 详情：编辑某一个详情模块

---

### 3.3.2 Focus Header

展示：

* 当前节点名称
* 节点角色
* 当前版本
* 来源模板
* 当前评分 / 状态

例如：

```text
当前节点：第2张 痛点对比图
版本：V3
模板：Main Image Template v2
状态：Generated
```

---

### 3.3.3 Action Bar

建议统一顶部操作条：

* Generate
* Replace
* Remove Background
* Upscale
* Expand / Crop
* Compare
* More

但根据节点类型做适配：

---

#### 主图任务 Action Bar

* Generate
* Replace
* Remove BG
* Upscale
* Expand
* Compare

#### 视频任务 Action Bar

* Rewrite Shot
* Expand Shot
* Generate Keyframe
* Regenerate Sequence
* Compare Shots

#### 详情任务 Action Bar

* Rewrite Module
* Replace Visual
* Adjust Layout
* Compare Module Versions

---

### 3.3.4 三类任务的焦点视图

---

#### A. 主图任务：Focus Canvas

* 单张图显示
* 对象 hover / 选中
* 区域框选
* 对象浮层工具
* compare strip
* version strip

##### 对象浮层建议

* Add to Chat
* Set as Primary
* Add as Secondary
* Replace
* Lock
* Remove

---

#### B. 视频任务：Shot Workspace

* 当前镜头 storyboard / 关键帧
* shot meta（场景 / 景别 / 运动 / 文案 / 口播）
* 当前镜头版本
* 左右切换上一个/下一个 shot

---

#### C. 详情任务：Module Workspace

* 当前模块预览
* 模块文案
* 模块视觉要求
* 模块卖点
* 模块布局对比

---

### 3.3.5 底部 Compare / Version Strip

所有任务类型都应有：

* 当前节点历史版本
* 候选变体对比
* 一键应用某个候选为当前版本

---

## 3.4 第四栏：Agent Workspace（多模态 Agent）

右侧是整个工作台的智能中枢。

---

### 3.4.1 Agent Workspace 职责

1. 理解当前任务与当前节点
2. 读取当前上下文记忆
3. 接收图、视频、对象、模板、策略包等附件
4. 给出 0-prompt 智能建议
5. 将建议转成 proposal
6. 调用技能执行修改
7. 输出结果并写回任务状态

---

### 3.4.2 右栏结构

```text
Agent Workspace
├── Context Header
├── Attachments Panel
├── 0-prompt Suggestions
├── Chat Thread
├── Proposal Card
├── Execution Result Card
└── Skills Tray
```

---

### 3.4.3 Context Header 展示字段

* 当前任务
* 当前节点
* 当前模板
* 当前版本
* 主对象 / 辅助对象
* 当前方向摘要
* 当前约束（品牌规则 / 锁定对象 / 模板约束）

---

### 3.4.4 Attachments Panel

可加入：

* 当前图 / 当前镜头 / 当前模块
* 参考图
* 参考视频
* 对象引用
* 区域引用
* 模板资产
* 策略包
* 品牌规则包
* 竞品图
* 历史满意版本
* Skill

每个 attachment 用 chip/card 表示，可设为：

* primary
* secondary
* supporting

---

### 3.4.5 0-prompt Suggestions

系统基于当前任务和当前节点自动给出四类建议：

1. **Next Actions**
2. **Assets**
3. **Skills**
4. **Template / Strategy**

例如：

* 建议放大主体商品
* 建议缩短标题文案
* 建议加载“温和不刺激”策略包
* 建议使用 Replace Background
* 当前卖点更适合“核心需求满足图”

---

### 3.4.6 Chat / Proposal / Result

#### Chat

用户可以输入文字，也可以拖入图/视频/对象作为上下文。

#### Proposal

Agent 输出结构化 proposal：

* summary
* target_objects
* intended_changes
* risks
* steps
* execution_mode

#### Result

执行结果返回：

* 新版本
* 对比图
* 执行说明
* 是否建议继续 refinement

---

# 4. 顶层对象模型

下面给你一版推荐的顶层域模型。

---

## 4.1 顶层层级关系

```text
WorkspaceTask
  └── WorkspacePlan
        └── Frame
              └── ResultNode
                    ├── ObjectNode
                    ├── Variant
                    ├── ConversationAttachment
                    ├── SuggestionCard
                    └── SessionMemory
```

---

## 4.2 顶层对象列表

建议新增/明确以下对象：

1. `WorkspaceTask`
2. `TaskSessionState`
3. `WorkspacePlan`
4. `Frame`
5. `ResultNode`
6. `Variant`
7. `ConversationAttachment`
8. `SkillRef`
9. `StrategyPackRef`
10. `SuggestionCard`
11. `AgentSessionMemory`

---

## 4.3 WorkspaceTask Schema

```yaml
WorkspaceTask:
  task_id: string
  task_type: main_image | video_plan | detail_page
  title: string
  description: string | null
  product_id: string | null
  brand_id: string | null
  workspace_id: string | null

  plan_id: string
  status: draft | compiling | editing | reviewing | approved | archived | failed
  priority: low | medium | high
  tags: string[]

  intent_summary: string
  goal_summary: string | null

  active_frame_id: string | null
  active_node_id: string | null
  active_variant_id: string | null

  progress:
    total_nodes: int
    generated_nodes: int
    reviewed_nodes: int
    approved_nodes: int

  unread_hint_count: int
  pending_review_count: int
  running_batch_count: int

  created_at: datetime
  updated_at: datetime
  archived_at: datetime | null
```

---

## 4.4 TaskSessionState Schema

用于恢复“任务现场”。

```yaml
TaskSessionState:
  task_id: string
  active_tab: results | assets | memory | structure
  active_node_id: string | null
  active_variant_id: string | null
  focus_mode: canvas | shot | module
  compare_variant_ids: string[]
  pinned_result_ids: string[]
  active_attachment_ids: string[]
  current_direction_summary: string | null
  recent_skill_ids: string[]
  scroll_positions:
    task_rail: number
    feed_rail: number
    focus_workspace: number
    agent_workspace: number
```

---

## 4.5 WorkspacePlan / Frame / ResultNode

沿用你当前已有模型，只建议补充任务兼容字段。

```yaml
WorkspacePlan:
  plan_id: string
  task_id: string
  intent_context: object
  compile_plan: object
  binding_summary: object
  status: active | completed | archived
```

```yaml
Frame:
  frame_id: string
  plan_id: string
  frame_type: main_image | video_shots | detail_modules
  title: string
  order_index: int
```

```yaml
ResultNode:
  node_id: string
  frame_id: string
  node_type: image | shot | detail_module
  title: string
  role: string
  status: draft | generating | generated | reviewed | approved | failed
  score_summary: object | null
  objects: ObjectNode[]
  active_variant_id: string | null
```

---

## 4.6 ConversationAttachment Schema

```yaml
ConversationAttachment:
  id: string
  task_id: string
  node_id: string | null
  type: current_image | reference_image | reference_video | object_ref | region_ref | template_asset | strategy_pack | brand_rule_pack | competitor_asset | historical_variant | skill_ref
  ref_id: string
  label: string
  role: primary | secondary | supporting
  preview_url: string | null
  payload: object
  source_scope: workspace | asset_library | task_memory | external
  pinned: boolean
  created_by: user | system | agent
  created_at: datetime
```

---

## 4.7 SkillRef Schema

```yaml
SkillRef:
  id: string
  name: string
  category: image_edit | planning | copy | brand_guard | variant | template | asset | video_edit | layout_edit
  description: string
  applicable_task_types: string[]
  applicable_node_roles: string[]
  applicable_object_roles: string[]
  input_contract: object
  output_contract: object
  trigger_mode: manual | recommended | auto
  enabled: boolean
```

---

## 4.8 SuggestionCard Schema

```yaml
SuggestionCard:
  id: string
  task_id: string
  node_id: string | null
  type: next_action | asset | skill | template_switch | strategy_pack | compare_hint
  title: string
  reason: string
  score: float
  priority: int
  target_refs: string[]
  suggested_skill_id: string | null
  suggested_attachment_ids: string[]
  suggested_params: object
  accepted: boolean
  dismissed: boolean
  created_at: datetime
```

---

## 4.9 AgentSessionMemory Schema

```yaml
AgentSessionMemory:
  session_id: string
  task_id: string
  plan_id: string
  frame_id: string | null
  node_id: string | null
  active_variant_id: string | null

  current_direction_summary: string | null
  primary_object_id: string | null
  secondary_object_ids: string[]

  active_attachment_ids: string[]
  recent_skill_ids: string[]
  recent_user_requests: string[]
  recent_applied_changes: string[]
  recent_suggestion_ids: string[]

  last_updated_at: datetime
```

---

# 5. 状态机设计

状态机分四层：

1. 任务状态机
2. 节点状态机
3. Agent 对话状态机
4. 页面 UI 状态机

---

## 5.1 任务状态机（Task Status）

```text
draft
  → compiling
  → editing
  → reviewing
  → approved
  → archived

异常分支：
compiling → failed
editing → failed
reviewing → editing
approved → editing（回退）
```

---

### 含义说明

* `draft`：任务已创建，尚未编译
* `compiling`：系统正在根据意图/模板/策略包生成任务骨架
* `editing`：进入日常编辑阶段
* `reviewing`：任务已进入人工审核或审批阶段
* `approved`：任务完成并通过
* `archived`：任务归档
* `failed`：任务执行失败，需要人工处理

---

## 5.2 节点状态机（ResultNode Status）

沿用你现有逻辑并补充回退：

```text
draft
  → generating
  → generated
  → reviewed
  → approved

失败分支：
generating → failed

回退分支：
reviewed → generated
approved → reviewed
approved → generated
```

---

## 5.3 Agent 对话状态机

```text
idle_with_suggestions
  → attachments_ready
  → chatting
  → proposal_ready
  → executing
  → result_ready

辅助分支：
proposal_ready → clarification_needed
clarification_needed → chatting
result_ready → chatting
result_ready → proposal_ready
```

---

### 含义说明

* `idle_with_suggestions`：右侧空闲，但系统已给出建议
* `attachments_ready`：上下文附件已就位
* `chatting`：用户与 Agent 对话中
* `proposal_ready`：Agent 已输出 proposal
* `clarification_needed`：需要澄清
* `executing`：正在执行技能或生成
* `result_ready`：结果完成，可继续 refinement

---

## 5.4 页面 UI 状态机

---

### Task Rail

* `collapsed`
* `expanded`
* `filtering`
* `switching_task`

### Feed Rail

* `results`
* `assets`
* `memory`
* `structure`

### Focus Workspace

* `main_image_canvas`
* `video_shot_view`
* `detail_module_view`
* `compare_mode`

### Agent Workspace

* `idle`
* `context_loaded`
* `suggesting`
* `chatting`
* `proposal_ready`
* `executing`
* `result_ready`

---

# 6. 关键交互链路

---

## 6.1 创建新任务

```text
点击 + New Task
→ 选择任务类型
→ 选择商品 / 输入目标
→ 选择模板（可选）
→ 选择策略包（可选）
→ Create
→ 创建 WorkspaceTask + WorkspacePlan
→ 进入 compiling
→ 编译完成后进入 editing
```

---

## 6.2 切换任务

```text
点击 TaskCard
→ 保存当前任务 TaskSessionState
→ 加载目标任务 TaskSessionState
→ 恢复 active node / variant / feed tab / attachments / direction summary
→ 中间切换到对应焦点节点
→ 右侧切换到对应 Agent 上下文
```

这一步是“像 Cursor 一样”的关键体验。

---

## 6.3 0-prompt 启动编辑

```text
打开某任务
→ Feed Rail 默认选中最近活跃节点
→ Focus Workspace 显示当前节点
→ Agent Workspace 自动加载上下文
→ Suggestions 出现
→ 用户点击建议
→ 生成 proposal
→ 执行
```

---

## 6.4 从结果添加到对话

```text
在 Results/Assets 中点击某图 Add to Chat
→ 生成 ConversationAttachment
→ role 默认为 supporting
→ 右侧刷新上下文
→ Agent 可直接引用
```

---

## 6.5 对象级编辑

```text
中间画布选中商品对象
→ 浮层操作：Set as Primary
→ 右侧附件增加 object_ref(primary)
→ 用户说：参考竞品图，让主体更突出
→ Agent proposal
→ apply proposal
```

---

# 7. 后端存储建议

如果你想最小改动，可新增 `workspace_tasks` 表，并保持现有 plan 表不动。

---

## 7.1 建议新增表

### `workspace_tasks`

任务顶层对象

### `workspace_task_session_state`

存储任务工作现场

### `workspace_conversation_attachments`

右侧附件

### `workspace_suggestions`

0-prompt 建议

---

## 7.2 与现有表的关系

```text
workspace_tasks
  1 -> 1 workspace_plans
  1 -> n workspace_frames
  1 -> n workspace_nodes
  1 -> n workspace_variants
  1 -> n workspace_session_events
  1 -> n workspace_suggestions
  1 -> n workspace_conversation_attachments
```

---

# 8. 前端组件树建议

---

## 8.1 页面顶层组件树

```text
GrowthLabWorkspacePage
├── WorkspaceTopbar
├── TaskRail
│   ├── TaskRailHeader
│   ├── WorkingSetPanel
│   ├── TaskCategoryTabs
│   ├── TaskSearchInput
│   └── TaskList
│       └── TaskCard
├── FeedRail
│   ├── CurrentTaskHeader
│   ├── FeedTabs
│   ├── ResultsPane
│   ├── AssetsPane
│   ├── MemoryPane
│   └── StructurePane
├── FocusWorkspace
│   ├── FocusHeader
│   ├── ActionBar
│   ├── MainImageCanvas / VideoShotView / DetailModuleView
│   └── CompareVersionStrip
├── AgentWorkspace
│   ├── ContextHeader
│   ├── AttachmentsPanel
│   ├── SuggestionsPanel
│   ├── ChatThread
│   ├── ProposalCard
│   ├── ResultCard
│   └── SkillsTray
└── BottomTimeline
```

---

# 9. API 设计建议

---

## 9.1 Task APIs

* `GET /api/workspace/tasks`
* `POST /api/workspace/tasks`
* `GET /api/workspace/task/{id}`
* `POST /api/workspace/task/{id}/rename`
* `POST /api/workspace/task/{id}/archive`
* `POST /api/workspace/task/{id}/duplicate`
* `POST /api/workspace/task/{id}/set-active`

---

## 9.2 Task Session APIs

* `GET /api/workspace/task/{id}/session-state`
* `POST /api/workspace/task/{id}/session-state`

---

## 9.3 Suggestions APIs

* `GET /api/workspace/task/{id}/node/{node_id}/suggestions`
* `POST /api/workspace/suggestion/{id}/accept`
* `POST /api/workspace/suggestion/{id}/dismiss`
* `POST /api/workspace/suggestion/{id}/propose`

---

## 9.4 Attachments APIs

* `GET /api/workspace/task/{id}/attachments`
* `POST /api/workspace/task/{id}/attachments`
* `POST /api/workspace/attachment/{id}/update-role`
* `DELETE /api/workspace/attachment/{id}`

---

# 10. AI-coding Prompt

下面给你一版可以直接喂给 Cursor / Codex 的实现提示，按批次拆开。

---

## Prompt 1：四栏工作台页面骨架

```text
请基于现有 Growth Lab 的 workspace 页面，重构为四栏工作台：

【目标】
页面从三栏升级为四栏：
1. Task Rail
2. Feed Rail
3. Focus Workspace
4. Agent Workspace

【要求】
- 顶部保留 topbar，并增强显示 current task / current node / template / strategy / status
- 最左新增 Task Rail：
  - + New Task
  - Search
  - Categories: all / main_image / video_plan / detail_page / done / archived
  - Task list
- 第二栏 Feed Rail 显示当前任务内容：
  - tabs: results / assets / memory / structure
- 第三栏 Focus Workspace 根据当前任务类型渲染不同视图：
  - main_image -> image canvas
  - video_plan -> shot workspace
  - detail_page -> module workspace
- 第四栏 Agent Workspace 包含：
  - context header
  - attachments panel
  - 0-prompt suggestions
  - chat / proposal / result / skills

【注意】
- 保持现有 workspace.html 的核心逻辑兼容
- 先实现 HTML + mock 数据，再逐步接真实接口
- 保持现有 timeline / compare / variant list 兼容
```

---

## Prompt 2：新增顶层对象模型与状态

```text
请为 Growth Lab 新增 Task-first 工作台的数据模型，并与现有 WorkspacePlan / Frame / ResultNode / Variant 兼容。

【请新增以下对象】
1. WorkspaceTask
2. TaskSessionState
3. ConversationAttachment
4. SkillRef
5. SuggestionCard
6. AgentSessionMemory

【字段要求】

WorkspaceTask:
- task_id
- task_type: main_image | video_plan | detail_page
- title
- description
- product_id
- brand_id
- workspace_id
- plan_id
- status: draft | compiling | editing | reviewing | approved | archived | failed
- priority
- tags
- intent_summary
- goal_summary
- active_frame_id
- active_node_id
- active_variant_id
- progress { total_nodes, generated_nodes, reviewed_nodes, approved_nodes }
- unread_hint_count
- pending_review_count
- running_batch_count
- created_at
- updated_at

TaskSessionState:
- task_id
- active_tab
- active_node_id
- active_variant_id
- focus_mode
- compare_variant_ids
- pinned_result_ids
- active_attachment_ids
- current_direction_summary
- recent_skill_ids
- scroll_positions

【要求】
- 使用 Pydantic
- 尽量放到 `apps/growth_lab/schemas/visual_workspace.py`
- 不破坏现有 compile / generate / review / approve 流程
```

---

## Prompt 3：任务栏与任务恢复逻辑

```text
请为 Growth Lab 实现 Task Rail 与任务恢复逻辑。

【目标】
用户可以并行创建多个任务，并在任务间切换时恢复各自的工作现场。

【请实现】
1. TaskRail 前端组件：
   - header
   - categories
   - task list
   - task card
   - create task modal

2. 后端 task API：
   - GET /api/workspace/tasks
   - POST /api/workspace/tasks
   - GET /api/workspace/task/{id}
   - POST /api/workspace/task/{id}/rename
   - POST /api/workspace/task/{id}/archive
   - POST /api/workspace/task/{id}/duplicate
   - POST /api/workspace/task/{id}/set-active

3. 任务会话恢复：
   - GET /api/workspace/task/{id}/session-state
   - POST /api/workspace/task/{id}/session-state

【核心要求】
- 切换任务前先保存当前 task session
- 切换任务后恢复 active node / active variant / active tab / attachments / direction summary
- 主图 / 视频 / 详情三类任务共享同一 task rail
```

---

## Prompt 4：按任务类型渲染 Focus Workspace

```text
请改造现有 Focus Workspace，使其支持三类任务的专属中间编辑视图：

【任务类型】
1. main_image
2. video_plan
3. detail_page

【渲染要求】
- main_image:
  - 单图焦点画布
  - 对象选中
  - 区域框选
  - action bar
  - compare/version strip

- video_plan:
  - 当前 shot 的 storyboard / keyframe / meta 信息
  - 支持切换 shot
  - 支持 rewrite shot / regenerate shot / compare shot

- detail_page:
  - 当前 detail module 预览
  - 模块文案与视觉要求展示
  - 支持 rewrite module / replace visual / compare module versions

【要求】
- 统一 FocusWorkspace 外层组件
- 内部根据 current task type 切换具体 renderer
- 保持与右侧 Agent Workspace 的 node 上下文一致
```

---

## Prompt 5：Agent Workspace 与 0-prompt 建议

```text
请将现有右栏升级成 Task-aware 的 Agent Workspace。

【结构】
1. ContextHeader
   - current task
   - current node
   - template
   - active variant
   - direction summary
   - constraints

2. AttachmentsPanel
   - supports current image/video/module, refs, template assets, strategy packs, skills
   - supports primary / secondary / supporting roles

3. SuggestionsPanel
   - next actions
   - assets
   - skills
   - template/strategy suggestions

4. ChatThread + ProposalCard + ResultCard + SkillsTray

【后端】
新增 suggestions 相关服务与 API：
- GET /api/workspace/task/{id}/node/{node_id}/suggestions
- POST /api/workspace/suggestion/{id}/accept
- POST /api/workspace/suggestion/{id}/dismiss
- POST /api/workspace/suggestion/{id}/propose

【建议生成信号】
- current task type
- current node role
- current template
- current attachments
- recent user actions
- direction summary
- current visual or script state

【要求】
- 优先规则 + ranking 实现
- 保留 LLM reasoner 扩展点
- suggestions 使用 SuggestionCard 结构
```

---

## Prompt 6：数据库与存储升级

```text
请为 Growth Lab 增加 Task-first 工作台所需的存储层。

【目标】
在不破坏现有 growth_lab_store 的基础上，新增：
1. workspace_tasks
2. workspace_task_session_states
3. workspace_conversation_attachments
4. workspace_suggestions

【要求】
- 兼容 SQLite
- 尽量沿用现有 storage 风格
- 提供 CRUD 方法
- 提供从 task_id 追踪到 plan / frames / nodes / variants 的聚合查询
- 提供任务列表查询（支持 type / status / keyword）
```

---

# 11. 推荐实施顺序

建议分 4 个 Batch。

---

## Batch 1：任务层接入

* 新增 `workspace_tasks`
* 前端加 Task Rail
* 支持多任务切换
* 支持恢复现场

## Batch 2：Feed Rail 按任务绑定

* Results / Assets / Memory / Structure 四 tab
* 与 task 绑定

## Batch 3：Focus Workspace 多任务类型适配

* main image / video / detail 三种 renderer

## Batch 4：Agent Workspace task-aware 升级

* Attachments
* Suggestions
* Proposal
* 0-prompt
* 建议转执行

---

# 12. 一句话总结

这版四栏工作台的核心不是“多加一个左边栏”，而是把整个 Growth Lab 从“结果编辑器”升级为：

> **一个以任务为顶层容器、以结果流为操作面、以焦点工作区为执行面、以 Agent 为智能中枢的内容策划工作台。**

它解决的是四个层次的问题：

* **Task Rail**：我现在在做什么任务？
* **Feed Rail**：这个任务下有哪些结果、资产、记忆、结构？
* **Focus Workspace**：我当前具体在改哪个焦点结果？
* **Agent Workspace**：AI 如何基于上下文帮助我更快更好完成当前任务？

