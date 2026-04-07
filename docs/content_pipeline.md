基于现有真实小红书数据、已有服务和审计结论，逐步补齐后半链路

这版 围绕 5 个断点展开：

* promoted 机会卡 → OpportunityBrief
* Brief → 模板选择
* 模板 → RewriteStrategy
* RewriteStrategy → NewNotePlan
* NewNotePlan → 标题/正文/图片策划 



---

# 0. 总控 Prompt

先给 AI-coding 一个总背景，让它别偏题。

```text id="64998"
你正在维护一个“小红书笔记 -> 内容策划工作台”项目。当前系统前半链路已完成，后半链路未打通。

已完成：
1. 原始笔记采集与解析
2. 三维信号提取（视觉 / 卖点主题 / 场景）
3. 跨模态校验
4. 本体映射
5. 机会卡生成
6. 人工评分、review 聚合、promoted 判定
7. 6 套策略模板库
8. 模板匹配器
9. MainImagePlanCompiler（只覆盖 5 张主图策划）

未完成或断开：
1. OpportunityBrief schema + brief_compiler
2. promoted 机会卡 -> 模板选择桥接
3. RewriteStrategy schema + strategy_generator
4. 完整版 NewNotePlan
5. title_generator / body_generator / image_brief_generator
6. 完整链路 API
7. 基于真实数据的前后链路工作台收口

要求：
- 不要使用 mock data 或 mock service
- 必须基于现有真实小红书数据和当前已实现模块增量升级
- 不要推翻现有项目结构，尽量复用现有 schema、service、pipeline、template 模块
- 输出代码要工程化，便于逐步提交
- 每一步都要说明：改哪些文件、新增哪些文件、输入输出是什么、为什么这样做
- 优先补齐对象模型、服务层、API 层，再考虑 UI 收口

你后续会收到分批 Prompt，请严格按当前批次完成，不要一次性做太多无关重构。
```

---

# P0：修现有硬伤

这批先修最小但影响大的问题。

---

## Prompt P0-1：修 promoted 链路入口

```text id="22821"
请先做一个小范围增量改造，目标是让 promoted 机会卡真正成为后半链路入口。

背景：
当前 review_store.list_promoted_cards() 方法已经存在，但没有任何调用方，这导致 promoted 机会卡没有进入后半链路，这是后半链路的起点断点。

请完成：
1. 全局搜索 review_store.list_promoted_cards、opportunity_status="promoted" 以及 GET /xhs-opportunities 的现有调用关系
2. 找出最适合作为“后半链路入口”的 API 路由和前端页面入口
3. 增加一个明确的服务层函数，例如：
   - list_promoted_opportunities()
4. 如果当前 API 已支持 status / qualified 筛选，则尽量复用，不要重复造轮子
5. 在现有 UI 中增加一个清晰入口：
   - “Promoted 机会卡”
   - 或在机会卡列表中增加 promoted 过滤视图
6. 输出修改说明：
   - 改了哪些文件
   - 新增了哪些文件
   - 现有调用链如何变化
   - 后续 Brief 生成如何从这个入口接入

要求：
- 不做 mock
- 不改变现有 review 逻辑
- 不破坏已有列表页和 review 提交流程
- 尽量小改动先打通入口
```

---

## Prompt P0-2：修 TemplateMatcher 的 recommended_phrases bug

```text id="25485"
请修复 TemplateMatcher 中一个明确 bug，并补充最小测试。

背景：
审计指出 TemplateMatcher 中 recommended_phrases 的遍历逻辑是：
for word in phrase[:4]
这会遍历字符串前 4 个字符，而不是词，行为与设计意图不一致。

请完成：
1. 定位 apps/template_extraction/agent/template_matcher.py 中这段逻辑
2. 修复为符合中文短语匹配意图的实现
3. 给出你采用的匹配策略说明，例如：
   - 直接 phrase in text
   - 或做更稳妥的短语切分
4. 补充最小单元测试，覆盖：
   - 短语命中
   - 不命中
   - 多短语竞争
5. 不要大改 TemplateMatcher 的整体设计，只修这个 bug 和相关最小必要逻辑

输出：
- patch 说明
- 影响范围
- 为什么这样修
```

