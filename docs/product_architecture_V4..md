

# 《AI Agent 交互升级 V2：从 Agent 功能清单到产品能力地图》

我会直接按你已经收敛好的 4 个页面来落，不再抽象谈 chat / council / pipeline，而是回答：

**在这 4 个页面里，AI 到底应该承担什么系统角色，哪些能力该前台可见，哪些该退到后台编排。**

同时我会把它和前面三个参考方向对应起来：

* **Chance**：对象优先、视觉优先、零 prompt 起步、围绕当前对象持续理解。([Chance AI][1])
* **Veeso**：从内容直接编译出 production-ready、可编辑的设计与交付物。([Veeso AI][2])
* **Lovart**：统一设计代理与创意工作面，强调一个画布里的协作与生成。([Lovart][3])

---

# 一、V2 的总判断

你们现在已经把页面收敛成 4 个核心 workspace，这是非常正确的一步。
这意味着产品心智已经从：

**“很多 Agent 模式”**

收敛成：

**“围绕 4 类核心对象工作的 4 个工作台”**

这正是 V2 的关键起点。

所以接下来，AI Agent 交互升级不应该继续以：

* chat 更强
* council 更多角色
* pipeline 更自动

为主叙事，而应该变成：

## **面向 4 个 Workspace 的产品能力地图**

也就是：

* Opportunity Workspace：AI 帮你判断机会
* Planning Workspace：AI 帮你收敛策略
* Creation Workspace：AI 帮你共创方案
* Asset Workspace：AI 帮你生产与交付

---

# 二、V2 的产品重新定义

## 2.1 产品定位

## **AI-native 内容策划编译与执行工作台**

不是：

* 通用聊天产品
* 通用视觉搜索产品
* 通用设计生成器

而是：

**围绕机会、brief、strategy、plan、asset 五类核心对象，AI 与人协作完成从判断到编译到交付的工作流系统。**

---

## 2.2 V2 的核心升级目标

从旧版本的：

## “AI 是很多功能按钮背后的工具”

升级成：

## “AI 是每个 Workspace 的原生系统能力”

也就是说，AI 不再只是：

* 一个聊天入口
* 一个分析按钮
* 一个讨论模式

而是每个页面的：

* 上下文装配器
* 阶段健康检查器
* 决策建议器
* 可执行动作生成器
* 编译器
* 记忆与复盘器

---

# 三、从 Agent 功能清单到能力地图

下面是 V2 最核心的六层能力地图。
这六层不是独立页面，而是会映射到 4 个 Workspace。

---

## Layer 1：Context OS

### 作用

统一 AI 所见上下文，让任何 Agent 都在同一个项目语境里工作，而不是吃碎片。

### 解决的问题

你之前已经明确提到：

* `run-agent`、`chat`、`council` 各自独立
* Council 结论不会自动流入后续策略
* 上下文丢失快

### V2 定义

所有页面的 AI 行为都必须先经过：

## `PlanningContextAssembler`

统一组装：

* 当前页面核心对象
* 上游对象摘要
* 下游状态
* 最近 Council 共识
* 当前 open questions
* 当前阶段 health issues
* 项目级记忆

### 对标参考

Chance 的核心不是聊天，而是“围绕当前看到的对象理解世界”；你们这里的“对象”不是相机画面，而是机会卡、Brief、Strategy、Plan、Asset。([Chance AI][1])

---

## Layer 2：Stage OS

### 作用

把每个页面从“静态编辑页”升级成“带健康度、完成度、建议动作的阶段操作系统”。

### 解决的问题

你之前也指出：

* AI 目前是被动的
* Brief 缺关键字段时系统不会提醒
* 用户不知道下一步该做什么

### V2 定义

每个 Workspace 顶部都应该有统一的：

## `Stage Header`

包含：

* 当前阶段分数
* blockers
* warnings
* next best action
* quick actions

对应能力：

* `StageHealthChecker`
* `NextStepAdvisor`

### 产品意义

AI 不只是“会回答”，而是：

## **会判断当前阶段状态，并主动推进**

---

## Layer 3：Decision OS

### 作用

让 AI 帮用户形成判断，而不是只输出解释。

### 解决的问题

* 单次分析、Council、多轮对话相互割裂
* Council 输出是文字，不是可应用结果
* 路由不稳定

### V2 定义

所有高级分析能力最终都要产出三类结构化结果：

* `consensus`
* `disagreements`
* `proposed_actions / diffs`

Council 不再是一个“特别的聊天模式”，而是：

## **结构化分歧求解器**

LeadAgent 也不再只是“猜你想问什么”，而是：

