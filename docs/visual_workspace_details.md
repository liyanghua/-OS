

# 《Visual Result Workspace》

**面向主图 / 详情模块 / 视频镜头的 AI-native 结果工作台**

它的核心不是自由编辑，而是：

* 承接编译台输出
* 显示模板与策略绑定
* 让用户围绕某个结果节点快速修改
* 统一对象编辑、模块编辑、分镜编辑
* 形成版本、评估与资产沉淀

---

# 一、产品定义

## 1.1 定位

Visual Result Workspace 是内容编译平台的结果装配与编辑中枢。
它把：

* 用户意图
* 模板绑定
* 编译计划
* 结果节点
* 对象化画布
* AI 编辑执行
* 版本与评估

统一到一个工作界面中，帮助用户快速得到“可用结果”。

---

## 1.2 适用输出类型

统一支持 3 类结果节点：

1. **Main Image Node**

   * 主图第 1 张、第 2 张……
2. **Detail Module Node**

   * 详情模块 1、模块 2……
3. **Video Shot Node**

   * 视频镜头 1、镜头 2……

统一抽象后，页面不用分裂成三套系统。

---

# 二、高保真页面结构

我建议是一屏 **Header + 左中右 + Bottom Rail** 的结构。

---

## 2.1 整体骨架

```text id="5i8x5m"
┌──────────────────────────────────────────────────────────────────────────────┐
│ Header                                                                       │
│ 任务标题 | 输出类型 | 当前节点 | 意图摘要 | 模板绑定 | 重新编译 | 发布        │
├──────────────────────┬──────────────────────────────────┬────────────────────┤
│ Left Context Rail    │ Main Result Workspace            │ Right AI Rail       │
│                      │                                  │                    │
│ Tab1 用户意图         │ 顶部：节点导航 / 结果切换 / 对比模式 │ 当前上下文卡         │
│ Tab2 模板与策略       │ 中部：结果主视图                 │ 推荐动作区           │
│ Tab3 编译计划         │ 底部：变体带 / 子结果 / 参考素材    │ 对话编辑器           │
│ Tab4 结构树           │                                  │ 执行提案 / 风险提示   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Bottom Rail: 版本时间线 | 评估分数 | 审核状态 | 资产沉淀 | 下一步动作             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.2 Header 设计

### Header 左侧

* 项目名
* 任务名
* 商品名
* 输出类型标签

  * 主图
  * 详情
  * 视频

### Header 中部

* 当前节点路径

  * 例：主图任务 / 第 2 张 / 痛点对比图
  * 例：详情任务 / 模块 3 / 特殊材料
  * 例：视频任务 / 镜头 5 / 核心卖点响应

### Header 右侧

按钮：

* 重新编译
* 更换模板
* 批量出变体
* 对比结果
* 发布到计划板
* 沉淀为模板样例

### Header 下方一条 Strategy Strip

显示：

* 人群
* 场景
* 核心卖点
* 风格要求
* 品牌约束
* 当前绑定模板

示例：

```text id="f0oq5k"
18-29女性 ｜ 氨基酸洗面奶 ｜ 温和不刺激 ｜ 真实生活感 ｜ 商品颜色不可偏移 ｜ 主图5张模板v2
```

---

# 三、左侧：Context Rail 高保真设计

左侧不是素材栏，而是“上下文与结构控制区”。

建议做成 4 个 Tab。

---

## Tab 1：用户意图

### 作用

展示来自编译台的结构化意图，并允许轻编辑。

### 组件区块

1. **Intent Summary Card**

   * 商品
   * 输出类型
   * 数量
   * 面向人群
   * 风格参考
   * 场景参考

2. **Must / Avoid Card**

   * 必须呈现
   * 避免元素
   * 风险点

3. **Intent Actions**

   * 编辑意图
   * 追加要求
   * 刷新编译

### 示例内容

```text id="yc1tv7"
商品：氨基酸洗面奶
输出：5张主图
人群：18-29岁女性
风格：都市白领公寓，真实生活感
必须包含：产品特写 / 使用状态 / 场景全景
避免：过强广告感 / 颜色失真
```

---

## Tab 2：模板与策略

### 作用

让用户看到“系统为什么这样生成”。

### 组件区块

1. **Template Binding Card**

   * 主模板
   * 子模板
   * 品牌模板
   * 绑定原因

2. **Strategy Object Card**

   * 当前节点目标
   * 当前卖点
   * 当前情绪
   * 当前表达类型

3. **Constraint Card**

   * logo 保护
   * 商品 identity 保真
   * 文案限制
   * 版式限制

4. **Template Actions**

   * 更换当前模板
   * 只替换子模板
   * 锁定策略
   * 查看模板说明

### 示例

```text id="r5jlxj"
主模板：主图5张叙事模板
子模板：第2张-痛点放大对比图
品牌模板：通用日化详情表达模板
当前卖点：洗后不紧绷
当前目标：强化差异对比
```

---

## Tab 3：编译计划

### 作用

让用户看到系统的执行计划，不是随机生成。

### 组件区块

1. **Compile Plan Summary**

   * 计划名称
   * 输出节点数量
   * 生成顺序
   * 评估规则

2. **Node Plan List**

   * 每个结果节点的标题
   * 节点目标
   * 状态
   * 是否已生成

3. **Plan Actions**

   * 重新编译当前节点
   * 重新编译全案
   * 调整节点顺序

### 主图例子

```text id="m95lhg"
1. 场景直击图
2. 痛点对比图
3. 需求满足图
4. 功能对比图
5. 信任背书图
```

### 详情例子

```text id="jitj0u"
1. 吸引注意
2. 独特设计
3. 特殊材料
4. 先进工艺
...
```

### 视频例子

```text id="80xwob"
1. 强痛点开场
2. 对比反差
3. 核心卖点响应
4. 多场景复用
5. 行动号召
```

---

## Tab 4：结果结构树

### 作用

从“计划节点”进入“可编辑对象”。

### 层级结构

建议为两层树：

#### 第一层：ResultNode

* 图 1 / 模块 3 / 镜头 5

#### 第二层：Node内部对象

* 主体商品
* 人物
* 背景
* 文案区
* 标签区
* 道具
* 辅助元素

### 支持操作

* 选中节点
* 选中对象
* 锁定对象
* 隐藏对象
* 查看属性

---

# 四、中间：Main Result Workspace 高保真设计

中间区不是单一画布，而是“节点工作区”。

---

## 4.1 顶部：Node Navigator

### 区块

* 左右切换节点
* 当前节点名
* 节点类型标签
* 当前节点状态
* 快速切换模式

### 模式切换

* 编辑模式
* 预览模式
* 对比模式
* 全案模式

---

## 4.2 中部：Result Main View

按输出类型渲染不同主视图，但交互逻辑统一。

---

### A. 主图模式

#### 视觉结构

* 上方一排 5 张图位缩略条
* 中间大画布
* 右上角当前模板说明按钮
* 底部变体带

#### 主画布能力

* 对象选中
* 区域框选
* zoom / pan
* 显示对象标签
* 显示禁改区
* 显示文字安全区

#### 附加区块

* 当前图位说明卡
* 当前图位目标
* 当前图位文案摘要

---

### B. 详情模式

#### 视觉结构

* 左侧详情模块目录
* 中间当前模块画布
* 顶部可切整页预览 / 模块预览
* 底部显示上/下模块关系

#### 主能力

* 模块级编辑
* 局部对象编辑
* 文案区编辑
* 模块顺序切换
* 模块版式替换

---

### C. 视频模式

#### 视觉结构

* 顶部分镜序列条
* 中间当前镜头 storyboard / keyframe
* 下方 shot list table
* 右下角口播/运镜联动说明

#### 主能力

* 镜头级编辑
* 关键帧画面调整
* 分镜文案联动
* 运镜建议切换
* 镜头变体生成

---

## 4.3 底部：Variant Strip

统一在中间主区底部展示当前节点的变体。

### 每个变体卡显示

* 缩略图 / 卡面
* 变体标签
* 主要差异
* 当前评分
* 推荐标记

### 支持操作

* 设为当前版本
* 与主版本对比
* 继续编辑此变体
* 标记候选

---

# 五、右侧：AI Rail 高保真设计

右侧不是聊天区，而是 AI 执行控制台。

---

## 5.1 Current Context Card

显示：

* 当前任务
* 当前节点
* 当前对象/区域
* 当前模式
* 当前约束
* 当前可执行动作

示例：

```text id="tzj4ur"
当前节点：第2张 痛点对比图
当前对象：右侧本品效果区
当前约束：商品颜色保真 / 不改logo / 可调背景 / 可调文案
可执行：增强差异 / 换文案 / 降低刺激感视觉 / 出3个变体
```

---

## 5.2 Suggested Actions

建议动作必须由 4 个维度共同驱动：

* 用户意图
* 当前模板
* 当前节点目标
* 当前评估结果

### 示例 chips

* 强化对比
* 放大主体
* 背景更生活化
* 文案更克制
* 提升高级感
* 减少文字占比
* 只优化当前节点
* 生成 3 个轻微变体

---

## 5.3 Chat Editor

### 输入框上方固定显示

* 当前节点
* 当前模板
* 当前选中对象/区域

### 输入提示

* “右边本品效果更温和一点”
* “标题更短，突出洗后不紧绷”
* “背景换成更真实的洗手台”
* “这个镜头更像真实买家秀”

### AI 回复形式

不是纯文字，而是 **Proposal Card**。

---

## 5.4 Execution Proposal Card

每次 AI 理解请求后，输出提案卡：

### 提案卡结构

1. **理解摘要**
2. **修改对象**
3. **执行步骤**
4. **预期影响**
5. **风险提醒**
6. **操作按钮**

### 例子

```text id="6y4n5c"
我理解你希望当前第2张主图右侧“本品使用后”区域看起来更柔和、更舒服，
同时缩短标题，保持差异对比但避免过强刺激感。

