
---

# 一、验收 Prompt 清单

建议你把验收分成 4 层：

* A. 结构与链路验收
* B. 单模块质量验收
* C. 端到端样本验收

---

## Prompt A1：让 AI coding 工具生成“当前实现 vs 目标链路”的验收报告

```text id="v02srv"
请基于当前代码库，生成一份“内容策划链路验收报告”。

目标链路是：
promoted 机会卡 -> OpportunityBrief -> 模板匹配 -> RewriteStrategy -> NewNotePlan -> 标题/正文/图片策划

请检查并输出：

1. 当前链路中每个阶段是否存在
- OpportunityBrief schema / service / API
- TemplateMatchResult
- RewriteStrategy schema / service
- NewNotePlan schema / compiler
- title_generator / body_generator / image_brief_generator
- orchestration flow
- API routes

2. 每个阶段的输入 / 输出对象是什么
3. 每个阶段是否有回溯字段：
- opportunity_id
- brief_id
- strategy_id
- template_id
- source_note_ids

4. 每个阶段是否真正被下游调用，而不是“代码存在但没有调用方”
5. 输出一个验收矩阵表：
- 模块名
- 状态（implemented / partial / missing / disconnected）
- 文件路径
- 关键问题
- 是否阻塞上线

要求：
- 直接基于当前代码分析
- 不要只看文件存在与否，要看是否真正串联
- 输出 markdown 格式
```

---

## Prompt A2：验收“对象链是否闭合”

```text id="l2edvh"
请基于当前代码，验收“对象链闭合情况”。

我要验证以下对象是否真正形成链路闭环：
- XHSOpportunityCard
- OpportunityBrief
- TemplateMatchResult
- RewriteStrategy
- NewNotePlan
- TitleGenerationResult
- BodyGenerationResult
- ImageBriefGenerationResult

请逐一检查：
1. 每个对象的 schema 是否存在
2. 是否有明确的构造/生成逻辑
3. 是否被下一阶段消费
4. 是否带有必要回溯字段
5. 是否可通过 API 返回

请输出：
- 对象链闭合图
- 每个对象的生产方 / 消费方
- 断点清单
- 修复建议

重点：
不要只说“对象存在”，要说明“谁生成、谁消费、在哪个函数/服务里串起来”。
```

---

## Prompt A3：验收 API 是否真的打通

```text id="e0f3t1"
请对内容策划相关 API 做链路验收，重点检查：

1. POST /xhs-opportunities/{id}/generate-brief
2. POST /xhs-opportunities/{id}/generate-note-plan

请输出：
- API 路由文件位置
- 请求参数定义
- 返回对象定义
- 内部调用链
- 错误处理逻辑
- 是否真的串联到 promoted 机会卡
- 是否支持 plan_only / with_generation 模式
- 是否返回完整回溯字段

请附加：
- 一组 curl 或 pytest 风格的最小调用示例
- 一份“接口是否达到前端接入条件”的判断
```

---

# B. 单模块质量验收 Prompt

---

## Prompt B1：验收 OpportunityBrief 质量

```text id="vvv1lu"
请对 OpportunityBrief 模块做专项验收。

验收目标：
OpportunityBrief 不是“标题 + 正文截断”的伪 brief，而是真正结构化的机会编译对象。

请检查：
1. OpportunityBrief schema 是否字段完整
2. brief_compiler 是否主要基于 promoted 机会卡 + parsed note 进行编译
3. target_user / target_scene / core_motive / content_goal / primary_value / template_hints / avoid_directions 是否都能被稳定产出
4. brief 是否明显比原机会卡更结构化、更可执行
5. 是否存在明显的“字段空洞”或大量 None
6. 是否可以直接供模板匹配器消费

请输出：
- 代码位置
- 质量问题清单
- 3 个 mock 输入输出案例
- 是否达到“可供业务人员确认”的水平
```

---

## Prompt B2：验收模板匹配是否已经从“原笔记关键词匹配”升级为“Brief 驱动”

```text id="65um6f"
请对 TemplateMatcher 做专项验收。

验收目标：
模板匹配必须优先使用 OpportunityBrief，而不是继续主要依赖原笔记标题 + 正文关键词。

请检查：
1. match_templates 是否支持 brief 输入
2. brief 是否为主输入源
3. content_goal / target_scene / visual_style_direction / primary_value 是否参与打分
4. 原笔记文本是否退为辅助信号
5. top3 模板候选是否稳定返回
6. rationale 是否清晰
7. recommended_phrases 的旧 bug 是否已修复（不要再按字符遍历）

请输出：
- 打分维度
- 权重结构
- 一个真实样例的匹配过程说明
- 仍然存在的 heuristic 风险
```

