

# 《AI-native 产品层：4 个页面 / 6 类对象 / 6 个 Agent / 关键交互 Spec》

这版不是商业化平台层 spec，不含计费、权限、SSO、运维后台；
它专注于你要补的那一层：

## **AI-native 产品层**

目标是把你现有已经跑通的：

* 机会卡
* Brief
* 模板匹配
* Rewrite Strategy
* NewNotePlan
* 标题 / 正文 / 图片 brief / AssetBundle

从“线性流程系统”升级成：

## **对象驱动、可持续交互、多人+多 Agent 协同的内容经营工作台**。

你当前系统已经具备这些对象和链路基础，所以这层不是从零开始，而是在现有工作台和编译链上做对象化重构。

---

# 一、产品层总目标

## 目标定义

AI-native 产品层要解决四件事：

### 1. 把“步骤”变成“对象”

用户不再是在跑：

* 第一步
* 第二步
* 第三步

而是在持续操作：

* 某张机会卡
* 某份 Brief
* 某套 Strategy
* 某个图位
* 某个 AssetBundle

### 2. 把“结果”变成“可编辑中间对象”

不是一次性输出，而是：

* 可改
* 可锁定
* 可比较
* 可派生新版本

### 3. 把“人类审批流”升级成“人类 + AI 协同流”

AI 先做：

* 分析
* 编译
* 对比
* 生成候选
  人类再做：
* 选
* 锁
* 改
* 批

### 4. 把“内容方案”升级成“可生产资产包”

最终不只是策略文本，而是：

* 标题
* 正文
* 图位 brief
* 资产包
* 变体

---

# 二、4 个页面

我建议 AI-native 产品层只做 4 个核心页面。
不是更多，而是每个页面都有非常明确的对象与角色。

---

## 页面 1：Opportunity Workspace

## 页面目标

围绕 **机会对象** 工作，而不是只看列表。

## 适用角色

* Strategist
* Reviewer
* Trend Analyst Agent
* Brief Synthesizer Agent

## 页面定位

这是“机会判断工作台”。

## 页面核心对象

* `OpportunityCard`
* `OpportunityReview`
* `SourceNotePreview`

## 页面布局

### 左栏：机会池

* promoted
* reviewed
* pending
* 过滤器（场景 / 风格 / 卖点 / 品类 / 互动强度）

### 中栏：当前机会详情

* 一句话洞察
* interaction insight
* validation summary
* evidence blocks
* action recommendation
* 来源笔记预览

### 右栏：协作区

* 人工 review
* AI 分析建议
* 生成 Brief
* 版本/历史

## 页面必须支持的动作

* 选中一张机会卡
* 查看其来源笔记和证据
* 人工 review / promoted / archive
* 调用 AI：生成/刷新 Brief
* 查看该机会已有的 Brief 和历史版本
* 把该机会送入内容策划

## 页面核心 CTA

* `生成 Brief`
* `进入策划`
* `查看历史版本`

---

## 页面 2：Planning Workspace

## 页面目标

围绕 **Brief / 模板 / Strategy** 做策划编译与对比。

## 适用角色

* Strategist
* Editor
* Template Planner Agent
* Strategy Director Agent

## 页面定位

这是“内容策划工作台”。

## 页面核心对象

* `OpportunityBrief`
* `TemplateMatchSet`
* `RewriteStrategy`

## 页面布局

### 左栏：Brief 面板

* target_scene
* audience
* core_selling_points
* why_now
* why_it_works
* differentiation_view
* planning_direction

### 中栏：模板与策略主区

* top3 模板候选
* 当前选中模板
* Strategy block view
* 多策略比较

### 右栏：动作与版本区

* 重新匹配模板
* 生成新 Strategy
* 比较 Strategy A / B / C
* 锁定某些策略块
* 进入 NotePlan

## 页面必须支持的动作

* 编辑 Brief
* 切换模板
* 对同一 Brief 生成多套 Strategy
* 比较 Strategy
* 局部重写某个 Strategy block
* 锁定 block
* 将选中的 Strategy 编译成 NotePlan

## 页面核心 CTA