执行步骤：
1. 调整右侧肤感表现与光线
2. 降低左右对比的刺激色强度
3. 将标题压缩为更短表达

影响对象：
- 右侧人物肤感区域
- 标题文案区
- 差异标签区

风险：
- 对比过弱会削弱卖点表达
```

按钮：

* 直接执行
* 分步执行
* 只生成预览
* 取消

---

## 5.5 Execution Log / Result Diff

执行后自动插入：

* 修改前后摘要
* 新 revision
* 分数变化
* 是否推荐继续沿此方向优化

---

# 六、Bottom Rail 设计

底部横条是结果状态与沉淀区。

---

## 6.1 Version Timeline

显示：

* V1 初版
* V2 模板替换
* V3 对象编辑
* V4 文案优化
* V4-A 变体
* V4-B 变体

支持：

* 切换
* 对比
* 回退
* 标记推荐

---

## 6.2 Eval Score Cluster

显示关键分数：

* 平台适配度
* 卖点清晰度
* 主体突出度
* 品牌一致性
* 广告感
* 视觉杂乱度

并显示相对上一版变化：

* ↑ / ↓

---

## 6.3 Workflow Status

* 草稿
* 编辑中
* 待审核
* 已通过
* 已沉淀

---

## 6.4 Next Actions

按钮：

* 提交审核
* 加入资产库
* 生成同模板新方案
* 发布到计划板
* 导出结果

---

# 七、关键组件清单

下面给你按模块拆组件。

---

## 7.1 Page Shell

* `VisualResultWorkspacePage`
* `WorkspaceHeader`
* `StrategyStrip`
* `BottomRail`

---

## 7.2 Left Context Rail

* `ContextRail`
* `IntentTab`
* `TemplateStrategyTab`
* `CompilePlanTab`
* `ResultTreeTab`
* `IntentSummaryCard`
* `TemplateBindingCard`
* `ConstraintCard`
* `CompileNodeList`
* `ResultNodeTree`

---

## 7.3 Main Result Workspace

* `NodeNavigator`
* `ResultMainView`
* `MainImageWorkspace`
* `DetailModuleWorkspace`
* `VideoShotWorkspace`
* `CanvasViewport`
* `ObjectOverlayLayer`
* `RegionSelectionLayer`
* `StoryboardPanel`
* `DetailModulePreview`
* `VariantStrip`

---

## 7.4 Right AI Rail

* `AIRail`
* `CurrentContextCard`
* `SuggestedActionsPanel`
* `ChatEditor`
* `ProposalCard`
* `ExecutionLogPanel`
* `RiskFlagsCard`

---

## 7.5 Bottom Rail

* `VersionTimeline`
* `EvalScoreCluster`
* `WorkflowStatusBadge`
* `NextActionBar`

---

# 八、统一对象模型建议

这里重点给页面运行时会用到的对象。

---

## 8.1 ResultNode

```yaml id="zk85h7"
ResultNode:
  id: string
  type: main_image | detail_module | video_shot
  title: string
  objective: string
  template_binding_id: string
  strategy_object_id: string
  current_revision_id: string
  child_object_ids: string[]
  status: draft | generating | editable | reviewing | approved | archived
  order_index: integer
