可以。下面给你一版**偏工程落地 + 产品可用 + 业务可验收**的：

# 《Hermes-Agent × DeerFlow × 4 个 Workspace 实现后的详细验收清单 / 自测清单》

这版清单分成 8 层：

1. 架构与依赖验收
2. Agent Base 层验收
3. Workflow / Orchestration 层验收
4. 4 个 Workspace 页面级验收
5. 对象链与数据一致性验收
6. 动作执行与可回滚验收
7. 质量与业务效果验收
8. 上线前回归清单


---

# 一、总体验收目标

先定 3 个总目标，后面的清单都围绕它们展开。

## Goal A：系统真的从“Agent 功能集合”升级为“4 个 Workspace 的原生能力”

判断标准：

* 用户不需要理解 chat / council / pipeline 才能完成工作
* 每个页面本身具备 AI 能力
* AI 是页面的一部分，不是外挂

## Goal B：对象链完整、可回溯、可执行

判断标准：

* `OpportunityCard -> OpportunityBrief -> TemplateMatchSet -> RewriteStrategy -> NewNotePlan -> AssetBundle`
  全部存在、串联、可追踪
* 所有关键动作都能落到统一 `ActionSpec`
* 支持局部 apply、局部 rerun、局部 compare

## Goal C：Hermes + DeerFlow 的引入不是“技术替换”，而是“产品增强”

判断标准：

* Hermes 负责记忆 / skill / 演化，DeerFlow 负责编排 / 子代理 / sandbox
* 你们自己的对象模型和 4 个 Workspace 没有被稀释
* 产品核心仍是“内容策划编译系统”

---

# 二、验收方式建议

我建议你把验收分成三种：

## 1. 自测（工程师/AI coding 自跑）

目标：

* 看功能是否存在
* 看链路是否能跑
* 看异常处理是否正常

## 2. 走查（产品/研发/算法一起过）

目标：

* 看对象和页面是否统一
* 看动作与 AI 结果是否一致
* 看是否符合产品定位

## 3. 业务试跑（运营/策划真实操作）

目标：

* 看工作流是否顺
* 看 AI 是否真的减负
* 看方案是否可直接被使用

下面清单默认三者都能用，但我会标注哪些更适合自测，哪些更适合业务试跑。

---

# 三、L0：架构与依赖验收清单

这层先验证 Hermes / DeerFlow 接入是否“站住”。

---

## 3.1 Hermes-Agent 基座接入验收

### 检查项

* [ ] Hermes 相关 runtime 已可启动
* [ ] memory provider 已可初始化
* [ ] skill registry 已加载
* [ ] session / project memory 可写入可读取
* [ ] cross-session memory 可按项目或对象查询
* [ ] 记忆读取不会阻塞主链路
* [ ] memory miss 时系统可正常 fallback
* [ ] self-evolution / learning hooks 不影响主流程运行
* [ ] 关键 skill 有注册信息、版本信息、描述信息
* [ ] skill 调用失败时有明确错误日志

### 验收标准

* 任意一个 Workspace 发起 AI 行为时，都能看到 Hermes 侧的：

  * 当前 project / session context
  * skill 调用记录
  * memory retrieval 记录

### 失败信号

* AI 每次像“第一次见到项目”
* 不同页面的 AI 结果彼此无记忆关联
* skill 注册了但从未真正被用到

---

## 3.2 DeerFlow 编排层接入验收

### 检查项

* [ ] Workflow graph 已定义并可运行
* [ ] 每个核心阶段都是 graph 节点，不是散落脚本
* [ ] 支持 node 级状态追踪
* [ ] 支持 partial rerun
* [ ] 支持 subagent delegation
* [ ] 支持 sandbox tool execution
* [ ] 每个线程 / 每个任务实例隔离良好
* [ ] 任务中断后可恢复或重试
* [ ] event bus / SSE 能同步关键状态
* [ ] graph 失败节点能返回可解释错误

### 验收标准

至少能在日志/调试面板中看到：

* 当前跑到哪个节点
* 输入对象 ID
* 输出对象 ID
* 哪个 subagent / skill 被调用
* 哪个 sandbox action 被执行

### 失败信号

* 仍然主要靠同步按钮串行调用
* 一旦失败就整链重跑
* 看不见 graph 状态

---

## 3.3 分层边界验收

### 检查项

* [ ] Hermes 负责 memory / skill / learning
* [ ] DeerFlow 负责 workflow / subagent / sandbox
* [ ] 你们的业务 schema 仍然在自己的产品层
* [ ] 没有把业务对象直接埋进 Hermes 内部结构
* [ ] 没有把产品页面逻辑直接写进 DeerFlow graph 节点