* `重新匹配模板`
* `生成策略`
* `比较策略`
* `编译为 NotePlan`

---

## 页面 3：Creation Workspace

## 页面目标

围绕 **NewNotePlan / MainImagePlan / ImageSlot** 做图文对象化共创。

## 适用角色

* Strategist
* Editor
* Designer
* Visual Director Agent
* Asset Producer Agent

## 页面定位

这是“创作与方案细化工作台”。

## 页面核心对象

* `NewNotePlan`
* `MainImagePlan`
* `ImageSlotPlan`
* `TitleCandidateSet`
* `BodyOutline`

## 页面布局

### 左栏：当前计划上下文

* 当前机会卡
* 当前 Brief 摘要
* 当前模板
* 当前 Strategy 版本
* 当前 plan 版本

### 中栏：Plan Board

按对象分块展示：

* 标题区
* 正文区
* 5 个图位区
* 标签策略
* 发布建议

### 右栏：局部编辑区

根据当前选中对象切换：

* 选中标题 → 显示标题操作
* 选中正文 → 显示正文操作
* 选中图位 → 显示图位操作

## 页面必须支持的动作

* 重生成标题候选
* 重生成正文 outline
* 选中第 N 个 ImageSlot
* 查看 role / intent / visual_brief / copy_hints
* 单独重生成某个 ImageSlot
* 锁定某个 ImageSlot
* 比较图位版本
* 编译为资产包

## 页面核心 CTA

* `重生成标题`
* `重生成正文`
* `重生成第 N 张图位`
* `生成资产包`

---

## 页面 4：Asset Workspace

## 页面目标

围绕 **AssetBundle / VariantSet** 做多资产生产、导出和回流。

## 适用角色

* Editor
* Designer
* Reviewer
* Asset Producer Agent
* Judge Agent

## 页面定位

这是“资产生产与交付工作台”。

## 页面核心对象

* `AssetBundle`
* `VariantSet`
* `ImageExecutionBrief`
* `ExportPackage`

## 页面布局

### 左栏：资产包上下文

* 来源机会卡
* 来源模板
* 来源 strategy
* 来源 plan
* 版本 lineage

### 中栏：资产内容区

Tab 形式：

* 标题
* 正文
* 图片执行 brief
* SKU / 详情 / 视频（可扩展）
* 变体

### 右栏：导出与审核区

* 导出
* 批准
* 标记为 ready / published
* 回填结果

## 页面必须支持的动作

* 重新生成标题变体
* 重新生成正文变体
* 单独重生成某个图位执行 brief
* 生成多个 Variant
* 比较 Variant A / B
* 导出 JSON / Markdown / image package
* 回填发布结果

## 页面核心 CTA

* `生成变体`
* `导出资产包`
* `标记已发布`
* `回填效果`

---

# 三、6 类核心对象

这些对象是 AI-native 产品层的骨架。
重点不是新增很多对象，而是让已有对象真正成为工作台中的“可交互对象”。

---

## 对象 1：OpportunityCard

## 作用

机会判断对象，所有策划链路的源头。

## 必要字段

* `opportunity_id`
* `title`
* `summary`
* `insight_statement`
* `interaction_insight`
* `validation_summary`
* `action_recommendation`
* `status`
* `source_note_ids`
* `lineage`

## 必须支持的交互

* promote / archive
* 查看证据
* 查看来源笔记
* 生成 Brief
* 进入策划

---

## 对象 2：OpportunityBrief

## 作用

把“为什么值得做”编译成“该怎么策划”。

## 必要字段

* `brief_id`
* `opportunity_id`
* `target_scene`
* `target_audience`
* `core_selling_points`
* `why_now`
* `why_it_works`
* `differentiation_view`
* `planning_direction`
* `status`
* `version`

## 必须支持的交互

* 编辑
* 保存
* 标记 stale 下游
* 重新编译模板候选

---

## 对象 3：TemplateMatchSet

## 作用

承载 top3 模板候选与匹配理由。

## 必要字段

* `brief_id`
* `template_candidates[]`
* `selected_template_id`
* `match_version`

每个 candidate 至少有：

* `template_id`
* `template_name`
* `score`
* `matched_dimensions`
* `rationale`

