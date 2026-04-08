按 **三层架构** 做增量升级：

* **第 1 层：决策编译层**
* **第 2 层：对象交互层**
* **第 3 层：资产生产层**

当前系统已经具备从原始笔记到机会卡、人工检视、Brief、模板匹配、Rewrite Strategy、NotePlan、标题/正文/图片生成的完整原型链路，只是还没有生产级地“持久化、版本化、工作台化、资产包化、回流闭环化”。这也是这套分批清单的出发点。

---

# 使用原则


## 每一批都要附带这段约束

```text id="52095"
约束：
1. 只做本批次范围内改动，不要顺手大改无关模块
2. 不要使用 mock data / mock service
3. 必须基于当前真实小红书数据与已有服务增量升级
4. 优先复用已有模块：
   - XHSParsedNote / XHSOpportunityCard
   - review / promoted
   - Brief / TemplateMatcher / StrategyGenerator / NewNotePlanCompiler
   - 现有 API 风格
   - llm_client / label_zh / IntelHubAdapter
5. 输出：
   - 修改文件清单
   - 新增文件清单
   - 设计说明
   - 测试/验证命令
   - 风险说明
6. 如发现上游结构问题，先标出再最小修复，不要推翻重做
```

## 每一批最好要求 Codex 先“读后改”

```text id="79049"
先阅读相关模块并输出：
- 当前实现路径
- 受影响文件
- 最小修改方案
- 预期输出对象
我确认后再开始改代码。
```

---

# 总体分批结构

## Batch 1：决策编译层生产化基础

目标：把已有编译链做成可持久化、可回溯、可版本化的生产级骨架。

## Batch 2：决策编译层增强

目标：让机会卡、Brief、Strategy、Plan 更强、更可审阅、更适合后续策划。

## Batch 3：对象交互层工作台化

目标：把当前流程页升级成对象化工作台，而不是线性表单流程。

## Batch 4：资产生产层资产包化

目标：把标题/正文/图片 brief 升级成可导出、可协作、可回流的资产包。

## Batch 5：批量化、异步化、反馈闭环

目标：让系统进入生产环境可持续运行。

---

---

# Batch 1：决策编译层生产化基础

这一批最重要。
不要急着改 UI，先把地基做稳。

---

## Prompt 1.1：会话持久化与对象落库

```text id="92476"
目标：把当前内容策划链从纯内存会话升级为可持久化对象流。

背景：
当前系统已实现：
- 原始笔记解析
- 机会卡生成
- 人工 review / promote
- Brief → 模板匹配 → Rewrite Strategy → NewNotePlan → 标题/正文/图片生成

但目前 _SessionState 仍是纯内存 dict，无法支持断点续做、多用户、版本比较、资产回溯。

请完成：
1. 阅读当前内容策划链相关模块，定位 _SessionState、Brief、TemplateMatch、RewriteStrategy、NewNotePlan、生成结果在内存中的流转路径
2. 设计并实现一个最小可用的持久化方案，优先使用 SQLite（若项目已有更合适持久层可复用）
3. 至少持久化这些对象：
   - OpportunityBrief
   - TemplateMatchResult / SelectedTemplate
   - RewriteStrategy
   - NewNotePlan
   - GeneratedTitles
   - GeneratedBody
   - GeneratedImageBriefs
4. 支持通过 ID 回查与继续执行
5. 设计状态字段，例如：
   - draft
   - generated
   - reviewed
   - approved
   - exported
6. 不推翻现有 service，只做最小侵入式接入

输出：
- 新增/修改文件清单
- 表结构或存储结构
- 对象间关联关系
- 验证方式
```

---

## Prompt 1.2：pipeline_run_id / lineage / version chain

```text id="95971"
目标：为整条编译链增加运行追踪、对象 lineage 和版本链。

背景：
当前系统已有从原始笔记到内容策划的完整编译链，但缺少 pipeline_run_id 和稳定的版本追踪，不利于回溯、对比和评估。

请完成：
1. 为一次完整编译运行生成 pipeline_run_id
2. 在这些对象中补充 lineage 字段：
   - XHSOpportunityCard
   - OpportunityBrief
   - RewriteStrategy
   - NewNotePlan
   - Generated asset objects
3. lineage 至少包含：
   - source_note_ids
   - opportunity_id
   - review_id / promote status（如可得）
   - brief_id
   - template_id
   - strategy_id
   - plan_id
   - pipeline_run_id
4. 增加 version chain 支持：
   - parent_version_id
   - derived_from_id
5. 保持向后兼容，旧对象允许空字段
6. 尽量不要大范围改 schema 风格

输出：
- 改动文件清单
- lineage 结构定义
- 示例对象
- 验证脚本或测试
```

