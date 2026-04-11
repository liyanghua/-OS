

# 《AI Agent 交互升级 V2：从 Agent 功能清单到产品能力地图》 - 架构升级

---

## 1. 一句话结论

你们不该做成“在 4 个页面里塞进更多 Agent 功能”，而应该做成：

## **Hermes-style 记忆/技能/自进化基座 + DeerFlow-style 长链路编排/沙箱/子代理能力 + 你们自己的对象化策划编译层**

也就是：

* **Hermes-Agent** 负责“Agent 会不会越用越懂你、越做越会做”
* **DeerFlow** 负责“Agent 能不能把复杂长链路任务稳定跑下来”
* **你们自己的系统** 负责“这些能力最终服务什么对象、什么工作流、什么业务产物”

Hermes-Agent 官方强调 built-in learning loop、skills、memory、cross-session user model；DeerFlow 官方强调 super-agent harness、sub-agents、memory、sandboxes、skills，并且 2.0 是重写后的新架构，后端公开说明基于 LangGraph、支持隔离线程环境、工具、文件、浏览器和子代理执行。([GitHub][1])

---

## 2. 先回答“为什么要 Hermes + DeerFlow，而不是只选一个”

### 2.1 Hermes-Agent 更适合做“Agent 基座人格与成长层”

Hermes-Agent 的公开定位非常鲜明：
它强调 built-in learning loop、从经验中创建和改进 skills、持久化知识、搜索历史对话、跨会话形成对用户的更深模型；其 memory 插件还公开支持 `hybrid/context/tools` 三种 memory integration 模式。([GitHub][1])

这对你们最有价值的不是“它会聊天”，而是三件事：

* **跨会话记忆**：品牌、项目、机会、策略偏好会持续沉淀
* **技能化沉淀**：经常出现的策划动作可以沉淀成 skills
* **自进化**：通过经验与评测循环不断优化 skill / prompt / tool descriptions；其 self-evolution 仓库公开就是围绕 DSPy + GEPA 做技能、工具描述、提示和代码的进化优化。([GitHub][1])

### 2.2 DeerFlow 更适合做“长链路任务执行层”

DeerFlow 官方公开口径非常明确：
它是 open-source super agent harness，强调 sub-agents、memory、sandboxes、skills；后端 README 直接写到是 LangGraph-based，支持 code execution、web browse、files、delegate tasks to subagents、per-thread isolated environments；Sandbox Provisioner 还明确用 FastAPI + Kubernetes 管 sandbox pod 生命周期。([GitHub][2])

这对你们最有价值的是：

* **长链路编排稳定性**
* **子代理委派**
* **沙箱执行**
* **技能驱动任务流**
* **线程级隔离上下文**

### 2.3 两者合起来，刚好补你们当前的两类短板

你前面总结的问题本质上分两类：

#### A. “会不会越来越懂项目与品牌”

这是 Hermes 强项。

#### B. “能不能把多阶段任务稳稳跑完”

这是 DeerFlow 强项。

所以最合理的组合不是“谁替代谁”，而是：

## **Hermes 作为 Agent runtime / memory / skill substrate**

## **DeerFlow 作为 workflow / subagent / sandbox orchestration layer**

---

## 3. 你们自己的产品层到底放哪

这里最关键。

无论 Hermes 还是 DeerFlow，都不能直接替代你们的核心产品层。
你们真正的壁垒仍然必须是：

## **对象化的策划编译系统**

也就是围绕这些业务对象：

* `OpportunityCard`
* `OpportunityBrief`
* `TemplateMatchSet`
* `RewriteStrategy`
* `NewNotePlan`
* `AssetBundle`
* `VariantSet`

把 AI 能力落到 4 个 Workspace 里。

换句话说：

### Hermes 不是产品

它是“Agent 能力底座”。

### DeerFlow 不是产品

它是“复杂任务执行引擎”。

### 你们的产品是

## **AI-native 内容策划编译与执行工作台**

---

# 4. V2 的新能力地图：用“基座层 / 编排层 / 产品层”重写

我建议把 V2 从原来的“Phase 1a/1b/2a/2b…”改写成三层地图。

---

## Layer A：Agent Base Layer（建议借 Hermes-Agent）

### 目标

解决“Agent 记不住、不成长、不会技能化”的问题。

### 核心能力

#### 1. Project Memory

不是泛泛聊天记忆，而是项目级记忆：

* 某个 opportunity 的历史判断
* 某个 brief 的修改轨迹
* 某个 strategy 的偏好
* 某个品牌的语气与调性
* 某类模板的历史采纳情况