### 验收标准

能明确回答每个核心模块属于哪一层：

* Agent Base
* Workflow Harness
* Workspace Product Layer

### 失败信号

* 业务逻辑和基座逻辑强耦合
* 后续很难替换某一层而不影响全部

---

# 四、L1：对象链与数据模型验收清单

这是最核心的一层。

---

## 4.1 对象链闭合验收

必须保证以下对象都存在，并且互相引用完整：

* [ ] `OpportunityCard`
* [ ] `OpportunityReview`
* [ ] `OpportunityBrief`
* [ ] `TemplateMatchSet`
* [ ] `RewriteStrategy`
* [ ] `NewNotePlan`
* [ ] `MainImagePlan`
* [ ] `ImageSlotPlan`
* [ ] `AssetBundle`
* [ ] `VariantSet`
* [ ] `ImageExecutionBrief`
* [ ] `ExportPackage`

### 对每个对象检查

* [ ] 是否有 schema
* [ ] 是否有构造来源
* [ ] 是否有消费方
* [ ] 是否能 API 返回
* [ ] 是否能前端展示
* [ ] 是否带回溯字段

---

## 4.2 回溯字段一致性验收

关键字段：

* `opportunity_id`
* `review_id` / review refs
* `brief_id`
* `template_id`
* `strategy_id`
* `plan_id`
* `asset_bundle_id`
* `variant_id`
* `source_note_ids`

### 检查项

* [ ] `OpportunityBrief.opportunity_id` 存在
* [ ] `TemplateMatchSet.brief_id` 存在
* [ ] `RewriteStrategy.opportunity_id / brief_id / template_id` 存在
* [ ] `NewNotePlan.opportunity_id / brief_id / strategy_id / template_id` 存在
* [ ] `MainImagePlan` 已带 `opportunity_id / brief_id / strategy_id`
* [ ] `AssetBundle` 能反查到 plan / strategy / template / opportunity
* [ ] `VariantSet` 能反查到 asset_bundle_id
* [ ] 导出包能反查 lineage

### 验收标准

任意一条资产都能追溯到：
`Asset -> Plan -> Strategy -> Template -> Brief -> Opportunity -> Source Note`

### 失败信号

* 资产生成出来了，但不知道来自哪个机会卡
* plan 看起来对，但不能回查之前的策略选择

---

## 4.3 版本与 lineage 验收

### 检查项

* [ ] 同一机会允许多个 brief 版本
* [ ] 同一 brief 允许多个 strategy 版本
* [ ] 同一 strategy 允许多个 plan 版本
* [ ] 同一 plan 允许多个 asset / variant
* [ ] 前端能看到 lineage
* [ ] compare 能基于 lineage 工作

### 验收标准

在任何一个对象详情页，都能看到：

* 来源版本
* 当前版本
* 相关兄弟版本
* 变更摘要

---

# 五、L2：Context OS / Stage OS 验收清单

这层是 V2 的核心产品升级。

---

## 5.1 PlanningContextAssembler 验收

### 检查项

* [ ] 所有 AI 调用都通过统一 context assembler
* [ ] Opportunity Workspace 注入机会、证据、review、历史相似机会
* [ ] Planning Workspace 注入 brief、strategy、模板候选、历史偏好
* [ ] Creation Workspace 注入 plan、strategy、template、机会摘要
* [ ] Asset Workspace 注入 asset、variant、lineage、history
* [ ] Council 调用与 run-agent 调用共用上下文基座
* [ ] 最近共识 / open questions / blockers 可自动注入
* [ ] 同项目跨页面上下文能延续

### 自测方法

在 4 个页面分别触发 AI 分析，检查日志里 context payload 是否符合页面语境。

### 通过标准

用户在不同页面提问同样的话，AI 会基于当前页面对象给出不同但合理的回应。

---

## 5.2 StageHealthChecker 验收

### 检查项

* [ ] 每个 Workspace 页面加载时自动执行轻量健康检查
* [ ] 检查结果结构化输出
* [ ] health issue 可区分 warning / blocker
* [ ] blocker 会阻止关键 CTA
* [ ] warning 只提醒，不阻止
* [ ] health 结果可被 SSE 更新
* [ ] 字段缺失、对象冲突、未完成环节都能识别
* [ ] 同一问题不会重复弹过多提示

### 页面级通过标准

#### Opportunity Workspace

* [ ] 证据不足会提示
* [ ] review 不足会提示
* [ ] promoted 不可进入 Brief 时会拦截