## 必须支持的交互

* 比较
* 选中
* 重新匹配
* 切换当前模板

---

## 对象 4：RewriteStrategy

## 作用

把模板与 Brief 翻译成可执行的内容策略。

## 必要字段

* `strategy_id`
* `brief_id`
* `template_id`
* `title_strategy`
* `body_strategy`
* `image_strategy`
* `hook_strategy`
* `tone_of_voice`
* `must_keep`
* `should_avoid`
* `differentiation_points`
* `scene_emphasis`
* `status`
* `version`

## 必须支持的交互

* 局部重写 block
* 比较多个版本
* 锁定 block
* 继续编译 NotePlan

---

## 对象 5：NewNotePlan

## 作用

把策略落实为完整内容方案对象。

## 必要字段

* `plan_id`
* `opportunity_id`
* `brief_id`
* `strategy_id`
* `template_id`
* `title_candidates`
* `body_outline`
* `image_plan`
* `tag_strategy`
* `publish_advice`
* `status`
* `version`

## 必须支持的交互

* 重生成标题
* 重生成正文
* 图位级查看与编辑
* 生成 AssetBundle

---

## 对象 6：AssetBundle

## 作用

真正的交付对象，面向执行与回流。

## 必要字段

* `asset_bundle_id`
* `plan_id`
* `title_candidates`
* `body_draft_or_outline`
* `image_execution_briefs`
* `variant_set`
* `export_status`
* `publish_status`
* `lineage`

## 必须支持的交互

* 导出
* 审核
* 生成变体
* 回填效果

---

# 四、6 个 Agent

这里的 Agent 不是“为了酷而加”，而是为了把工作从“人工线性点击”升级成“AI 预处理 + 人类判断”。

---

## Agent 1：Trend Analyst Agent

## 负责

* 扫描机会池
* 标出高优先级机会
* 推荐进入 promoted 的候选

## 输入

* 原始笔记
* 机会卡
* 互动数据
* review 状态

## 输出

* 优先级建议
* why worth review
* promoted 推荐清单

---

## Agent 2：Brief Synthesizer Agent

## 负责

* 把机会卡编译成更适合策划的 Brief

## 输入

* OpportunityCard
* source note
* validation summary
* interaction insight

## 输出

* OpportunityBrief
* why_now
* why_it_works
* differentiation_view

---

## Agent 3：Template Planner Agent

## 负责

* 对同一 Brief 给出 top3 模板候选
* 解释为什么推荐这些模板

## 输入

* Brief
* 模板库
* 历史高表现模板（后续可扩）

## 输出

* TemplateMatchSet
* 比较理由
* 风险说明

---

## Agent 4：Strategy Director Agent

## 负责

* 生成 RewriteStrategy
* 产出多个策略版本
* 局部重写策略块

## 输入

* Brief
* 选中模板
* 品牌约束

## 输出

* RewriteStrategy v1 / v2 / v3

---

## Agent 5：Visual Director Agent

## 负责

* 把 Strategy 编译成 5 图位 / ImageSlotPlan / ImageExecutionBrief
* 管理图位一致性与差异化

## 输入

* RewriteStrategy
* NewNotePlan
* 参考笔记/图像（后续可扩）

## 输出

* MainImagePlan
* ImageSlotPlan
* ImageExecutionBrief

---

## Agent 6：Asset Producer Agent

## 负责

* 标题
* 正文
* 资产包
* 变体

## 输入

* NewNotePlan
* 策略
* 品牌约束

## 输出

* AssetBundle
* VariantSet
* 导出包

---

# 五、关键交互 Spec

下面是最关键的一部分。
这是你产品会不会“AI-native”的关键。

---

## 交互 1：对象锚定

每个页面顶部都必须固定显示当前对象：

* 当前机会卡
* 当前 Brief
* 当前模板
* 当前 Strategy
* 当前 Plan
* 当前 AssetBundle

用户不能“只看到一堆结果”，必须始终知道：
**我现在在操作哪个对象。**

---

## 交互 2：局部编辑，不整套重来

系统必须支持：