---

## Prompt P0-3：给 MainImagePlan 增加 lineage 关键字段

```text id="37924"
请对现有 MainImagePlan 做一次最小但关键的 schema 升级。

背景：
审计指出当前 MainImagePlan 没有 opportunity_id，无法回溯到来源机会卡；而 plan_compiler 虽然接收 opportunity_card 参数，但没有把 ID 写入输出。

请完成：
1. 找到 apps/template_extraction/schemas/agent_plan.py 中 MainImagePlan 的定义
2. 最小增量增加以下字段：
   - opportunity_id: str | None
   - source_note_ids: list[str] = []
   - brief_id: str | None = None
   - strategy_id: str | None = None
3. 找到 MainImagePlanCompiler，把可获得的 upstream lineage 写入 plan
4. 保持向后兼容，避免破坏现有调用方
5. 如有必要，为旧 plan 输出做默认值兜底
6. 补充最小测试

输出：
- schema 变更说明
- compiler 变更说明
- 回溯链路会如何改善
```

---

# P1：补对象模型

这批是最关键的架构升级。

---

## Prompt P1-1：新增 OpportunityBrief schema + service skeleton

```text id="24589"
请新增 OpportunityBrief 的领域对象，并建立最小可用的服务骨架。

背景：
当前系统不存在 OpportunityBrief schema，但后半链路到处都需要 brief。现在只是把 title + body[:100] 或 product_brief 字符串临时当 brief，这不够。

请完成：
1. 新增 OpportunityBrief Pydantic schema
2. 放在合适位置，命名与现有项目风格一致
3. 字段至少包含：
   - brief_id
   - opportunity_id
   - source_note_ids
   - brief_status
   - target_scene
   - core_selling_points
   - target_audience
   - price_positioning
   - visual_style_preference
   - content_intent
   - opportunity_summary
   - evidence_summary
   - constraints
   - suggested_direction
   - created_at
   - updated_at
4. brief_status 建议支持：
   - draft
   - generated
   - reviewed
   - approved
5. 新增一个 brief_compiler.py 的服务骨架文件，先定义接口，不一定一次性补完所有逻辑
6. brief_compiler 的输入设计为：
   - XHSOpportunityCard
   - 原始/解析后 note 上下文
   - review 聚合结果（如存在）
7. 输出为 OpportunityBrief

要求：
- 不要直接写成 LLM-only 黑盒
- schema 设计要考虑后续可审阅、可编辑、可回溯
- 先保证对象定义清晰
- 输出文件路径建议和代码说明
```

---

## Prompt P1-2：新增 RewriteStrategy schema

```text id="76817"
请新增 RewriteStrategy 的领域对象 schema，为后续策略生成服务做准备。

背景：
当前模板选择之后没有“具体怎么写”的翻译层。需要一个 RewriteStrategy，把模板规则和 OpportunityBrief 编译成标题策略、正文策略、图片策略等。

请完成：
1. 新增 RewriteStrategy Pydantic schema
2. 字段至少包含：
   - strategy_id
   - opportunity_id
   - brief_id
   - template_id
   - strategy_status
   - title_strategy
   - body_strategy
   - image_strategy
   - tone_of_voice
   - hook_strategy
   - cta_strategy
   - must_keep
   - should_avoid
   - differentiation_points
   - scene_emphasis
   - rationale
   - created_at
   - updated_at
3. strategy_status 建议支持：
   - draft
   - generated
   - reviewed
   - approved
4. schema 设计要便于后续前端结构化展示和局部重生成
5. 输出文件路径建议，并保持与现有 schemas 风格一致

要求：
- 这是领域对象，不要只做 dict
- 字段要考虑未来 title_generator / body_generator / image_brief_generator 的复用
```