---

## Prompt 1.3：Prompt Registry / Prompt 配置化

```text id="51568"
目标：把当前硬编码在代码里的 Prompt 抽离成可版本管理的 Prompt Registry。

背景：
当前策略生成、标题生成、正文生成、图片 brief 生成等环节存在 LLM 调用，Prompt 逻辑散落在代码中，不利于多品类扩展、版本管理和 A/B 优化。

请完成：
1. 全局搜索以下模块中的 Prompt / system prompt / user prompt 逻辑：
   - strategy_generator.py
   - title_generator.py
   - body_generator.py
   - image_brief_generator.py
   - 其他直接调用 llm_client 的编译模块
2. 设计 Prompt Registry 目录结构，例如：
   - prompts/strategy/
   - prompts/title/
   - prompts/body/
   - prompts/image_brief/
3. 支持按场景/模板/品类选择 Prompt
4. 改造调用方式，使 service 从 registry 加载 prompt，而不是内联硬编码
5. 保持当前行为不变，先做结构性重构，不优化 prompt 内容本身

输出：
- 新目录结构
- 改动文件清单
- Prompt 加载方式说明
- 验证方式
```

---

# Batch 2：决策编译层增强

这一批是在地基稳后，把“判断对象”和“策划对象”做强。

---

## Prompt 2.1：机会卡增强（互动洞察 + 跨模态结论 + insight_statement）

```text id="41647"
目标：增强 XHSOpportunityCard，使其更像“运营判断卡”，而不是 refs 容器。

背景：
当前机会卡已经能通过本体映射 + 规则编译生成，但下一阶段需要让它更适合后续策划和人工决策。现有实现已经包含机会卡编译器、互动数据、跨模态结果以及 insight_statement 方向，需要基于真实实现进一步强化。

请完成：
1. 阅读当前 opportunity_compiler、cross_modal_validator、parsed_note.engagement_summary 等真实实现
2. 增强 XHSOpportunityCard，补强这些字段（如已有则优化生成逻辑）：
   - interaction_insight / engagement_evidence
   - validation_summary / validation_interpretation
   - insight_statement
   - action_recommendation
   - opportunity_strength_score（若当前缺少综合强度）
3. 编译逻辑必须使用真实互动数据：
   - like_count
   - collect_count
   - comment_count
   - share_count
   - save_ratio / collect_like_ratio / total engagement 等
4. 把 CrossModalValidation 的结论沉淀到机会卡中，而不只是用于阈值过滤
5. 输出结果要更适合运营理解与后续 Brief 生成

要求：
- 先基于现有字段最小扩展
- 不要让卡片退化成大段自然语言
- 保持证据可追溯
- 输出测试或示例对象
```

---

## Prompt 2.2：BriefCompiler 升级

```text id="26402"
目标：把 BriefCompiler 从“字段搬运器”升级成“策划编译器”。

背景：
当前 Brief 已经能从机会卡生成，但接下来需要显著增强：
- why_now
- why_it_works
- differentiation_view
- proof_blocks
- planning_direction

请完成：
1. 阅读当前 brief_compiler.py 和 OpportunityBrief schema
2. 在不推翻现有 Brief 的前提下补强以下结构：
   - why_now
   - why_it_works
   - differentiation_view
   - proof_blocks
   - planning_direction
3. 这些字段必须综合使用：
   - 机会卡中的核心机会判断
   - parsed_note 的互动数据与 engagement_summary
   - CrossModalValidation 的结论
   - review / promote 结果
4. proof_blocks 要结构化，不要只是 snippet 列表
5. planning_direction 要为后续模板匹配和策略生成提供更直接输入
6. 输出结果要适合前端工作台直接展示

要求：
- 先用规则编译为主
- 保持中文友好
- 不做大而全自然语言总结
- 输出修改文件与示例
```

---

## Prompt 2.3：TemplateMatcher 多候选与解释增强

```text id="47831"
目标：增强模板匹配层，使其适合策略对比，而不是只产一个 top1。

背景：
当前模板匹配已实现，且支持 LLM 优先 / 规则兜底。下一阶段需要支持对象交互层的多策略对比。

请完成：
1. 阅读 template_matcher.py 的当前实现
2. 输出结构从“单一推荐”增强为：
   - top_k templates
   - 每个模板的 score
   - rationale
   - matched_dimensions（scene / goal / style / hook / avoid）
3. 允许前端工作台读取 top3 候选，并切换模板后重新生成策略
4. 保持 LLM 优先、规则兜底逻辑不变
5. 提升结果的可解释性，但不引入额外大模型依赖

输出：
- schema / 返回结构调整
- 受影响调用链
- 验证方式
```