* 改 Brief 的 audience，不动机会卡
* 切换模板，不重写 Brief
* 改 RewriteStrategy 里的 image_strategy，不重写 title_strategy
* 改第 3 张图位，不重跑整套 Plan
* 重生成标题，不影响图位

---

## 交互 3：版本比较

至少支持比较：

* Template A / B / C
* Strategy v1 / v2
* ImageSlot 版本
* AssetBundle 变体

必须有：

* side-by-side compare
* selected / current 标识
* 回退 / 设为当前版本

---

## 交互 4：锁定机制

用户必须能锁定：

* Brief 某字段
* Strategy 某 block
* ImageSlot 某图位
* 标题候选某一条

锁定后，下游重生成不能覆盖它。

---

## 交互 5：stale / regenerate 显式化

不要静默重算。

规则：

* Brief 改了 → template/strategy/plan/assets stale
* Template 改了 → strategy/plan/assets stale
* Strategy 改了 → plan/assets stale
* 某个 ImageSlot 改了 → 只让该 slot brief stale

页面必须可见：

* `fresh`
* `stale`
* `regenerating`

---

## 交互 6：AI 建议 chips

每个对象页都应有快捷操作 chips，例如：

### 在 Strategy 上

* 更偏种草
* 更偏转化
* 更适合礼赠
* 更平价改造

### 在 ImageSlot 上

* 桌布更突出
* 更有场景感
* 更少广告感
* 更适合小红书封面

### 在标题上

* 更像小红书原生
* 更克制
* 更强钩子

这样比写 prompt 更 AI-native。

---

## 交互 7：Board / Workspace 视图

至少在 Planning Workspace 或 Creation Workspace 中加入 Board 视图：

可把这些对象拼在一个面里：

* 当前机会卡
* 参考笔记
* 当前 Brief
* top3 模板
* 当前 Strategy
* 5 个图位
* 当前 AssetBundle 预览

这一步最接近 Chance / Lovart 的对象工作方式。

---

## 交互 8：人类 + AI 协同动作

每个对象都应区分：

### AI 可做

* 分析
* 生成候选
* 比较版本
* 自动解释差异
* 自动检查

### 人可做

* promote
* approve
* lock
* select current version
* export
* publish
* feedback

---

# 六、最小可落地版本建议

如果你现在只做一版 MVP，我建议优先落这 4 项：

## MVP-1

Opportunity Workspace

* Trend Analyst / Brief Synthesizer

## MVP-2

Planning Workspace

* Template Planner / Strategy Director

## MVP-3

Creation Workspace

* Visual Director

## MVP-4

Asset Workspace

* Asset Producer

这样你就已经形成了一个完整 AI-native 产品层。

---

# 七、给 AI-coding 的总 Prompt

你可以直接把下面这段给 Codex / Cursor：

```text id="20976"
请基于现有真实小红书内容编译系统，实现一层 AI-native 产品层。

目标：
围绕 4 个页面、6 类对象、6 个 Agent，重构现有工作台，使系统从“线性流程页”升级为“对象驱动的 AI-native 内容经营工作台”。

必须实现的 4 个页面：
1. Opportunity Workspace
2. Planning Workspace
3. Creation Workspace
4. Asset Workspace

必须强化的 6 类对象：
- OpportunityCard
- OpportunityBrief
- TemplateMatchSet
- RewriteStrategy
- NewNotePlan
- AssetBundle

必须支持的 6 个 Agent：
- Trend Analyst Agent
- Brief Synthesizer Agent
- Template Planner Agent
- Strategy Director Agent
- Visual Director Agent
- Asset Producer Agent

关键交互要求：
- 当前对象锚点固定显示
- 支持局部编辑与局部失效
- 支持版本比较与回退
- 支持锁定对象局部
- 支持 AI 建议 chips
- 支持 Board / Workspace 视图
- 不要做聊天优先 UI
- 不使用 mock data / mock service
- 必须复用现有真实 API 和对象

请先输出：
1. 当前实现中最适合承接这 4 个页面的现有模板 / 路由 / API
2. 最小改造路径
3. 需要新增的对象字段
4. 需要新增的页面和组件
我确认后再开始改代码
```

