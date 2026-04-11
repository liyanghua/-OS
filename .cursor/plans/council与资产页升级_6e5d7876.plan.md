---
name: Council与资产页升级
overview: 修复 Council 讨论结果无法正确 apply、资产详情页分析失效、讨论历史不可见等 5 个核心问题，并给出资产详情页整体重构方案。
todos:
  - id: a1-fix-apply-path
    content: "A1: 修复 planning_workspace.html 的 apply/reject 路径为 /proposals/{id}/apply"
    status: completed
  - id: a2-fix-proposed-updates-render
    content: "A2: 修复 _renderFinalProposal 读取 proposed_updates + diff 展示"
    status: completed
  - id: a3-strategy-block-diff-apply
    content: "A3: strategy 块级 diff 映射到 apply_stage_updates"
    status: completed
  - id: b1-fix-asset-producer
    content: "B1+B2: 诊断并修复 asset_producer agent 注册与 fast mode"
    status: completed
  - id: c1-asset-council-roles
    content: "C1: 定义资产阶段 Council 角色列表"
    status: completed
  - id: d1-discussion-list-api
    content: "D1+D2: 新增按 opportunity 列出历史讨论 API + store 方法"
    status: completed
  - id: d3-discussion-history-ui
    content: "D3: 前端展示历史讨论列表（planning_workspace + content_assets）"
    status: completed
  - id: e1-asset-page-refactor
    content: "E: 资产详情页右栏重构（Tab化 + 合并 + 折叠）"
    status: completed
isProject: false
---

# Council 讨论 Apply + 资产详情页升级计划

## 问题诊断总结

### 问题 1: Council 讨论结果未映射回 Brief/Strategy

**根因**: 两处断裂

- (a) **planning_workspace.html 的 apply/reject 前端调用路径错误**：模板调用 `/discussions/{id}/apply`，但后端路由是 `/proposals/{proposal_id}/apply`。`content_assets.html` 已使用正确路径，但 planning_workspace 未修正。
- (b) **proposed_updates 字段名不一致**: 后端 `StageProposal` 返回 `proposed_updates`，但前端 `_renderFinalProposal` 读取的是 `field_changes || changes`，导致变更列表为空，用户看不到可采纳的结构化字段。
- (c) **Strategy 块级 diff 未映射**: `_synthesize_consensus` 输出 `strategy_block_diffs`，但 `apply_stage_updates` 的 strategy 分支只处理 `proposed_updates` 中的扁平字段，块级 diff 丢失。

### 问题 2: 资产制作人分析不工作

**根因**: 浏览器访问 `/content-planning/assets/{id}` 渲染的是 `content_assets.html`（非 `asset_workspace.html`）。`content_assets.html` 中 `runAgent('asset_producer')` 调用 `POST /run-agent/{id}`，后端 LeadAgent 的 `_route` 方法中 `asset_producer` 角色可能未注册在 agent 实例化映射中，或 `mode: 'fast'` 跳过了深度分析逻辑。需要检查 `_instantiate('asset_producer')` 是否返回 None。

### 问题 3: 资产页无 Council 组件复用

资产页 `content_assets.html` 已有独立的 Council UI，但角色是硬编码的通用 Council 参与者，未定义资产阶段专属角色。

### 问题 4: 委员会历史讨论不可见

后端缺少按 opportunity 列出历史讨论的 API；前端没有历史讨论列表区块。

### 问题 5: 资产详情页臃肿需重构

当前 `content_assets.html` 右栏堆了 10+ 个卡片区块（资产制作人、Council、导出、发布结果、结果摘要、状态、技能、时间线、对话、协同侧栏），信息密度过高。

---

## 实施计划

### Phase A: 修复 Council Apply 断裂（问题 1）

**A1. 修复 planning_workspace.html 的 apply/reject 路径**

文件: [apps/intel_hub/api/templates/planning_workspace.html](apps/intel_hub/api/templates/planning_workspace.html)

- `applyProposal(discussionId)` 改为接收 `proposalId`，调用 `/proposals/{proposalId}/apply`
- `rejectProposal(discussionId)` 同理改为 `/proposals/{proposalId}/reject`
- `_renderFinalProposal(data)` 中把按钮的 `onclick` 传入 `data.proposal_id` 而非 `discussionId`

**A2. 修复 proposed_updates 前端展示**

文件: [apps/intel_hub/api/templates/planning_workspace.html](apps/intel_hub/api/templates/planning_workspace.html)

- `_renderFinalProposal` 中的变更列表改为读取 `proposal.proposed_updates`（而非 `field_changes || changes`）
- 渲染每个字段的 before/after 对比（利用 `proposal.diff` 里已有的 `field` / `before` / `after`）
- 给每个字段添加勾选框，apply 时传 `selected_fields`

**A3. Strategy 块级 diff 映射**

文件: [apps/content_planning/services/opportunity_to_plan_flow.py](apps/content_planning/services/opportunity_to_plan_flow.py)