---

## Prompt 2.4：RewriteStrategy 增强为可对比对象

```text id="53258"
目标：把 RewriteStrategy 做成真正可对比、可编辑、可局部重编译的对象。

背景：
当前 strategy_generator 已可生成完整 RewriteStrategy。下一阶段需要支撑：
- 多模板策略对比
- 局部重编译
- 工作台显示与人工编辑

请完成：
1. 阅读当前 RewriteStrategy schema 和 strategy_generator.py
2. 增强 RewriteStrategy 结构，使其明确区分：
   - title_strategy
   - body_strategy
   - image_strategy
   - hook_strategy
   - tone_of_voice
   - must_keep
   - should_avoid
   - differentiation_points
   - scene_emphasis
3. 增加字段支持：
   - strategy_version
   - comparison_note（可选）
   - editable_blocks
4. 保持与现有 NotePlanCompiler 兼容
5. 支持同一 Brief 派生多套 Strategy

输出：
- 改动文件
- 版本与对比结构说明
- 示例对象
```

---

# Batch 3：对象交互层工作台化

这一批开始真正补你们的“下一代产品感”。

---

## Prompt 3.1：重构工作台信息架构

```text id="74579"
目标：把当前内容策划 HTML 工作台从“流程页”升级为“对象工作台”。

背景：
当前已有：
- /content-planning/brief/
- /content-planning/strategy/
- /content-planning/plan/

但下一阶段需要围绕当前对象工作，而不是只是按步骤跳转。

请完成：
1. 阅读现有 Jinja2 模板、前端页面、对应 API
2. 重构页面信息架构，形成 3 个工作台：
   - Opportunity Workspace
   - Planning Workspace
   - Asset Workspace
3. 保留现有页面能力，但重新组织为：
   - 当前对象锚点
   - 左侧上下文
   - 中间核心对象视图
   - 右侧动作/局部编辑/版本切换
4. 不必做最终视觉精修，先完成信息架构与交互结构调整
5. 保持真实 API 接入，不使用 mock

输出：
- 路由调整建议
- 模板/页面改动清单
- 每页对象模型
- 页面流转关系
```

---

## Prompt 3.2：局部失效与局部重算显式化

```text id="89495"
目标：把当前已有的“下游缓存失效逻辑”升级为用户可理解的对象级状态机制。

背景：
当前 OpportunityToPlanFlow 已能在 Brief 修改后让下游缓存失效。下一阶段需要把这种逻辑显式化到系统层，便于前端工作台和后续局部编辑。

请完成：
1. 阅读 OpportunityToPlanFlow 当前的状态管理和缓存失效逻辑
2. 设计对象级 stale / dirty / regenerated 状态
3. 至少覆盖：
   - Brief 改动后，TemplateMatch / Strategy / Plan / Assets 的失效
   - Template 改动后，Strategy / Plan / Assets 的失效
   - Strategy 改动后，Plan / Assets 的失效
   - 单个 ImageSlot 改动后，仅对应 image brief 失效
4. 输出清晰的状态流转逻辑
5. 尽量最小改动接入现有实现

输出：
- 状态设计
- 改动文件
- 示例流程
```

---

## Prompt 3.3：多策略对比视图支撑

```text id="86511"
目标：让同一 Brief 支持多模板/多策略对比，并在工作台中可并排展示。

背景：
系统已有模板匹配和策略生成，但当前默认链路偏 top1。下一阶段需要支持：
- 同一 Brief 下的多模板候选
- 多套 Strategy 对比
- 多套 Plan 比较

请完成：
1. 调整服务层和 API，允许在同一 brief_id 下保存多条策略记录
2. 允许同一 strategy 对应多个 derived plan 版本
3. 输出用于前端并排对比的结构
4. 不要一次性重构 UI，先把后端对象和 API 结构准备好

输出：
- schema / API / 存储调整
- 对比视图的数据结构
- 验证方式
```

---

## Prompt 3.4：图位级对象化

```text id="88264"
目标：把 MainImagePlan 里的 ImageSlotPlan 真正升级为可独立操作对象。

背景：
当前系统已有 MainImagePlan 和 image_brief_generator。下一阶段需要让每个图位成为可单独查看、比较、重编译的对象。

请完成：
1. 阅读 MainImagePlan / ImageSlotPlan / image_brief_generator
2. 为每个 ImageSlot 引入稳定 ID 与版本信息
3. 支持：
   - 单独查看 slot 的 role / intent / visual_brief / copy_hints
   - 单独触发 image brief 重生成
   - 单独记录修改与 lineage
4. 保持 MainImagePlan 顶层结构不被破坏
5. 为对象交互层预留良好 API

输出：
- schema 调整
- generator 接口调整
- 示例返回结构
```