---

## Prompt B3：验收 RewriteStrategy 是否真的起作用

```text id="x4eaf4"
请对 RewriteStrategy 模块做专项验收。

验收目标：
RewriteStrategy 必须成为“模板选择 -> 内容改写方向”的翻译层，而不是空洞描述。

请检查：
1. RewriteStrategy schema 是否完整
2. strategy_generator 是否使用了 brief + template_match_result
3. 是否能稳定产出：
   - positioning_statement
   - new_hook
   - new_angle
   - keep_elements
   - replace_elements
   - enhance_elements
   - avoid_elements
   - title_strategy
   - body_strategy
   - image_strategy
4. 是否体现差异化改写，而不是模板套壳
5. 是否能供 NewNotePlan 编译器直接使用

请输出：
- 一个桌布案例的 strategy 样本
- 优点
- 问题
- 是否达到“可以让业务人员理解为什么这样写”的水平
```

---

## Prompt B4：验收 NewNotePlan 是否已经是“完整版”

```text id="v5fq93"
请对 NewNotePlan 做专项验收。

验收目标：
NewNotePlan 不只是旧的 MainImagePlan，而是包含标题、正文、图片三维策划的完整对象。

请检查：
1. NewNotePlan schema 是否存在并可实例化
2. 是否包含：
   - title_plan
   - body_plan
   - image_plan
   - publish_notes
3. image_plan 是否复用了现有 MainImagePlan
4. NewNotePlan 是否带有：
   - opportunity_id
   - brief_id
   - strategy_id
   - template_id
5. 是否能作为后续标题/正文/图片执行指令生成的唯一输入
6. 是否适合前端工作台展示

请输出：
- NewNotePlan 示例
- 结构完整性判断
- 对前端展示友好度判断
```

---

## Prompt B5：验收内容生成器是否 plan-aware

```text id="73av9q"
请验收 title_generator / body_generator / image_brief_generator 是否已经是 plan-aware 生成器。

要求：
1. 必须从 NewNotePlan 派生
2. 不能绕开 plan 自由发挥
3. 输出必须与 title_plan / body_plan / image_plan 对齐
4. 在无 LLM 条件下也能返回基础结果
5. 在有 LLM 条件下可以增强，但不能偏离 plan

请逐一检查：
- title_generator
- body_generator
- image_brief_generator

请输出：
- 每个生成器的输入输出
- 是否真正 plan-aware
- 是否存在“绕开 plan 直接生成”的风险
- 一个样例调用结果摘要
```

---

# C. 端到端样本验收 Prompt

---

## Prompt C1：跑 12 条样本的端到端验收

```text id="flr14n"
请基于当前代码，设计并执行一套“12 条 promoted 机会卡”的端到端验收。

目标：
验证以下链路是否稳定跑通：
promoted 机会卡 -> OpportunityBrief -> 模板匹配 -> RewriteStrategy -> NewNotePlan -> 标题/正文/图片执行指令

要求：
1. 样本分三档：
- 4 条容易样本
- 4 条中等样本
- 4 条困难样本

2. 每条样本输出验收表：
- opportunity_id
- brief 是否完整
- template match 是否合理
- strategy 是否明确
- note plan 是否完整
- 标题是否可用
- 正文是否可用
- 图片指令是否可用
- 回溯字段是否齐全
- 是否通过

3. 最终输出：
- 链路通过率
- 生成通过率
- 最常见失败原因
- Top 5 修复建议

请输出 markdown 报告。
```

---

## Prompt C2：做 3 条 golden cases 详细剖析

```text id="ea8z1t"
请从样本中挑 3 条最具代表性的桌布机会卡，输出详细的 golden cases。

每条 case 请完整展示：
1. promoted 机会卡摘要
2. OpportunityBrief
3. top3 模板匹配结果
4. RewriteStrategy
5. NewNotePlan
6. 标题候选
7. 正文草稿
8. 图片执行指令摘要
9. 你对结果质量的点评

目标：
让我和业务人员能直观看到“这条链路最后产出的内容到底是什么样”。
```

---

## 实现侧补充（与代码同步）

- **API 路径**：主入口为 `POST /content-planning/xhs-opportunities/{id}/generate-brief` 与 `generate-note-plan`；并注册无前缀别名 `POST /xhs-opportunities/{id}/...` 以兼容上文 Prompt A3。详见 [CONTENT_PLANNING_API.md](CONTENT_PLANNING_API.md)。
- **promoted**：仅 `opportunity_status=promoted` 的机会卡可生成 Brief/策划，否则 HTTP **403**。
- **C1/C2 脚本**：`apps/content_planning/scripts/run_acceptance_c1.py`、`export_golden_cases.py`。

---