```

---

## 8.2 IntentContext

```yaml id="3f6pj2"
IntentContext:
  id: string
  product_name: string
  category: string
  output_type: main_images | detail_page | video_script
  output_count: integer
  audience: string
  style_refs: string[]
  scenario_refs: string[]
  must_have: string[]
  avoid: string[]
  raw_prompt: string
```

---

## 8.3 TemplateBinding

```yaml id="jlwm11"
TemplateBinding:
  id: string
  primary_template_id: string
  sub_template_id: string | null
  brand_template_id: string | null
  binding_reason: string
  locked_fields: string[]
  constraint_rules: string[]
```

---

## 8.4 StrategyObject

```yaml id="4gr65d"
StrategyObject:
  id: string
  node_id: string
  core_claim: string
  supporting_claims: string[]
  target_emotion: string
  visual_goal: string
  copy_goal: string
  layout_guideline: string
  platform_goal: string
```

---

## 8.5 WorkspaceSelectionContext

```yaml id="4ropoz"
WorkspaceSelectionContext:
  mode: scene | node | object | region
  active_node_id: string
  selected_object_id: string | null
  selected_region_id: string | null
  editable_actions: string[]
  effective_constraints: string[]
```

---

## 8.6 RevisionNode

```yaml id="q8o2gx"
RevisionNode:
  id: string
  result_node_id: string
  parent_revision_id: string | null
  branch_name: string | null
  trigger_type: initial_compile | template_switch | ai_edit | manual_adjust | variant_generation
  diff_summary: string
  asset_ref: string
  eval_scores:
    platform_fit: number
    salience: number
    brand_match: number
    clutter: number
    ad_feel: number
    message_clarity: number
  status: draft | candidate | recommended | approved | rejected
  created_at: datetime
