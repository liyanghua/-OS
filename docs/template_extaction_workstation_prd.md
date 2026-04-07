# D. 工作台可用性验收 Prompt

---

## Prompt D1：验收工作台是否满足业务使用

```text id="f9fe7b"
请站在业务人员视角，验收“内容策划工作台 v1”是否具备最小可用性。

目标用户：
- 业务运营
- 内容策划
- 商品运营
- 客户侧使用者（较轻度）

请按以下流程检查可用性：
1. 从机会池挑选 promoted 机会
2. 查看并确认 OpportunityBrief
3. 查看模板候选并选模板
4. 查看 RewriteStrategy
5. 查看 NewNotePlan
6. 查看标题/正文/图片执行指令
7. 保存或导出

请输出：
- 哪些操作已经顺畅
- 哪些地方仍然需要开发或优化
- 哪些字段业务人员看不懂
- 哪些步骤应该允许人工编辑
- 哪些步骤应该支持局部重生成
- 是否已经达到“可让业务人员试用”的程度
```

---

# 二、工作台 PRD v1

下面给你一版偏“最小可用工作台”的 PRD。

---

# 1. 产品目标

## 1.1 目标

让业务人员基于 **promoted 机会卡**，完成从机会确认到内容策划生成的闭环操作，而不需要理解底层复杂链路。

## 1.2 目标链路

用户在工作台里完成：

**挑机会 → 看 brief → 选模板 → 看策略 → 看新笔记策划方案 → 导出标题/正文/图片执行指令**

## 1.3 当前阶段定位

v1 不是“自动发笔记系统”，而是：

**机会驱动的内容策划工作台**

重点是“生成可审核、可编辑、可导出的内容方案”。

---

# 2. 页面结构设计

建议先做 4 个页面。

---

## 页面 1：机会池页

### 页面目标

给业务人员快速浏览和筛选 promoted 机会卡。

### 页面结构

#### 顶部筛选栏

字段：

* 状态：all / reviewed / promoted
* 机会类型：visual / scene / demand
* 分数区间
* 标签筛选：风格 / 场景 / 类目
* 搜索：标题 / summary / note_id

#### 左侧：机会列表

每行显示：

* 封面缩略图
* 机会标题
* 机会类型
* composite_review_score
* review_count
* opportunity_status
* tags
* source note 数量

#### 右侧：机会预览卡

显示：

* summary
* evidence_refs 摘要
* scene/style/need/audience refs
* suggested_next_step
* 原笔记预览入口

#### 底部主按钮

* 生成 Brief
* 进入内容策划

### 页面动作

* 点击机会卡进入详情
* 支持批量筛选
* 支持只看 promoted

### 对应 API

* `GET /xhs-opportunities`
* `GET /xhs-opportunities/{id}`

---

## 页面 2：Brief 确认页

### 页面目标

把 promoted 机会卡转成结构化 `OpportunityBrief`，并允许业务人员轻编辑。

### 页面结构

#### 左栏：来源上下文

显示：

* 原始笔记封面与标题
* 原文摘要
* 互动摘要
* 机会卡摘要
* review 结果

#### 中栏：自动生成的 OpportunityBrief

字段直接展示：

* 目标人群
* 目标场景
* 核心动机
* 内容目标
* primary value
* secondary values
* visual style direction
* template hints
* avoid directions
* proof from source

#### 右栏：人工修订区

支持编辑：

* target_user
* target_scene
* content_goal
* primary_value
* visual_style_direction
* avoid_directions
* template_hints

#### 底部按钮

* 保存 Brief
* 重新生成 Brief
* 下一步：模板匹配

### 页面动作

* 一键生成 brief
* 人工修订 brief
* 保存后进入模板匹配

### 对应 API

* `POST /xhs-opportunities/{id}/generate-brief`
* `PUT /content-planning/briefs/{brief_id}` 或等价保存接口

---

## 页面 3：模板与策略页

### 页面目标

选择模板，并查看/修订 `RewriteStrategy`。

### 页面结构

#### 上半区：模板候选区

展示 top3 模板卡片：

* template_name
* template_goal
* fit_scenarios
* fit_styles
* 匹配分数
* rationale
* risk_notes

支持：

* 选择 top1
* 改选 top2 / top3
* 手动指定模板重新生成策略

#### 下半区：RewriteStrategy 区

字段展示：

* positioning_statement
* new_hook
* new_angle
* tone_of_voice
* keep_elements
* replace_elements
* enhance_elements
* avoid_elements
* title_strategy
* body_strategy
* image_strategy
* differentiation_axis
* risk_notes

#### 右侧操作栏

* 重新生成 Strategy
* 只改 Hook
* 只改 Tone
* 只改 Image Strategy
* 进入策划方案

### 页面动作

* 模板切换
* Strategy 重生成
* Strategy 局部编辑

### 对应 API

* `POST /xhs-opportunities/{id}/generate-note-plan`（可返回 brief + template_match + strategy）
* 或单独拆：

  * `POST /content-planning/briefs/{brief_id}/match-template`
  * `POST /content-planning/briefs/{brief_id}/generate-strategy`

---