---

## Prompt P1-3：新增完整版 NewNotePlan schema

```text id="20588"
请新增完整版 NewNotePlan 领域对象，并复用现有 MainImagePlan，而不是推翻它。

背景：
当前 MainImagePlan 只覆盖 5 张主图策划，不能表达完整内容方案。需要一个更上层的 NewNotePlan，整合标题、正文、图片策划、标签策略、发布建议。

请完成：
1. 保留现有 MainImagePlan 和 ImageSlotPlan
2. 新增 NewNotePlan schema
3. 至少包含字段：
   - plan_id
   - opportunity_id
   - brief_id
   - strategy_id
   - template_id
   - plan_status
   - title_candidates
   - body_outline
   - image_plan: MainImagePlan
   - tag_strategy
   - publish_advice
   - lineage
   - created_at
   - updated_at
4. 为 title_candidates / body_outline 设计最小结构化子对象
5. lineage 至少应记录：
   - opportunity_id
   - brief_id
   - strategy_id
   - template_id
   - source_note_ids
6. plan_status 建议支持：
   - draft
   - generated
   - reviewed
   - approved
   - exported

要求：
- 兼容现有 MainImagePlan
- 便于前端后续直接消费
- 不引入过度复杂嵌套
```

---

# P2：补服务层

---

## Prompt P2-1：实现 brief_compiler

```text id="51670"
请基于现有真实数据与服务，实现 OpportunityBrief 的 first usable version。

背景：
系统已有 promoted 机会卡、XHSParsedNote、review 聚合结果。现在要把它们编译成结构化 OpportunityBrief。

请完成：
1. 实现 brief_compiler 服务
2. 输入：
   - XHSOpportunityCard
   - 对应 XHSParsedNote / source notes
   - review 聚合结果（若有）
3. 输出：
   - OpportunityBrief
4. 编译逻辑优先采用规则 + 现有信号对象整合，不要直接一步到位全丢给 LLM
5. 建议编译：
   - target_scene：从 scene_refs / 场景信号归纳
   - core_selling_points：从 selling theme / summary / evidence 提取
   - target_audience：从 audience_refs / note 语义推断
   - visual_style_preference：从 style_refs / visual_signals 推断
   - content_intent：根据 opportunity_type + review + tags 粗分类
   - evidence_summary：从 evidence_refs 归并
6. 若字段无法高置信生成，允许给默认值或低置信占位
7. 补充最小测试
8. 给出示例输出

要求：
- 先可用，不求完美
- 输出要稳定、结构化
- 不要让 brief 退化成一段字符串
```

---

## Prompt P2-2：把 promoted card 正式接到模板匹配

```text id="50762"
请把“promoted 机会卡 -> 模板匹配”这条桥接正式接起来。

背景：
当前 TemplateMatcher 理论上接受 opportunity_card: dict | None，但实际上没有代码把 promoted 机会卡传给它。/strategy-templates 页面还是在用标题+正文临时拼接。

请完成：
1. 找出现有 TemplateMatcher 和 build_main_image_plan 的调用链
2. 新增或改造一个桥接服务，例如：
   - match_templates_for_opportunity_brief(brief, opportunity_card)
3. 输入必须优先使用：
   - OpportunityBrief
   - promoted XHSOpportunityCard
4. 仅在必要时用原始 note 文本做辅助
5. 返回：
   - top templates
   - score
   - rationale
6. 暴露一个明确 API 入口，供前端调用
7. 尽量复用现有 template_retriever / template_matcher
8. 清理 /strategy-templates 页面里基于 title + body[:100] 的临时逻辑，替换为真实链路

要求：
- 不推翻现有 matcher
- 做成桥接层
- 输出代码变更说明
```

---

## Prompt P2-3：实现 strategy_generator