#### Planning Workspace

* [ ] brief 缺 target_user / target_scene / core_selling_points 会提示
* [ ] strategy 与 brief 不一致会提示
* [ ] template 与 planning_direction 冲突会提示

#### Creation Workspace

* [ ] title 为空会提示
* [ ] body outline 缺关键段会提示
* [ ] 5 图位缺失或职责冲突会提示

#### Asset Workspace

* [ ] asset 未完整生成会提示
* [ ] variant 未评估会提示
* [ ] export package 不完整会提示

---

## 5.3 NextStepAdvisor 验收

### 检查项

* [ ] 每页顶部有 suggestion chips
* [ ] 建议基于阶段状态，不是固定文案
* [ ] 建议能映射到 action
* [ ] 不同页面建议不同
* [ ] 建议支持一键执行
* [ ] 建议不会过量刷屏

### 通过标准

用户无需自己想下一步，只要看页面顶部建议就能继续推进。

---

# 六、L3：Decision OS / Action OS 验收清单

---

## 6.1 LeadAgent / Routing 验收

### 检查项

* [ ] 当前页面作为强约束输入
* [ ] 路由优先走确定性规则
* [ ] LLM 只作为兜底
* [ ] 意图结果能区分：

  * analyze
  * generate
  * discuss
  * evaluate
  * apply
* [ ] 路由日志可查看
* [ ] 错误路由率可统计

### 页面级样例自测

#### Planning Workspace

用户说：

* “帮我优化 brief”
* “重新匹配模板”
* “给我 3 套策略”
* “发起讨论”

检查是否分别路由到正确能力。

---

## 6.2 Council / Discussion 验收

### 检查项

* [ ] Council 不再只是长文本输出
* [ ] 输出至少有：

  * consensus
  * disagreements
  * proposed_updates / proposed_actions
* [ ] 支持跨讨论历史共识注入
* [ ] 支持基于同一对象重复发起 discussion
* [ ] discussion 输出可 apply 到对应对象
* [ ] 支持 block-level diff preview

### 通过标准

Council 结果至少可以直接作用于：

* Brief 字段
* Strategy block
* Plan block
* Asset variant

### 失败信号

* 讨论很长，但不能落地
* 用户看完仍要自己手动改对象

---

## 6.3 ActionSpec 验收

### 检查项

* [ ] 所有可执行动作都走统一协议
* [ ] action 有 target_object / target_field
* [ ] action 支持 preview_diff
* [ ] action 支持 confirmation_required
* [ ] action 可映射到具体 API
* [ ] action 执行后对象刷新正常
* [ ] action 支持 telemetry

### 样例动作覆盖

* [ ] `generate_brief`
* [ ] `promote_opportunity`
* [ ] `rematch_templates`
* [ ] `generate_strategy`
* [ ] `lock_strategy_block`
* [ ] `compile_note_plan`
* [ ] `regenerate_title`
* [ ] `regenerate_image_slot`
* [ ] `generate_asset_bundle`
* [ ] `generate_variants`
* [ ] `mark_published`
* [ ] `submit_feedback`

### 通过标准

任何 AI 建议最后都能变成：

* 一个明确动作
* 一个明确预览
* 一个明确结果

---

# 七、L4：Compiler OS 验收清单

---

## 7.1 Opportunity -> Brief 编译验收

### 检查项

* [ ] promoted 机会卡能直接生成 brief
* [ ] brief 不是临时字符串拼接
* [ ] target_scene / audience / core_selling_points / why_now / why_it_works / planning_direction 可稳定生成
* [ ] brief 可人工编辑并保存版本
* [ ] 编辑后会触发下游提醒

---

## 7.2 Brief -> Template -> Strategy 编译验收

### 检查项

* [ ] 能稳定返回 top3 模板
* [ ] rationale 合理
* [ ] 支持同一 brief 生成多套 strategy
* [ ] 支持 strategy compare
* [ ] 支持锁 block
* [ ] 支持局部重写 strategy block

### 通过标准

Planning Workspace 可以完成：

* 策略生成
* 策略对比
* 策略锁定
* 编译为 NotePlan

---

## 7.3 Strategy -> NewNotePlan 编译验收

### 检查项

* [ ] `NewNotePlan` 完整生成
* [ ] 包含标题区、正文区、5 图位区、标签策略、发布建议
* [ ] `MainImagePlan` 正确嵌入
* [ ] 单个 `ImageSlotPlan` 支持单独重生成
* [ ] 计划对象支持版本管理
* [ ] lock 后的 block 不会被误重写

---