- 在 `apply_stage_updates` 的 strategy 分支中，除了处理 `proposed_updates` 的扁平字段外，增加对 `strategy_block_diffs` 的处理逻辑
- 将 `strategy_block_diffs` 中 action=rewrite 的块映射到对应 strategy 字段（如 `title_strategy` / `body_strategy` / `image_strategy`）

### Phase B: 修复资产制作人分析（问题 2）

**B1. 诊断 asset_producer agent 注册**

文件: [apps/content_planning/agents/lead_agent.py](apps/content_planning/agents/lead_agent.py)

- 检查 `_instantiate('asset_producer')` 的映射表，确认该角色是否有对应的 agent 类
- 若缺失，在 `_route` 的角色映射或 `AGENT_CLASSES` 中注册 `asset_producer` 指向合适的 agent（可指向一个通用分析 agent 或新建轻量 AssetProducerAgent）

**B2. 确保 fast mode 不跳过分析**

文件: [apps/content_planning/agents/lead_agent.py](apps/content_planning/agents/lead_agent.py)

- 检查 `_run_pipeline` 的 fast mode 路径，确保 `asset_producer` 角色的分析逻辑不被跳过

### Phase C: 资产页 Council 角色定义（问题 3）

**C1. 定义资产阶段 Council 角色**

文件: [apps/content_planning/agents/discussion.py](apps/content_planning/agents/discussion.py)

- 在 `STAGE_DISCUSSION_ROLES` 中为 `asset` 阶段定义专属角色列表，建议：
  - `creative_director` — 审视视觉一致性与封面张力
  - `brand_guardian` — 品牌合规审查
  - `growth_strategist` — 转化效果预测
  - `risk_assessor` — 素材风险与平台规则检查

**C2. 资产页 Council UI 沿用 content_assets.html 已有组件**

- `content_assets.html` 已有 Council 区块，确认 stage 参数传 `asset` 即可触发正确角色

### Phase D: 委员会历史可见（问题 4）

**D1. 新增按 opportunity 列出讨论的 API**

文件: [apps/content_planning/api/routes.py](apps/content_planning/api/routes.py)

- 新增 `GET /discussions/by-opportunity/{opportunity_id}` 端点
- 从 store 查询该 opportunity 的所有讨论记录，按时间倒序返回

**D2. 新增 store 方法**

文件: [apps/content_planning/storage/plan_store.py](apps/content_planning/storage/plan_store.py)

- 在 `ContentPlanStore` 中添加 `list_discussions_by_opportunity(opportunity_id, limit=20)` 方法

**D3. 前端展示历史讨论列表**

文件: [apps/intel_hub/api/templates/planning_workspace.html](apps/intel_hub/api/templates/planning_workspace.html)

- 在 Council 抽屉顶部增加「历史讨论」折叠区
- 页面加载时 fetch 历史列表，显示每条讨论的时间、阶段、摘要、状态
- 点击可展开查看详情（调用 `GET /discussions/{id}`）

文件: [apps/intel_hub/api/templates/content_assets.html](apps/intel_hub/api/templates/content_assets.html)

- 同样在 Council 区块上方增加历史讨论折叠区

### Phase E: 资产详情页重构（问题 5）

**当前 content_assets.html 右栏结构问题**:

右栏 10+ 卡片垂直堆叠，用户需大量滚动。功能分散，无主次之分。

**重构建议 -- 分区合并 + Tab 化**:

```
右栏重构后结构：
├── 主操作区（固定）
│   ├── 资产制作人分析按钮
│   ├── 导出按钮（JSON/MD）
│   └── 标记就绪按钮
├── AI 面板 Tab
│   ├── Tab 1: AI 评审（Judge 分数 + 风险 + 建议）
│   ├── Tab 2: Council（提问 + 历史 + 提案）
│   └── Tab 3: 协同（时间线 + 对话合并）
├── 发布与复盘（折叠）
│   ├── 发布结果录入
│   ├── 结果摘要
│   └── 效果反馈
└── 辅助信息（折叠）
    ├── 可用技能
    └── 对象状态
```

具体改动:

- **合并对话与时间线**为一个「协同」Tab，共享同一滚动区
- **Council + AI 评审** 放入同一 Tab 组，默认展示 AI 评审
- **发布结果录入 + 结果摘要 + 效果反馈** 合并为「发布与复盘」折叠区，非首屏优先
- **可用技能 + 对象状态** 合并为「辅助信息」折叠区
- **主操作按钮**固定在右栏顶部，不跟随滚动

文件: [apps/intel_hub/api/templates/content_assets.html](apps/intel_hub/api/templates/content_assets.html)

---

## 优先级与执行顺序

1. **Phase A** (Council Apply 修复) -- 最高优先级，直接影响核心流程
2. **Phase B** (资产制作人分析修复) -- 高优先级，定位快修复快
3. **Phase D** (历史讨论可见) -- 中高优先级，补全信息闭环
4. **Phase C** (资产 Council 角色) -- 中优先级，角色配置
5. **Phase E** (资产页重构) -- 中优先级，改善体验但不阻塞功能