```text id="20664"
请实现 RewriteStrategy 的 first usable version。

背景：
现在已经有：
- OpportunityBrief
- 选定模板
还缺从“选了什么模板”到“具体怎么写”的翻译层。

请完成：
1. 新增 strategy_generator 服务
2. 输入：
   - OpportunityBrief
   - 选定模板对象
   - 可选的 opportunity_card / evidence
3. 输出：
   - RewriteStrategy
4. 生成逻辑优先采用“模板规则 + brief 编译”的方式，必要时可接 LLM，但不要做成不可解释黑盒
5. 至少生成：
   - title_strategy
   - body_strategy
   - image_strategy
   - tone_of_voice
   - hook_strategy
   - must_keep
   - should_avoid
   - differentiation_points
   - scene_emphasis
   - rationale
6. 要让 strategy 适合前端结构化展示

要求：
- first usable version 即可
- 要清晰解释每块策略来自哪里
- 保留未来 LLM 增强空间
```

---

## Prompt P2-4：实现 note_plan_compiler

```text id="64749"
请实现一个更高层的 note_plan_compiler，把 RewriteStrategy 编译成完整版 NewNotePlan。

背景：
当前已有 MainImagePlanCompiler，但它只产出 5 张主图策划。现在要在不推翻现有代码的前提下，把它嵌入 NewNotePlan。

请完成：
1. 新增 note_plan_compiler
2. 输入：
   - RewriteStrategy
   - OpportunityBrief
   - 选定模板
   - opportunity_card（可选）
3. 输出：
   - NewNotePlan
4. 要复用现有 MainImagePlanCompiler 生成 image_plan
5. title_candidates / body_outline / tag_strategy / publish_advice 先可生成 v1 结构，不必一开始就很复杂
6. NewNotePlan 中写入完整 lineage
7. 确保 image_plan 和顶层 plan 的 IDs / lineage 一致可追踪

要求：
- 不重写 MainImagePlanCompiler
- 以组合方式实现
- 输出测试和示例
```

---

# P3：补 API

---

## Prompt P3-1：补原子 API 端点

```text id="37655"
请为后半链路新增一组原子 API 端点，供真实前端工作台调用。

请完成：
1. POST /xhs-opportunities/{id}/generate-brief
2. POST /briefs/{id}/match-templates
3. POST /briefs/{id}/generate-strategy
4. POST /strategies/{id}/generate-plan

要求：
- 尽量复用现有 API 风格和 router 组织方式
- 输入输出使用真实 schema，不使用 mock
- 对错误情况做明确处理
- 若某对象还未持久化，可先走内存/临时对象返回，但接口层要稳定
- 输出要适合前端工作台逐步调用
- 每个端点都给最小文档说明
```

---

## Prompt P3-2：补编排 API

```text id="50671"
请新增一个编排型 API 端点，把 promoted 机会卡一路编译成内容方案。

目标端点：
POST /xhs-opportunities/{id}/compile-note-plan

行为：
从一个 promoted 机会卡出发，顺序执行：
1. generate brief
2. match templates
3. choose best template（先按 top1）
4. generate rewrite strategy
5. generate new note plan

返回：
- opportunity_card
- brief
- matched_templates
- selected_template
- rewrite_strategy
- new_note_plan

要求：
- 使用现有真实服务
- 不做 mock
- 先实现 happy path
- 对每一步失败时返回清晰错误上下文
- 便于前端一键“从机会卡生成策划方案”
```

---

# P4：补生成器

---

## Prompt P4-1：实现 title_generator

```text id="94542"
请实现 title_generator 的 first usable version。

输入：
- RewriteStrategy
- OpportunityBrief
- 选定模板
- 可选的 opportunity_card evidence

输出：
- 3~5 个标题候选

要求：
1. 优先基于模板 copy_rules + strategy.title_strategy + brief.content_intent 生成
2. 如项目已有 llm_client，可在规则生成后加一个 LLM 优化步骤
3. 输出结构化 TitleCandidate 对象，至少包含：
   - text
   - style
   - rationale
4. 要避免纯促销口吻
5. 适配小红书内容语境
6. 给最小测试和示例输出
```