## 7.4 NewNotePlan -> AssetBundle 编译验收

### 检查项

* [ ] 可生成标题变体
* [ ] 可生成正文变体
* [ ] 可生成单图位 `ImageExecutionBrief`
* [ ] 可批量生成 `VariantSet`
* [ ] 可导出 `ExportPackage`
* [ ] 可支持未来 SKU / 详情 / 视频扩展

### 通过标准

Asset Workspace 不是纯展示页，而是真正能产出资产包。

---

# 八、L5：四个 Workspace 页面级验收清单

下面按页面给你最实用的 checklist。

---

# 页面 1：Opportunity Workspace

## 1. 页面基础

* [ ] 左栏机会池可筛 promoted / reviewed / pending
* [ ] 支持场景 / 风格 / 卖点 / 品类 / 互动强度筛选
* [ ] 中栏显示当前机会详情
* [ ] 右栏协作区可用

## 2. 对象展示

* [ ] `OpportunityCard` 详情完整
* [ ] `OpportunityReview` 可查看
* [ ] `SourceNotePreview` 可预览
* [ ] evidence blocks 可展开

## 3. 关键动作

* [ ] review / promoted / archive 可执行
* [ ] AI 分析建议可触发
* [ ] `生成 Brief` 正常工作
* [ ] `查看历史版本` 可查看
* [ ] `进入策划` 正常跳转

## 4. AI 原生能力

* [ ] 页面顶部显示机会健康状态
* [ ] 有进入 Brief 的推荐建议
* [ ] 有相似历史机会记忆
* [ ] review 后 AI 建议会变化

## 5. 失败回退

* [ ] 无法 promoted 时有明确原因
* [ ] source note 缺失时有错误提示
* [ ] AI 分析失败时不影响人工 review

---

# 页面 2：Planning Workspace

## 1. 页面基础

* [ ] 左栏 Brief 面板展示完整
* [ ] 中栏模板与策略主区可切换
* [ ] 右栏动作与版本区可用

## 2. 对象展示

* [ ] `OpportunityBrief` 可编辑
* [ ] `TemplateMatchSet` 显示 top3
* [ ] `RewriteStrategy` block view 清晰

## 3. 关键动作

* [ ] 编辑 Brief 后可保存
* [ ] 重新匹配模板可用
* [ ] 生成多套 Strategy 可用
* [ ] Strategy 比较可用
* [ ] block 锁定可用
* [ ] 局部重写某 block 可用
* [ ] `编译为 NotePlan` 可用

## 4. AI 原生能力

* [ ] 顶部显示 brief health / readiness
* [ ] 模板匹配有 rationale
* [ ] Strategy 可视化比较
* [ ] Council 可产出可 apply 的 diff

## 5. 一致性检查

* [ ] 改 Brief 后能提示需要更新 Strategy
* [ ] 换模板后旧 Strategy 不会被误认为最新
* [ ] 锁定 block 后不会被后续策略重写

---

# 页面 3：Creation Workspace

## 1. 页面基础

* [ ] 左栏上下文完整
* [ ] 中栏 Plan Board 可用
* [ ] 右栏局部编辑区能跟随选中对象切换

## 2. 对象展示

* [ ] `NewNotePlan` 完整显示
* [ ] `MainImagePlan` 嵌入正常
* [ ] `ImageSlotPlan` 逐个可查看
* [ ] `TitleCandidateSet` / `BodyOutline` 可展示

## 3. 关键动作

* [ ] 重生成标题可用
* [ ] 重生成正文 outline 可用
* [ ] 选中第 N 个图位可查看明细
* [ ] 单独重生成某图位可用
* [ ] 图位锁定可用
* [ ] 图位版本比较可用
* [ ] `生成资产包` 可用

## 4. AI 原生能力

* [ ] 右侧 inspector 根据当前选中对象变化
* [ ] 每个图位有 role / intent / visual_brief / copy_hints
* [ ] plan consistency 问题能提示
* [ ] AI 可基于单个图位提出 action chips

## 5. 关键通过标准

用户可以在这一页完成“对象化共创”，而不是只能整体重跑。

---

# 页面 4：Asset Workspace

## 1. 页面基础

* [ ] 左栏 lineage / 上下文完整
* [ ] 中栏 Tab 内容可切换
* [ ] 右栏导出与审核区可用

## 2. 对象展示

* [ ] `AssetBundle` 可见
* [ ] `VariantSet` 可见
* [ ] `ImageExecutionBrief` 可见
* [ ] `ExportPackage` 可见

## 3. 关键动作