```

---

## 8.7 Proposal

```yaml id="3nr2ak"
Proposal:
  id: string
  node_id: string
  selection_context: string
  summary: string
  actions:
    - action_type: string
      target_ref: string
      params: object
  expected_effect: string[]
  risk_flags: string[]
  requires_confirmation: boolean
  status: draft | confirmed | running | done | failed
```

---

# 九、状态机 Schema

下面给你 4 个核心状态机。

---

## 9.1 Workspace 全局状态机

```text id="58cwuh"
idle
→ loading_context
→ ready
→ editing
→ proposing
→ executing
→ reviewing
→ approved
→ archived
```

### 说明

* `idle`：尚未加载
* `loading_context`：加载意图、模板、节点
* `ready`：可浏览
* `editing`：用户正在编辑
* `proposing`：AI 生成提案
* `executing`：执行修改
* `reviewing`：查看结果与评分
* `approved`：节点已确认
* `archived`：任务关闭

---

## 9.2 ResultNode 状态机

```text id="7onh0f"
draft
→ compiling
→ generated
→ editable
→ candidate
→ reviewing
→ approved
↘ rejected
```

### 触发条件

* `draft -> compiling`：开始生成
* `compiling -> generated`：初版完成
* `generated -> editable`：进入工作台编辑
* `editable -> candidate`：形成候选版本
* `candidate -> reviewing`：提交审核
* `reviewing -> approved/rejected`

---

## 9.3 Edit Session 状态机

```text id="q0twnm"
idle
→ selecting_context
→ inputting_request
→ parsing_intent
→ proposal_ready
→ executing
→ revision_created
→ comparing
→ back_to_editing
```

### 说明

* `selecting_context`：选节点/对象/区域
* `inputting_request`：输入自然语言
* `parsing_intent`：AI 解析
* `proposal_ready`：提案卡可执行
* `executing`：执行动作
* `revision_created`：生成新版本
* `comparing`：与旧版本比较
* `back_to_editing`：继续下一轮

---

## 9.4 Template Binding 状态机

```text id="ajqf8s"
unbound
→ matched
→ applied
→ adjusted
→ locked
```

### 说明

* `unbound`：未匹配模板
* `matched`：系统推荐模板
* `applied`：已应用
* `adjusted`：用户局部替换
* `locked`：不允许自动切换

---

# 十、关键页面交互流

---

## 10.1 从编译台进入

```text id="yei97v"
编译台提交
→ 生成 IntentContext + TemplateBinding + CompilePlan
→ 创建 ResultNodes
→ 自动生成每个节点初版
→ 打开工作台，默认落在第一个节点
→ 用户浏览、切换、编辑
```

---

## 10.2 从节点编辑

```text id="t1ll0w"
用户选择第2张主图
→ 系统加载 node strategy + object tree + current revision
→ 用户点选右侧对象
→ 输入“右边更柔和一些”
→ 解析为 Proposal
→ 用户确认执行
→ 生成新 revision
→ 更新版本时间线和评分
```

---

## 10.3 更换模板

```text id="yb0dd2"
用户在模板 tab 点击“替换当前子模板”
→ 选择新模板
→ 系统生成 template switch proposal
→ 生成分支 revision
→ 用户比较前后差异
→ 选定其一
```

---

## 10.4 资产沉淀

```text id="65ct9h"
节点通过
→ 生成结果卡
→ 写入模板样例 / 资产图谱
→ 记录模板、意图、评分、最终版本
```

---

# 十一、AI-coding Prompt

下面给你 6 组可以直接喂给 Codex / Cursor 的 Prompt。

---

## Prompt 1：实现 Visual Result Workspace 页面骨架

```text id="9tow2c"
你是资深前端架构师 + AI-native 产品工程师。