---

## Prompt P4-2：实现 body_generator

```text id="36496"
请实现 body_generator 的 first usable version。

输入：
- RewriteStrategy
- OpportunityBrief
- 选定模板
- 可选的 opportunity_card evidence

输出：
- 正文大纲（优先）
- 可选正文草稿

要求：
1. 先做大纲优先，不必一次到位生成长文
2. 结合：
   - strategy.body_strategy
   - brief.target_scene
   - brief.core_selling_points
   - 模板 scene_rules / copy_rules
3. 输出结构化对象，至少包含：
   - opening_hook
   - body_sections
   - cta_line
4. 语言风格适配小红书
5. 避免泛泛而谈
6. 给最小测试和示例输出
```

---

## Prompt P4-3：实现 image_brief_generator

```text id="96641"
请实现 image_brief_generator，把 MainImagePlan 的 5 个 ImageSlotPlan 进一步细化为可执行图片指令。

输入：
- MainImagePlan
- RewriteStrategy
- OpportunityBrief
- 选定模板

输出：
- 每个 slot 对应一个 ImageExecutionBrief

要求：
1. 每个 brief 至少包含：
   - slot_index
   - goal
   - scene_setup
   - composition
   - must_include
   - avoid
   - copy_overlay
   - visual_style_hint
2. 保持和现有 ImageSlotPlan 的强关联
3. 输出应适合后续接 Visual Agent / 设计师 / 生图工具
4. 给示例输出
5. 不要破坏原有 MainImagePlan 结构
```

---

# P5：前端与工作台收口

---

## Prompt P5-1：把真实 API 接进工作台

```text id="94666"
请基于现有真实 API 和刚新增的后半链路端点，把“XHS 内容策划工作台”接成真实工作台，而不是 mock 原型。

目标页面：
1. Opportunities 页面：支持 promoted 卡过滤
2. Opportunity Detail / Brief 页面：支持生成和查看 Brief
3. Template / Strategy 页面：支持模板匹配、模板切换、生成 RewriteStrategy
4. Plan 页面：展示 NewNotePlan，含标题、正文大纲、MainImagePlan、标签策略、发布建议

要求：
- 删除或替换掉原来的 mock 方案
- 调用真实 API
- 保留当前对象锚点
- 支持状态：
  - loading
  - generated
  - reviewed
  - approved
- 不要做成聊天产品
- 保持工作台式 UI
- 如已有 MainImagePlan 页面，尽量复用

请输出：
- 改哪些页面
- 改哪些 hooks / services
- 如何把页面串起来
```

---

# P6：收尾与评估

---

## Prompt P6-1：补链路验收脚本

```text id="49122"
请为“小红书机会卡 -> 内容策划方案”完整链路补一个最小验收脚本。

目标：
给定一个真实 promoted 机会卡 ID，验证系统是否能依次产出：
1. OpportunityBrief
2. matched templates
3. RewriteStrategy
4. NewNotePlan
5. （可选）title candidates / body outline / image execution briefs

请完成：
- 一个 CLI 或测试脚本
- 打印每一步关键输出摘要
- 若失败，打印明确断点和错误信息
- 输出最终 lineage 摘要

要求：
- 不使用 mock
- 尽量复用真实 service / API
- 便于后续作为回归测试
```


# P7: 验收
## 验收 1：对象链路

给一张 promoted 机会卡，系统能否稳定产出：

-Brief
-模板候选
-RewriteStrategy
-NewNotePlan
## 验收 2：回溯链路

从任意一份 plan 能否回溯到：

- opportunity_id
- source_note_ids
- template_id
- strategy_id
## 验收 3：人工可控

用户是否可以：

-切换模板
-修改策略
-重新生成标题
-重新生成正文
-重新生成图片执行指令
## 验收 4：真实数据可跑通

从真实小红书数据出发，抽一批 promoted 卡，是否能走完整链路，不依赖 mock。