* [ ] 生成标题变体可用
* [ ] 生成正文变体可用
* [ ] 单独重生成某个图位执行 brief 可用
* [ ] 生成多个 Variant 可用
* [ ] 比较 Variant A / B 可用
* [ ] 导出 JSON / Markdown / image package 可用
* [ ] 标记 ready / published 可用
* [ ] 回填效果可用

## 4. AI 原生能力

* [ ] Judge Agent 给出结构化评分
* [ ] 回填结果触发 review loop
* [ ] 发布后建议下一轮优化方向

## 5. 关键通过标准

这页必须体现“生产与交付”，不能只是最终结果展示页。

---

# 九、L6：业务验收 / 试跑清单

这是最接近真实价值的一层。

---

## 9.1 业务试跑样本准备

建议至少准备：

* [ ] 10 条 promoted 机会卡
* [ ] 覆盖 3 类机会类型
* [ ] 覆盖简单 / 中等 / 复杂三档
* [ ] 每条都至少有 1 条 source note、1 条 review

---

## 9.2 业务试跑任务清单

### 任务 1：从机会到 Brief

* [ ] 运营能在 3 分钟内完成一次机会判断并生成 Brief
* [ ] 能理解 why_now / why_it_works / planning_direction

### 任务 2：从 Brief 到 Strategy

* [ ] 能看懂 top3 模板区别
* [ ] 能比较两套 strategy
* [ ] 能决定用哪套

### 任务 3：从 Strategy 到 Plan

* [ ] 能理解 5 个图位职责
* [ ] 能单独调整某图位
* [ ] 能接受 AI 的标题/正文建议

### 任务 4：从 Plan 到 Asset

* [ ] 能导出一个资产包
* [ ] 能比较 2 个变体
* [ ] 能标记发布并回填

---

## 9.3 业务通过标准

* [ ] 80% 以上试跑者能在无额外培训下完成完整链路
* [ ] 70% 以上认为“比人工从零策划更快”
* [ ] 60% 以上认为“AI 建议是有帮助的，不只是装饰”
* [ ] 至少一半用户会使用局部重生成，而不是全链路重跑

---

# 十、L7：稳定性 / 异常 / 上线前回归清单

---

## 10.1 稳定性

* [ ] 所有 AI 接口有 timeout
* [ ] 有 fallback 路径
* [ ] LLM 失败时页面不崩
* [ ] memory retrieval 失败时流程可继续
* [ ] sandbox 异常时能明确报错
* [ ] deerflow graph 中断能重试

---

## 10.2 安全与约束

* [ ] action chips 带确认机制
* [ ] destructive actions 不会误触发
* [ ] 应用 diff 前可预览
* [ ] 导出资产时带 lineage 信息
* [ ] 项目记忆不会串项目污染

---

## 10.3 性能

* [ ] 页面首屏加载时间可接受
* [ ] StageHealthChecker 不阻塞主线程
* [ ] 顶部建议生成时间可接受
* [ ] 大对象切换不卡顿
* [ ] 多个 Variant 生成时前端可感知进度

---

## 10.4 回归测试

* [ ] 旧的单次分析不崩
* [ ] 旧的模板库展示页不崩
* [ ] 旧的 MainImagePlan 编译逻辑兼容
* [ ] 原有 promoted 机会卡 review 流程不受影响

---

# 十一、推荐的验收输出物

建议你最终至少产出这 4 份东西：

## 1. 技术验收报告

包括：

* 架构层通过情况
* 对象链通过情况
* API 通过情况
* 异常处理情况

## 2. 页面验收报告

4 个 Workspace 每页一页：

* 已实现能力
* 未通过项
* 阻塞项

## 3. 业务试跑报告

包括：

* 样本数
* 平均完成时长
* AI 采纳率
* 常见问题

## 4. 上线阻塞清单

只列：

* 阻塞上线的问题
* 风险但不阻塞的问题
* 上线后再补的问题

---

# 十二、一版最短的“上线前通关标准”

如果你要一个最短版本，我建议上线前至少满足：

### 必须通过

* [ ] 4 个 Workspace 都能跑完整对象链
* [ ] Opportunity -> Brief -> Strategy -> Plan -> Asset 闭环跑通
* [ ] 所有关键对象可回溯
* [ ] Stage Header 可用
* [ ] ActionSpec 可执行
* [ ] 局部重生成可用
* [ ] 至少 10 条样本端到端通过率 >= 80%

### 可以上线后优化

* [ ] 更强的 self-evolution
* [ ] 更复杂的 council 角色
* [ ] 更强的协同编辑
* [ ] 更细的 lineage 可视化

---