请实现一个 Visual Result Workspace 页面，服务于“内容编译平台”的结果工作台场景。

【定位】
这个页面不是通用画布，也不是普通聊天页，而是一个承接：
- 用户意图
- 模板绑定
- 编译计划
- 结果节点（主图/详情模块/视频镜头）
- AI 编辑执行
- 版本评估
的统一工作界面。

【技术栈】
- Vue 3 + TypeScript
- Pinia
- Vue Router
- 暗色/浅色都可，优先简洁专业的工作台风格
- 使用 mock data，先不接真实后端

【页面结构】
1. Header
   - 项目名、任务名、商品名
   - 输出类型标签
   - 当前节点路径
   - Strategy Strip
   - 按钮：重新编译 / 更换模板 / 批量出变体 / 发布

2. Left Context Rail
   - Tab1 用户意图
   - Tab2 模板与策略
   - Tab3 编译计划
   - Tab4 结果结构树

3. Main Result Workspace
   - Node Navigator
   - Result Main View
   - Variant Strip

4. Right AI Rail
   - Current Context Card
   - Suggested Actions
   - Chat Editor
   - Proposal Card
   - Execution Log

5. Bottom Rail
   - Version Timeline
   - Eval Scores
   - Workflow Status
   - Next Actions

【输出要求】
请输出：
1. 前端目录结构
2. 页面主组件代码
3. 关键子组件代码
4. mock schema
5. mock data
6. 状态管理设计
```

---

## Prompt 2：实现 Left Context Rail

```text id="1fdvj2"
请实现 Visual Result Workspace 的左侧 Context Rail，使用 Vue3 + TypeScript。