## 页面 4：内容策划页

### 页面目标

展示完整版 `NewNotePlan`，并派生标题、正文、图片执行指令。

### 页面结构

#### 左栏：方案上下文

* 机会摘要
* Brief 摘要
* 选定模板
* RewriteStrategy 摘要

#### 中栏：NewNotePlan 主体

分成 3 个区块：

### A. 标题策划

* title_axes
* candidate_titles
* do_not_use_phrases

### B. 正文策划

* opening_hook
* body_outline
* cta_direction
* tone_notes

### C. 图片策划

* 5 个图位卡片
  每个图位显示：
* role
* intent
* visual_brief
* copy_hints
* must_include_elements
* avoid_elements

#### 右栏：生成结果区

分 tab：

* 标题候选
* 正文草稿
* 图片执行指令

#### 底部操作

* 重新生成标题
* 重新生成正文
* 重新生成图片执行指令
* 导出 JSON
* 导出 markdown
* 保存方案
* 发送给视觉 Agent / 设计执行

### 对应 API

* `POST /xhs-opportunities/{id}/generate-note-plan?with_generation=true`
* 或拆分：

  * `POST /content-planning/plans/{plan_id}/generate-titles`
  * `POST /content-planning/plans/{plan_id}/generate-body`
  * `POST /content-planning/plans/{plan_id}/generate-image-briefs`

---

# 3. 操作流设计

## 3.1 主操作流

### Flow 1：从机会池进入

1. 业务人员在机会池页筛选 `promoted`
2. 点开某张机会卡
3. 点击“生成 Brief”

### Flow 2：确认 Brief

4. 系统自动调用 `generate-brief`
5. 用户查看并轻编辑 brief
6. 点击“下一步：模板匹配”

### Flow 3：模板与策略

7. 系统显示 top3 模板候选
8. 用户选择模板
9. 系统生成 RewriteStrategy
10. 用户可局部改 strategy
11. 点击“生成策划方案”

### Flow 4：策划与导出

12. 系统生成 NewNotePlan
13. 用户查看标题/正文/图片三维策划
14. 用户触发生成标题、正文、图片执行指令
15. 用户保存或导出方案

---

## 3.2 局部重生成流

### Flow A：只重生成 Brief

* 适用于机会判断对，但人群/场景不准

### Flow B：只换模板

* 适用于 top1 不满意，切到 top2/top3

### Flow C：只重生成 Strategy

* 适用于 hook 不满意、语气不对

### Flow D：只重生成标题/正文/图片执行指令

* 适用于 plan 对，但生成内容不满意

### 原则

不要每次整链重跑。
局部重生成必须是工作台的重要能力。

---

# 4. API 对应关系

下面给你一版清晰映射。

## 4.1 页面 1：机会池页

### API

* `GET /xhs-opportunities`
* `GET /xhs-opportunities/{id}`

### 返回

* 机会列表
* 机会详情
* promoted 状态
* review 信息

---

## 4.2 页面 2：Brief 确认页

### API

* `POST /xhs-opportunities/{id}/generate-brief`
* `PUT /content-planning/briefs/{brief_id}`

### 返回

* `OpportunityBrief`

---

## 4.3 页面 3：模板与策略页

### API 方案一：合并型

* `POST /xhs-opportunities/{id}/generate-note-plan`

  * 参数：`mode=plan_only`

### API 方案二：拆分型

* `POST /content-planning/briefs/{brief_id}/match-template`
* `POST /content-planning/briefs/{brief_id}/generate-strategy`

### 返回

* `TemplateMatchResult`
* `RewriteStrategy`

---

## 4.4 页面 4：内容策划页

### API

* `POST /xhs-opportunities/{id}/generate-note-plan`

  * 参数：`with_generation=true`

或拆分：

* `POST /content-planning/plans/{plan_id}/generate-titles`
* `POST /content-planning/plans/{plan_id}/generate-body`
* `POST /content-planning/plans/{plan_id}/generate-image-briefs`

### 返回

* `NewNotePlan`
* `TitleGenerationResult`
* `BodyGenerationResult`
* `ImageBriefGenerationResult`

---

# 5. v1 字段编辑原则

v1 不要做全字段自由编辑。
只开放业务最需要改的字段：

## 可编辑

* Brief：target_user / target_scene / content_goal / primary_value / visual_style_direction
* Strategy：new_hook / new_angle / tone_of_voice / avoid_elements
* Plan：candidate_titles 局部重生成、body_outline 局部重生成、单图位图片执行指令重生成

## 不建议 v1 开放

* 全量 schema 原地手改
* 任意 JSON 编辑
* 多人协作冲突管理
* 复杂版本树

---

# 6. v1 验收标准

## 功能验收

* 4 页全部可打开
* 每页有真实 API 支撑
* 一条 promoted 机会能走完整链路

## 业务验收

* 业务人员能在 5 分钟内完成一次完整内容策划
* 不需要理解底层模型逻辑
* 至少能产出可审核的标题/正文/图片执行指令

## 质量验收

* 生成内容与 Brief / Strategy / Plan 一致
* 方案可回溯
* 局部重生成可用

---