---

# Batch 4：资产生产层资产包化

这一批让系统从“能生成几个结果”升级成“能交付一整包资产”。

---

## Prompt 4.1：AssetBundle 统一对象

```text id="11199"
目标：把当前零散的标题、正文、图片 brief 输出统一成 AssetBundle。

背景：
当前系统已经能生成标题、正文、图片 brief，但仍偏分散。下一阶段需要一个统一的资产包对象，便于导出、审批、协作和回流。

请完成：
1. 新增 AssetBundle schema
2. 至少包含：
   - asset_bundle_id
   - plan_id
   - title_candidates
   - body_outline / body_draft
   - image_execution_briefs
   - optional: sku_direction / detail_outline / video_outline
   - export_status
   - lineage
3. 改造 title/body/image 生成结果，使其最终可组装为 AssetBundle
4. 提供统一获取接口

输出：
- 新对象结构
- 改动文件
- 组装流程说明
```

---

## Prompt 4.2：导出层

```text id="42517"
目标：为 AssetBundle 增加企业可用的导出能力。

背景：
当前系统生成结果还缺少运营可直接使用的导出格式。下一阶段需要支持将内容资产包导出给运营、设计、飞书/Notion 等外部协作环境。

请完成：
1. 为 AssetBundle 支持以下导出格式：
   - JSON
   - Markdown brief
   - 文本型 image execution package
2. 设计一个统一导出接口
3. 输出文件命名规范
4. 保持与现有工作台兼容
5. 不接复杂第三方 API，先把标准化导出物做出来

输出：
- 导出 service
- API 端点
- 示例导出内容
```

---

## Prompt 4.3：批量内容资产生产

```text id="18459"
目标：支持从多张 promoted 机会卡批量生成 AssetBundle。

背景：
当前系统主要是单条链路可跑通。生产环境需要批量调度和进度追踪。

请完成：
1. 设计批量编译入口：
   - 输入：多个 promoted opportunity_id
   - 输出：多个 AssetBundle
2. 支持最小进度追踪
3. 支持部分成功、部分失败
4. 先用同步/半同步方式实现，不强制引入任务队列
5. 输出结构要适合后续异步化

输出：
- 批量接口
- 返回结构
- 失败处理方式
```

---

# Batch 5：批量化、异步化、反馈闭环

这一批是从“原型系统”走向“生产系统”。

---

## Prompt 5.1：异步并行生成

```text id="82651"
目标：把当前串行的标题/正文/图片生成升级为并行任务，提高内容策划链效率。

背景：
当前策划链中的多个 LLM 调用大概率串行执行。下一阶段需要并行化：
- title generation
- body generation
- image brief generation

请完成：
1. 阅读当前 content planning 生成链调用顺序
2. 找出可以并行的步骤
3. 优先用 asyncio 做最小并行化
4. 保持错误隔离：
   - 某一路失败不影响其他路输出
5. 输出：
   - 改动说明
   - 性能收益预估
   - 风险说明
```

---

## Prompt 5.2：运营看板基础指标

```text id="76495"
目标：增加运营看板所需的基础统计指标，为生产环境管理提供可视化数据。

背景：
当前系统已有很多链路对象，但缺少全局统计。需要先补最基础的指标聚合。

请完成：
1. 聚合这些指标：
   - 机会卡通过率 / promoted rate
   - 模板命中分布
   - 策略生成耗时
   - 资产生成耗时
   - 各阶段失败率
2. 输出一个最小 dashboard data API
3. 不做复杂 BI 页，先把指标数据准备好
4. 保持可扩展

输出：
- 指标定义
- 聚合逻辑
- API 端点
```

---

## Prompt 5.3：效果回流闭环

```text id="12933"
目标：为“发布效果 -> 机会卡/模板/策略优化”建立最小回流结构。

背景：
下一阶段最重要的长期能力，是把生成内容发布后的真实效果回流到系统，形成 Review-to-Asset 的闭环。

请完成：
1. 设计最小回流对象：
   - published_asset_result
   - engagement_result
   - template_effectiveness_record
2. 支持把发布后互动数据回写到：
   - opportunity
   - template
   - strategy
   - asset bundle
3. 先不做复杂自动学习，只把数据结构和回写能力做好
4. 输出：
   - schema
   - service
   - API
   - 未来可如何用于模板 A/B 和机会判断优化
```