【目标】
左栏是“上下文与结构控制区”，不是素材栏。

【包含 4 个 Tab】
1. 用户意图
2. 模板与策略
3. 编译计划
4. 结果结构树

【每个 Tab 要求】
- 用户意图：展示结构化 prompt、must have、avoid
- 模板与策略：展示 template binding、strategy object、constraints
- 编译计划：展示 plan summary 和 result node list
- 结果结构树：展示 ResultNode -> child objects 的树状结构，支持选中节点、选中对象

【事件要求】
- 点击 ResultNode，通知主区切换当前节点
- 点击 object，通知右栏切换当前上下文
- 点击“替换模板”，抛出 template-switch 事件
- 点击“刷新编译”，抛出 recompile 事件

【输出】
- 组件拆分
- 类型定义
- 示例数据
- 事件流设计
```

---

## Prompt 3：实现 Main Result Workspace 的三种模式

```text id="z89t8v"
请实现 Visual Result Workspace 中间主区，统一支持三种 ResultNode 类型：

1. main_image
2. detail_module
3. video_shot

【要求】
- 统一由 ResultMainView 根据当前 node.type 进行渲染
- main_image 模式：支持缩略图条 + 大画布 + 变体带
- detail_module 模式：支持模块预览 + 局部对象编辑入口
- video_shot 模式：支持 storyboard + shot list + 当前镜头视图

【重要要求】
- 三种模式的交互风格要一致
- 都要支持 current node info、selection state、variant selection
- 当前 node 改变时，主区刷新
- 支持 compare mode

【技术要求】
- Vue3 + TS
- 主图模式可使用 mock 画布
- 详情和视频模式先用结构化卡片模拟

【输出】
- 组件代码
- 渲染策略
- 当前 node 与 selection 的接线逻辑
```

---

## Prompt 4：实现 Right AI Rail 与 Proposal 流程

```text id="lmpq54"
请实现 Visual Result Workspace 的右侧 AI Rail。

【定位】
这是 AI 编辑执行控制台，不是普通聊天框。

【组件要求】
1. CurrentContextCard
2. SuggestedActionsPanel
3. ChatEditor
4. ProposalCard
5. ExecutionLogPanel

【输入】
- 当前 node
- 当前 selection context
- 当前 template binding
- 当前 strategy object
- 当前 revision eval scores

【行为要求】
- 根据 node + template + eval 生成 suggested actions
- 用户输入后先进入 parse 阶段
- 不直接执行，先生成 ProposalCard
- ProposalCard 包含：
  - summary
  - target objects
  - actions
  - expected effect
  - risk flags
  - buttons: 执行 / 分步 / 取消 / 只预览
- 点击执行后创建新的 revision，并写入 execution log

【先用 mock planner】
根据关键词将请求映射为 action_type：
- 背景 → replace_background
- 放大主体 → enhance_subject
- 文案更短 → rewrite_copy
- 更高级感 → restyle_scene
- 出变体 → generate_variants

【输出】
- 组件代码
- mock planner 逻辑
- proposal state flow
- execution log mock 数据
```

---

## Prompt 5：实现状态机与 Pinia Store

```text id="l93b5j"
请为 Visual Result Workspace 实现完整的前端状态管理与状态机。

【请实现以下对象】
- IntentContext
- TemplateBinding
- StrategyObject
- ResultNode
- WorkspaceSelectionContext
- RevisionNode
- Proposal