Hermes 官方口径里就强调 persistent knowledge、search past conversations、deepening model of who you are；其 memory 模式支持自动上下文注入和工具调用两种混合。([GitHub][1])

#### 2. Skill Substrate

把你们的高频动作沉淀为可调用 skill，而不是每次临时 prompting。
例如：

* `generate_brief_from_promoted_opportunity`
* `rematch_templates_for_brief`
* `compare_strategy_blocks`
* `regenerate_image_slot`
* `compile_asset_bundle`

Hermes README 及发布说明都强调 first-class plugin architecture、toolsets / plugins / skills。([GitHub][3])

#### 3. Self-Evolution Loop

把你们现有评测、人工反馈、采纳率、回填结果，转成：

* skill 版本更新
* prompt 版本更新
* tool description 版本更新
* 路由策略更新

Hermes self-evolution 仓库已经公开把 skill/tool/prompt/code 的进化优化当成一等公民。([GitHub][4])

### 对你们页面的意义

这层一般不直接前台暴露，但会让 4 个 Workspace 的 AI 越来越“像懂项目的人”。

---

## Layer B：Execution & Orchestration Layer（建议借 DeerFlow）

### 目标

解决“多阶段任务跑不稳、子任务难拆、执行能力弱”的问题。

### 核心能力

#### 1. Workflow Graph

用 DeerFlow / LangGraph 式 workflow 去跑：

* Opportunity → Brief
* Brief → TemplateMatch
* Template → Strategy
* Strategy → NotePlan
* NotePlan → AssetBundle
* AssetBundle → Variant / Export / Review Loop

DeerFlow 后端公开说明就是 LangGraph-based agent backend。([GitHub][5])

#### 2. Subagent Delegation

每个 Workspace 内部可以委派不同子代理：

* TrendAnalyst
* BriefSynthesizer
* TemplatePlanner
* StrategyDirector
* VisualDirector
* AssetProducer
* Judge

DeerFlow README 明确就是 harness that orchestrates sub-agents。([GitHub][2])

#### 3. Sandbox & Tool Execution

需要真正“执行”的动作走 sandbox：

* 生成图片执行包
* 调视觉 Agent
* 调导出器
* 运行格式检查
* 批量生成 variants
* 质量对比脚本

DeerFlow 的 sandbox provisioner 明确支持独立 sandbox pod 生命周期管理。([GitHub][6])

#### 4. Skill Registry / Tool Binding

把 Hermes 的 skills 与 DeerFlow 的 workflow 节点绑定起来。
这样 DeerFlow 负责“什么时候调谁”，Hermes 负责“这个 skill 怎么越来越好”。

### 对你们页面的意义

这层也主要偏后台，但它会决定：

* 是否可以长链路稳定执行
* 是否支持局部重跑
* 是否支持后台异步执行
* 是否支持观察每个阶段状态

---

## Layer C：Product OS Layer（必须由你们自己定义）

### 目标

把 Hermes + DeerFlow 的能力，变成你们真正的业务产品。

### 核心不是 Agent，而是对象与工作流

你们前面已经把页面收敛到 4 个 Workspace，这就是正确的产品形态。
V2 要做的是：

## **让这 4 个 Workspace 成为 AI 原生对象工作台**

---

# 5. 四个 Workspace × 三层能力映射

这是你最该拿去内部讲的一张图的文字版。

---

## 页面 1：Opportunity Workspace

### 页面定义

机会判断工作台

### Hermes 借鉴点

#### Project Memory

* 历史相似机会
* 过去被 promoted / archive 的相似案例
* 某品牌对哪类机会更偏好

#### Skill

* `evaluate_opportunity_strength`
* `summarize_evidence_blocks`
* `draft_brief_from_opportunity`

### DeerFlow 借鉴点

#### Workflow Node

这个页面对应 workflow 的起点节点：

* opportunity evaluation
* evidence sanity check
* review aggregation
* promote/archive action

#### Subagents

* TrendAnalystAgent
* BriefSynthesizer pre-stage

### 产品层能力

#### Context OS

当前机会 + source note + review + 相似历史机会

#### Stage OS

* readiness to brief
* evidence completeness
* blockers
* next action

#### Action OS

* promote
* archive
* generate brief
* ask for more evidence

### 升级判断