## **页面感知 + 意图感知的决策路由器**

---

## Layer 4：Action OS

### 作用

把所有 AI 输出统一翻译成“可执行动作”。

### 解决的问题

你已经明确指出现在最大问题之一是：

* 结果只有 explanation
* 用户需要自己理解并手动修改
* action chips 还不统一

### V2 定义

建立统一 `ActionSpec`：

* `action_type`
* `target_object`
* `target_field`
* `label`
* `description`
* `preview_diff`
* `confirmation_required`
* `api_endpoint`
* `payload`

任何 AI 来源：

* run-agent
* council
* advisor
* chat
* health checker

最后都只输出两类结果：

* insight
* action

### 产品意义

把系统从：
**建议型 AI**
升级成：

## **可执行型 AI**

---

## Layer 5：Compiler OS

### 作用

把机会和策略真正编译成可交付产物，而不是停在文本建议。

### 解决的问题

* 当前很多结果还是文字说明
* 用户还要自己再理解和转译
* plan 到 asset 之间还缺更强的编译语义

### V2 定义

V2 必须坚持：

## **所有生成都从对象派生**

不是从 prompt 自由发挥。

对象链：

* OpportunityCard
* OpportunityBrief
* RewriteStrategy
* NewNotePlan
* AssetBundle

再派生：

* 标题
* 正文
* ImageExecutionBrief
* VariantSet
* ExportPackage

### 对标参考

Veeso 的价值就在于“Content in, Design out”，而且强调 production-ready、editable。你们应该借鉴的是“编译思维”，不是做成通用设计工具。([Veeso AI][2])

---

## Layer 6：Collaboration OS

### 作用

让人和 AI 围绕同一对象协作，而不是各干各的。

### 解决的问题

* 现在还是按钮式触发
* 实时协同不够
* 修改后的连锁影响没被系统感知
* review loop 还没完整闭环

### V2 定义

协作能力包括：

* Guided Workflow
* 实时字段变更建议
* 局部重生成
* Review Loop
* 项目级记忆

### 对标参考

Lovart 代表的是统一创意画布和设计代理协作。你们不必做通用 canvas，但应该做：

## **对象化的策划协作画布 / workspace**。 ([Lovart][3])

---

# 四、把六层能力映射到你这 4 个页面

这是 V2 最关键的版本。

---

# 页面 1：Opportunity Workspace

## 定义

**机会判断工作台**

## 核心对象

* `OpportunityCard`
* `OpportunityReview`
* `SourceNotePreview`

## 页面里的 AI 角色

### 1. Opportunity Interpreter

帮用户把机会卡解释清楚：

* 为什么这是机会
* 机会成立在什么证据上
* 这更像趋势还是噪音

### 2. Review Copilot

帮 reviewer 看：

* 证据是否足够
* 机会是否值得 promoted
* 哪些字段还缺
* 是否建议直接进入 Brief

### 3. Brief Trigger

不只是按钮“生成 Brief”，而是：

* 在 promoted 条件满足时主动建议进入 Brief
* 自动带出推荐方向

## 该页面应具备的 V2 能力

### Context OS

注入：

* source note
* 原始证据
* review 历史
* 同类历史机会

### Stage OS

顶部显示：

* promoted readiness
* evidence completeness
* review consensus
* blockers

### Decision OS

支持：

* 单次 AI 分析
* 高风险时发起 discussion
* 输出结构化“是否值得 promoted”的理由

### Action OS

可执行动作：

* `promote_opportunity`
* `archive_opportunity`
* `generate_brief`
* `request_more_evidence`

## 页面核心升级判断

这个页面不应再是“左边列表 + 右边聊天区”，而应是：

## **机会对象检视与判断系统**

### 最应该先做的 3 个升级

1. 顶部 `Opportunity Health Header`
2. AI 推荐“是否进入 Brief”
3. 相似历史机会记忆注入

---

# 页面 2：Planning Workspace

## 定义

**内容策划工作台**

## 核心对象

* `OpportunityBrief`
* `TemplateMatchSet`
* `RewriteStrategy`

## 页面里的 AI 角色

### 1. Brief Synthesizer

围绕 brief 给出：

* 缺什么
* 哪些字段不一致
* 是否足以进入策略阶段

### 2. Template Planner

不只是返回 top3 模板，而要解释：

* 为什么是这 3 个
* 分别适合什么路径
* 风险在哪里

### 3. Strategy Director

帮用户生成、比较、局部改写 strategy block

## 该页面应具备的 V2 能力

### Context OS

注入：