【请实现以下 store 能力】
1. 加载 workspace context
2. 切换 current node
3. 切换 selection context
4. 创建 proposal
5. 执行 proposal
6. 生成 revision
7. 切换 revision
8. 标记 node approved
9. 切换 template binding

【请实现以下状态机】
- workspace state
- result node state
- edit session state
- template binding state

【输出】
1. TypeScript 类型定义
2. Pinia store
3. selector/getter
4. mock builder
5. 状态流转说明
```

---

## Prompt 6：输出后端接口契约

```text id="2nnn24"
请为 Visual Result Workspace 输出一版前后端接口契约设计。

【目标】
这个页面需要对接：
- 编译台
- 模板中心
- 图像编辑执行器
- 版本与评估系统
- 资产沉淀系统

【需要的接口】
1. 获取 workspace context
2. 获取 result nodes
3. 获取某个 node 的 current revision
4. 切换模板绑定
5. 生成 proposal
6. 执行 proposal
7. 生成 variants
8. 获取 eval scores
9. 提交审核
10. 沉淀为模板样例

【请输出】
- REST API 列表
- 请求/响应 schema
- 错误码
- 异步任务模型
- 前端 adapter 设计
- revision 与 asset 的存储建议
```

---

# 十二、推荐前端目录结构

```text id="n7k2hl"
src/
  pages/
    visual-result-workspace/
      VisualResultWorkspacePage.vue

  components/
    visual-result-workspace/
      header/
        WorkspaceHeader.vue
        StrategyStrip.vue

      left-rail/
        ContextRail.vue
        IntentTab.vue
        TemplateStrategyTab.vue
        CompilePlanTab.vue
        ResultTreeTab.vue
        cards/
          IntentSummaryCard.vue
          TemplateBindingCard.vue
          ConstraintCard.vue
          StrategyObjectCard.vue
          CompilePlanSummaryCard.vue

      main-workspace/
        NodeNavigator.vue
        ResultMainView.vue
        main-image/
          MainImageWorkspace.vue
          CanvasViewport.vue
          ObjectOverlayLayer.vue
          VariantStrip.vue
        detail-module/
          DetailModuleWorkspace.vue
          DetailModulePreview.vue
        video-shot/
          VideoShotWorkspace.vue
          StoryboardPanel.vue
          ShotListTable.vue

      right-rail/
        AIRail.vue
        CurrentContextCard.vue
        SuggestedActionsPanel.vue
        ChatEditor.vue
        ProposalCard.vue
        ExecutionLogPanel.vue
        RiskFlagsCard.vue

      bottom-rail/
        BottomRail.vue
        VersionTimeline.vue
        EvalScoreCluster.vue
        WorkflowStatusBadge.vue
        NextActionBar.vue

  domain/
    types/
      visual-result-workspace.ts
    services/
      mockPlanner.ts
      suggestionEngine.ts
      revisionManager.ts
      templateBindingManager.ts

  stores/
    visualResultWorkspaceStore.ts

  mock/
    visualResultWorkspaceMock.ts

  adapters/
    visualResultWorkspaceApi.ts
```

---

# 十三、落地优先级建议

## P0

* 页面骨架
* 4 个左栏 tab
* 当前节点切换
* 右栏 proposal 流
* revision timeline
* mock 三种节点模式

## P1

* 模板切换分支
* eval score 联动
* compare mode
* 资产沉淀入口

## P2

* 真正接图像编辑器
* 真正接视频镜头 planner
* 真正接模板中心与编译台
* 自动评估回流

---

# 十四、这版设计的关键价值

这版最大的优化不是更复杂，而是把四件事统一了：

* **用户意图**
* **模板绑定**
* **编译计划**
* **当前结果节点**

这样用户看到的不是一张孤立图，而是：

> 我为什么得到这个结果、我当前正在编辑哪个节点、它应用了什么模板、下一步应该怎么改。