这个页面要像 Chance 一样“先围绕对象理解”，而不是一上来空白 prompt。
对象是 `OpportunityCard`，不是相机画面。([chance.vision](https://www.chance.vision/))

---

## 页面 2：Planning Workspace

### 页面定义

内容策划工作台

### Hermes 借鉴点

#### Memory

* 某品牌过去喜欢什么模板
* 过去哪些 strategy block 常被采用
* 历史 Brief/Strategy 的高频分歧点

#### Skills

* `repair_brief_missing_fields`
* `match_templates_for_brief`
* `generate_strategy_variants`
* `compare_strategy_versions`

### DeerFlow 借鉴点

#### Workflow Node

* brief compile
* template match
* strategy branch A/B/C
* evaluate and choose

#### Subagents

* TemplatePlannerAgent
* StrategyDirectorAgent
* Council / Judge style subagents

### 产品层能力

#### Decision OS

这是最强的一页。
Council 应该成为结构化分歧求解器，而不是独立聊天模式。

#### Action OS

* rematch templates
* generate strategy
* compare strategy
* lock block
* apply proposal diff

#### Compiler OS

把确定的 strategy 编译成 `NewNotePlan`

### 升级判断

这里最像“本体大脑”应该发力的页面。
Hermes 负责把品牌/项目偏好记住，DeerFlow 负责把多策略分支跑出来，你们自己负责把它们落到 `Brief / Template / Strategy` 对象上。

---

## 页面 3：Creation Workspace

### 页面定义

创作与方案细化工作台

### Hermes 借鉴点

#### Memory

* 哪些标题风格常被这个品牌采用
* 哪种图位重写经常成功
* 哪些 ImageSlot 经常被人工锁定

#### Skills

* `regenerate_titles`
* `refine_body_outline`
* `regenerate_image_slot`
* `lock_slot_and_propagate_constraints`

### DeerFlow 借鉴点

#### Workflow Node

* note plan compile
* image slot refinement
* local regeneration
* consistency evaluation

#### Sandbox / tool execution

* prompt packaging
* slot validation
* local preview generation

### 产品层能力

#### Compiler OS

这一页是 plan 编译的核心。

#### Collaboration OS

这是最适合借 Lovart 的页面：
不是做通用 canvas，而是做：

## **Plan Board / Visual Planning Canvas**

围绕：

* 标题
* 正文
* 5 个图位
* 标签策略
* 发布建议

做对象化共创。([lovart.ai](https://www.lovart.ai/))

#### Action OS

* regenerate title
* regenerate body
* regenerate slot N
* compare slot versions
* lock slot
* compile asset bundle

### 升级判断

这一页最应该从“卡片+右侧编辑区”升级成更强的对象化工作面。

---

## 页面 4：Asset Workspace

### 页面定义

资产生产与交付工作台

### Hermes 借鉴点

#### Memory

* 哪类 asset variant 更常被采用
* 过去哪些导出格式最常用
* 哪些 Judge 反馈经常导致重做

#### Skills

* `generate_variants`
* `compare_variants`
* `prepare_export_package`
* `record_publish_feedback`

### DeerFlow 借鉴点

#### Workflow Node

* asset generation
* variant generation
* judge scoring
* export
* publish feedback loop

#### Sandbox

* 批量导出
* 包结构校验
* 多变体比较

### 产品层能力

#### Compiler OS

从 `NewNotePlan` 派生：

* 标题
* 正文
* ImageExecutionBrief
* VariantSet
* ExportPackage

这部分最接近 Veeso 的交付物编译思路，但你们更强，因为前面有机会判断和策略编译。([veeso.ai](https://veeso.ai/))

#### Review Loop

发布后效果回填，进入下一轮 skill / strategy / template 优化。

### 升级判断

这一页应该是“交付与回流系统”，不只是下载页面。

---

# 6. 用 Hermes + DeerFlow 重写你原来的升级阶段

你原来是：

* Phase 1 上下文 + 路由
* Phase 2 主动 AI
* Phase 3 可执行 AI
* Phase 4 协作 AI

这个思路没问题，但我建议改写成更适合落地的四阶段。

---

## V2-Phase A：Base Layer 接入

### 目标

把 Hermes 变成 Agent Base。

### 重点

* `ProjectMemoryProvider`
* `SkillRegistry`
* `LearningLoopHooks`
* `PlanningContextAssembler`

### 结果

所有 Agent 都吃同一种项目级记忆和 skill。

---

## V2-Phase B：Workflow Layer 接入

### 目标

把 DeerFlow 变成 orchestration harness。

### 重点

* 把 4 个 Workspace 的后台流程建成 workflow graph
* 支持 subagent delegation
* 支持 sandbox execution
* 支持 partial rerun / async execution / event bus state sync

### 结果

你们不再只是同步按钮式调用，而是真正有了长链路执行引擎。

---

## V2-Phase C：Workspace-native AI

### 目标

让 AI 成为每个页面的原生能力，而不是外挂功能。

### 重点

* Stage Header
* AI Inspector
* ActionSpec
* Proposal diff apply
* 局部重生成

### 结果

用户体验从“点按钮叫 AI”升级为“页面本身就具备 AI 能力”。

---

## V2-Phase D：Review & Evolution Loop

### 目标

把人类反馈、Judge 评分、发布结果变成进化信号。

### 重点

* 项目级记忆
* 采纳率统计
* 变体优胜回流
* skill / template / strategy 进化

### 结果

系统开始真的“越用越懂、越做越稳”。

---

# 7. 你们该如何描述自己的差异化

这是很重要的一点。

## 不是 Chance

你们不是 C 端视觉伴侣，不是 camera-first lifestyle app。
你们借的是：

* object-first interaction
* no-prompt-first
* 围绕当前对象持续对话与推进([chance.vision](https://www.chance.vision/))

## 不是 Veeso

你们不是通用“文案转设计图”工具。
你们借的是：

* content-to-deliverable compiler
* editable deliverables
* production-ready asset outputs([veeso.ai](https://veeso.ai/))

## 不是 Lovart

你们不是通用设计代理或创意平台。
你们借的是：

* one-canvas / one-workspace 协作思路
* 统一对象工作面
* AI 与人共创的界面结构([lovart.ai](https://www.lovart.ai/))

## 你们是什么

## **机会驱动的内容策划编译与执行操作系统**

这句话建议你内部固定下来。

---

# 8. 最终版能力地图

下面给你一版适合做内部评审表述的简版。

## 能力层 1：Agent Base

由 Hermes 风格能力承接：

* Project Memory
* Skill Registry
* Learning Loop
* Cross-session preference model

## 能力层 2：Workflow Harness

由 DeerFlow 风格能力承接：

* Workflow Graph
* Subagent Delegation
* Sandbox Execution
* Thread-isolated state
* Async long-horizon execution

## 能力层 3：Workspace OS

由你们自己定义：

* Context OS
* Stage OS
* Decision OS
* Action OS
* Compiler OS
* Collaboration OS

## 最终落点

这六层能力映射到 4 个 Workspace：

* Opportunity Workspace
* Planning Workspace
* Creation Workspace
* Asset Workspace

---

# 9. 我建议你下一步内部优先推进的 5 件事

如果你问我：基于 Hermes + DeerFlow，最值得先做哪 5 件事？

## 1. `PlanningContextAssembler` 接 Hermes-style memory

因为没有统一上下文，后面所有智能都散。

## 2. 把 4 个页面后台流程抽成 DeerFlow-style workflow graph

尤其是：

* generate brief
* match template
* generate strategy
* compile note plan
* generate assets
* generate variants

## 3. 建统一 `ActionSpec`

让所有 AI 输出都能直接在页面执行。

## 4. Council → structured diff → apply

把讨论变成对象变更，而不是长文本。

## 5. 在 Creation Workspace 做一个 `Plan Board / Visual Planning Canvas`

这是最能体现你们产品差异化的一步。

---

# 10. 一页总结版

## 标题

**AI Agent 交互升级 V2：基于 Hermes-Agent 基座与 DeerFlow 编排能力的产品能力地图**

## 副标题

**以 Hermes 构建记忆、技能与自进化基座，以 DeerFlow 承接长链路编排、子代理与沙箱执行，以四个 Workspace 落地 Context / Stage / Decision / Action / Compiler / Collaboration 六层产品能力。**

## 三个核心判断

1. **Hermes 用来做“越来越懂项目与用户”的 Agent Base**
2. **DeerFlow 用来做“长链路、多子任务、可执行”的 Workflow Harness**
3. **真正的产品壁垒仍然是你们自己的对象化策划编译系统**

---



[1]: https://github.com/NousResearch/hermes-agent/blob/main/README.md?utm_source=chatgpt.com "README.md - NousResearch/hermes-agent"
[2]: https://github.com/bytedance/deer-flow/blob/main/README.md?utm_source=chatgpt.com "deer-flow/README.md at main"
[3]: https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.3.0.md?utm_source=chatgpt.com "hermes-agent/RELEASE_v0.3.0.md at main"
[4]: https://github.com/NousResearch/hermes-agent-self-evolution?utm_source=chatgpt.com "NousResearch/hermes-agent-self-evolution"
[5]: https://github.com/bytedance/deer-flow/blob/main/backend/README.md?utm_source=chatgpt.com "deer-flow/backend/README.md at main"
[6]: https://github.com/bytedance/deer-flow/blob/main/docker/provisioner/README.md?utm_source=chatgpt.com "deer-flow/docker/provisioner/README.md at main"