* 当前 brief
* 来源机会卡
* 历史同类 brief
* 品牌 / 项目记忆

### Stage OS

顶部显示：

* brief 完整度
* template fit score
* strategy readiness
* blockers
* next steps

### Decision OS

这是最适合 Council 发挥价值的页面，但 Council 必须产出：

* 策略共识
* 分歧点
* block-level proposal diff

### Action OS

可执行动作：

* `refine_brief_field`
* `rematch_templates`
* `regenerate_strategy`
* `lock_strategy_block`
* `compare_strategy_versions`
* `compile_note_plan`

### Collaboration OS

允许：

* 局部 block 重写
* 锁定 block
* 对 block 发起讨论
* 改 brief 后自动提醒哪些 strategy block 需同步变更

## 页面核心升级判断

这是 V2 最重要的一页。
因为它是从“机会判断”进入“内容编译”的真正转换层。

### 最应该先做的 4 个升级

1. `PlanningContextAssembler` 先落这一页
2. `Stage Header` + `HealthChecker`
3. Council 输出结构化 diff，并可 apply 到 Strategy
4. block-level actions + lock 机制

---

# 页面 3：Creation Workspace

## 定义

**创作与方案细化工作台**

## 核心对象

* `NewNotePlan`
* `MainImagePlan`
* `ImageSlotPlan`
* `TitleCandidateSet`
* `BodyOutline`

## 页面里的 AI 角色

### 1. Plan Compiler Copilot

围绕 `NewNotePlan` 检查：

* 方案是否完整
* 各图位是否职责清晰
* 标题 / 正文 / 图位是否一致

### 2. Visual Director

围绕每个图位解释：

* 当前 role / intent
* 为什么这么设计
* 怎么改更好

### 3. Asset Pre-Producer

在不进入最终资产阶段之前，先把 plan 细化成“可执行的图文对象”。

## 该页面应具备的 V2 能力

### Context OS

注入：

* 当前 plan
* 当前 strategy
* 当前 template
* 当前机会卡和 brief 摘要

### Stage OS

顶部显示：

* title completeness
* body completeness
* image slot completeness
* plan consistency
* blockers

### Action OS

统一支持：

* `regenerate_titles`
* `regenerate_body_outline`
* `regenerate_image_slot`
* `lock_image_slot`
* `compare_slot_versions`
* `compile_asset_bundle`

### Collaboration OS

这是最适合做“对象化共创”的页面。
应该支持：

* 选中某个标题对象
* 选中某个正文对象
* 选中某个图位对象
* 右侧 inspector 根据对象切换 AI 操作

### 最关键的产品升级

这一页应该逐步从“表单+右栏操作”升级成：

## **Plan Board / Visual Planning Canvas**

也就是一个更接近 Lovart 的“统一创意工作面”，但围绕的是内容策划对象，而不是通用设计画布。([Lovart][3])

### 最应该先做的 4 个升级

1. 对象选中态驱动右侧 AI Inspector
2. 每个 ImageSlot 的局部分析与动作 chips
3. 图位版本比较
4. Plan consistency health check

---

# 页面 4：Asset Workspace

## 定义

**资产生产与交付工作台**

## 核心对象

* `AssetBundle`
* `VariantSet`
* `ImageExecutionBrief`
* `ExportPackage`

## 页面里的 AI 角色

### 1. Asset Producer

基于 `NewNotePlan` 派生出标题、正文、图片执行 brief、变体

### 2. Judge Agent

评估：

* 资产是否与 plan 一致
* 是否存在风险
* 哪些变体更值得导出/发布

### 3. Review Loop Driver

在资产生成后，把结果回流为：

* 待办
* 改进建议
* 再评分入口

## 该页面应具备的 V2 能力

### Context OS

注入：

* 来源机会卡
* 来源 strategy
* 来源 plan
* 版本 lineage
* 历史同类资产

### Stage OS

顶部显示：

* asset readiness
* export readiness
* review issues
* publish status

### Action OS

统一支持：

* `regenerate_title_variant`
* `regenerate_body_variant`
* `regenerate_image_brief`
* `generate_variants`
* `approve_asset_bundle`
* `mark_published`
* `submit_feedback`

### Compiler OS

这是最强的一层。
这个页面体现的是：

## **从策划对象到可交付资产包的编译能力**

### Collaboration OS

支持：

* 变体对比
* 导出前审核
* 发布后效果回填
* Judge 建议自动变成下一轮优化入口

### 最应该先做的 4 个升级

1. `VariantSet` 对比视图
2. Judge Agent 的结构化评分
3. 回填发布结果
4. 导出包与 lineage 绑定

---

# 五、V2 的交互总原则：从“模式驱动”收敛为“对象驱动”

这是我最建议你在内部统一的一条产品原则。

## 旧版心智

* 我要不要点 chat
* 要不要开 council
* 要不要跑 pipeline

## V2 心智

* 我当前在看哪个对象
* 我现在要 analyze、compare、apply，还是 generate

也就是：

## **对象优先，动作其次，Agent 在后台编排**

这正是借鉴 Chance 的正确方式：
不是做成 camera-first，而是做成：

## **current-object-first**。 ([Chance AI][1])

---

# 六、四个页面各自的“AI 原生能力卡”

这个适合直接拿去做内部能力评审。

---

## Opportunity Workspace

### AI 原生能力

* 证据解释
* promoted readiness 判断
* 风险提醒
* 进入 Brief 建议
* 历史机会记忆

### 主要 KPI

* promoted 转化率
* 人工 review 效率
* 误 promoted 降低率

---

## Planning Workspace

### AI 原生能力

* Brief 健康检查
* 模板 top3 匹配
* Strategy 多版本生成与比较
* Council 分歧求解
* block-level strategy apply

### 主要 KPI

* Brief 完整度
* Strategy 采纳率
* 模板选择正确率
* 人工改写成本下降

---

## Creation Workspace

### AI 原生能力

* Plan consistency 检查
* 标题 / 正文 / 图位局部重生成
* ImageSlot 对象化协作
* 版本比较
* Plan Board 共创

### 主要 KPI

* 单次 plan 完成时长
* 图位重做率
* 标题/正文采纳率
* 进入资产阶段通过率

---

## Asset Workspace

### AI 原生能力

* 变体生成
* Judge 评分
* 导出建议
* 发布回填
* 复盘闭环

### 主要 KPI

* 资产导出率
* 变体采纳率
* 发布后回填率
* 改进闭环完成率

---

# 七、V2 的优先级建议

如果你要继续按阶段推进，我建议不再按“功能编号”推进，而按**页面价值**推进。

## P0：Planning Workspace

因为它是全链路中最关键的一页。
优先做：

* PlanningContextAssembler
* Stage Header
* 结构化 Council diff
* ActionSpec
* block-level strategy 协作

## P1：Creation Workspace

因为它决定能否从“策略”走到“对象化共创”。
优先做：

* 右侧对象 inspector
* ImageSlot actions
* Plan health check
* 版本比较

## P2：Opportunity Workspace

因为它更偏上游，但能明显提升机会判断效率。
优先做：

* promoted readiness
* 证据解释
* 历史机会记忆

## P3：Asset Workspace

因为它偏下游交付，但需要前面 plan 足够稳。
优先做：

* Judge Agent
* VariantSet
* 回填结果
* 导出与 lineage

---

# 八、和三个参考产品的再映射

| 你们页面                  | 对标 Chance           | 对标 Veeso                    | 对标 Lovart    |
| --------------------- | ------------------- | --------------------------- | ------------ |
| Opportunity Workspace | 围绕对象理解，不从 prompt 开始 | 弱                           | 弱            |
| Planning Workspace    | 围绕当前对象多轮理解          | 从 brief 到策略编译               | 多方案比较与决策面    |
| Creation Workspace    | 围绕对象持续追问            | 从 plan 到可交付内容               | 最强，对应统一创意工作面 |
| Asset Workspace       | 视觉上下文持续保留           | 最强，对应 deliverables & export | 次强，对应设计输出与版本 |

### 核心结论

* **Chance 的启发主要落在前两页**：对象优先交互。([Chance AI][1])
* **Veeso 的启发主要落在后两页**：编译成可编辑交付物。([Veeso AI][2])
* **Lovart 的启发最强地落在 Creation Workspace**：统一创意工作面。([Lovart][3])

---

# 九、最后一版总结

## V2 不再是：

“给四个页面分别加更多 Agent 功能”

## V2 应该是：

“把四个页面都升级成 AI 原生 Workspace，让 AI 以 Context OS、Stage OS、Decision OS、Action OS、Compiler OS、Collaboration OS 六层能力嵌入其中。”

### 一句话版

## **从 Agent 功能清单，升级为围绕四个核心对象工作台的产品能力地图。**

### 更短的内部表述

## **AI 不再是外挂助手，而是四个 Workspace 的原生操作系统。**



[1]: https://www.chance.vision/ "https://www.chance.vision/"
[2]: https://veeso.ai/ "https://veeso.ai/"
[3]: https://www.lovart.ai/ "https://www.lovart.ai/"



