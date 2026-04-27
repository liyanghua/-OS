# Implement Instructions

## 1. Source of Truth

The following files are source of truth:

1. `README_PRODUCT.md`
2. `ARCHITECTURE.md`
3. `IA_AND_PAGES.md`
4. `DATA_MODEL.md`
5. `PLAN.md`
6. `DECISIONS.md`

If implementation details conflict with these files, update docs first or note the issue before proceeding.

---

## 2. Core Rules

1. Keep scope limited to the current milestone.
2. Prefer reusable typed components over page-specific ad hoc code.
3. Preserve lifecycle-driven and project-object-centered structure.
4. Do not turn the product into:
   - a generic dashboard
   - a generic task manager
   - a generic chat shell
5. Surface management decisions, approvals, exceptions, and live state clearly.
6. Distinguish explicitly between:
   - human decisions
   - AI recommendations
   - agent progress
   - automation results
7. Use mock data and mock state where real integrations do not exist.
8. Update progress notes after each milestone.
9. Use the prescribed src/ layout as the implementation skeleton.
Create folders incrementally by milestone instead of generating the entire tree at once.

---

## 3. Frontend Design Rules

1. Cards should feel management-oriented, not just data-oriented.
2. Default layout should emphasize:
   - pulse
   - risks
   - opportunities
   - pending approvals
   - blockers
   - project health
3. AI modules should be embedded in-page, not a floating generic assistant.
4. Action lifecycle must be visible.
5. Review pages must support asset capture.
6. Lifecycle is the main structural axis.
7. Project Object is the main collaboration object.
8. **视觉与交互**：以仓库根目录 `Guidelines.md` 与 `src/app/globals.css`（`:root` 设计令牌）为准；全页壳层见 `AppShell` / `SideNav` / `RoleSwitcher`；标准内容块优先使用 `ManagementPanel`（圆角、分区顶栏、轻阴影）。

---

## 4. Code Rules

1. Use strict typing for core schemas.
2. Centralize enums and shared types in `src/domain/types/*`.
3. Shared UI elements should live in reusable components.
4. Avoid duplicate card implementations unless justified.
5. Keep route naming and file structure predictable.
6. Keep page composition modular.
7. Prefer ViewModel mappers for page-specific formatting instead of distorting canonical domain types.
8. Do not couple page layout directly to raw mock data shape when a ViewModel is more appropriate.

---

## 5. Product-to-Code Mapping

This section explains how product goals should map to code modules.

### 5.1 CEO Command Center
- Product goal:
  - show pulse
  - show battles
  - show resources
  - show pending approvals
  - show org/AI efficiency
- Core models:
  - `PulseBundle`
  - `ProjectObject`
  - `ActionItem`
  - `ExceptionItem`
- Code locations:
  - `src/app/command-center/page.tsx`
  - `src/components/dashboards/*`
  - `src/components/cards/*`
  - `src/domain/mappers/to-ceo-dashboard-vm.ts`

### 5.2 Product R&D Director Desk
- Product goal:
  - review opportunities
  - review incubation
  - review definition and sampling risk
  - review upgrade opportunities
- Core models:
  - `PulseBundle`
  - `ProjectObject`
  - `DecisionObject`
  - `ProductDefinition`
  - `SamplingReview`
- Code locations:
  - `src/app/command-center/page.tsx` or future role-specific route
  - `src/components/dashboards/*`
  - `src/components/project/*`
  - `src/domain/mappers/to-product-rd-vm.ts`

### 5.3 Growth Director Desk
- Product goal:
  - review launch and growth pulse
  - compare plans
  - approve key actions
  - track blockers and live health
- Core models:
  - `PulseBundle`
  - `ProjectObject`
  - `ActionItem`
  - `ExceptionItem`
  - `ProjectRealtimeSnapshot`
- Code locations:
  - `src/app/command-center/page.tsx` or future role-specific route
  - `src/components/dashboards/*`
  - `src/components/cards/*`
  - `src/domain/mappers/to-growth-vm.ts`

### 5.4 Visual Director Desk
- Product goal:
  - review visual priorities
  - compare versions
  - identify upgrade opportunities
  - manage reusable visual assets
- Core models:
  - `PulseBundle`
  - `ProjectObject`
  - `ExpressionPlan`
  - `CreativeVersion`
  - `PublishedAsset`
- Code locations:
  - `src/app/command-center/page.tsx` or future role-specific route
  - `src/components/dashboards/*`
  - `src/components/project/*`
  - `src/domain/mappers/to-visual-vm.ts`

### 5.5 Lifecycle Overview
- Product goal:
  - show lifecycle flow
  - show stage distribution
  - show blockers, approvals, health
- Core models:
  - `ProjectObject`
  - `LifecycleOverviewVM`
  - `ProjectRealtimeSnapshot`
  - `ExceptionItem`
  - `ActionItem`
- Code locations:
  - `src/app/lifecycle/page.tsx`
  - `src/components/lifecycle/*`
  - `src/domain/mappers/*`

### 5.6 Opportunity Pool
- Product goal:
  - show opportunity candidates
  - score and prioritize them
  - convert them into projects
- Core models:
  - `ProjectObject`
  - `OpportunitySignal`
  - `OpportunityAssessment`
  - `DecisionObject`
- Code locations:
  - `src/app/lifecycle/opportunity-pool/page.tsx`
  - `src/components/cards/*`
  - `src/components/project/*`

### 5.7 New Product Incubation
- Product goal:
  - turn opportunities into launchable product projects
- Core models:
  - `ProjectObject`
  - `ProductDefinition`
  - `SamplingReview`
  - `DecisionObject`
  - `ActionItem`
- Code locations:
  - `src/app/lifecycle/new-product-incubation/page.tsx`
  - `src/components/project/*`
  - `src/components/cards/*`

### 5.8 Launch Validation
- Product goal:
  - validate launch outcome
  - decide scale / adjust / pause
- Core models:
  - `ProjectObject`
  - `ExpressionPlan`
  - `CreativeVersion`
  - `DecisionObject`
  - `ProjectRealtimeSnapshot`
- Code locations:
  - `src/app/lifecycle/launch-validation/page.tsx`
  - `src/components/project/*`
  - `src/components/cards/*`

### 5.9 Growth Optimization
- Product goal:
  - diagnose and optimize products
  - support battle-style growth execution
- Core models:
  - `ProjectObject`
  - `DecisionObject`
  - `ActionItem`
  - `AgentState`
  - `ProjectRealtimeSnapshot`
- Code locations:
  - `src/app/lifecycle/growth-optimization/page.tsx`
  - `src/components/project/*`
  - `src/components/cards/*`

### 5.10 Legacy Upgrade
- Product goal:
  - identify and run legacy upgrade projects
- Core models:
  - `ProjectObject`
  - `DecisionObject`
  - `ProductDefinition`
  - `ExpressionPlan`
  - `ReviewSummary`
- Code locations:
  - `src/app/lifecycle/legacy-upgrade/page.tsx`
  - `src/components/project/*`
  - `src/components/cards/*`

### 5.11 Project Object Page
- Product goal:
  - unify summary, decision, definition, expression, actions, live state, review, assets
- Core models:
  - `ProjectObject`
  - `DecisionObject`
  - `ProductDefinition`
  - `ExpressionPlan`
  - `ActionItem`
  - `AgentState`
  - `ReviewSummary`
  - `AssetCandidate`
  - `ProjectRealtimeSnapshot`
- Code locations:
  - `src/app/projects/[projectId]/page.tsx`
  - `src/components/project/*`
  - `src/domain/mappers/to-project-page-vm.ts`

### 5.12 Action Hub
- Product goal:
  - manage decision-to-action lifecycle
- Core models:
  - `ActionItem`
  - `ApprovalRecord`
  - `ExecutionLog`
- Code locations:
  - `src/app/action-hub/page.tsx`
  - `src/components/governance/*`
  - `src/components/cards/*`

### 5.13 Governance Console
- Product goal:
  - handle exceptions, policy boundaries, and high-risk approvals
- Core models:
  - `ExceptionItem`
  - `PolicyBoundary`
  - `DecisionObject`
  - `ActionItem`
  - `ExecutionLog`
- Code locations:
  - `src/app/governance/page.tsx`
  - `src/components/governance/*`

### 5.14 Review to Asset Loop
- Product goal:
  - turn review into assets
- Core models:
  - `ReviewSummary`
  - `AttributionFactor`
  - `AssetCandidate`
  - `PublishedAsset`
- Code locations:
  - `src/app/lifecycle/review-capture/page.tsx`
  - `src/components/review/*`

### 5.15 Asset Hub
- Product goal:
  - manage reusable operating assets
- Core models:
  - `PublishedAsset`
  - `AssetCandidate`
- Code locations:
  - `src/app/assets/page.tsx`
  - `src/components/review/*`
  - `src/components/cards/*`

---

## 6. Implementation Sequence Rules

When implementing milestones:

1. Start from structure and routing.
2. Then establish domain types.
3. Then implement page skeletons.
4. Then add reusable cards and panels.
5. Then connect mock store and ViewModels.
6. Then improve state visibility and interaction details.

Do not start from visual polish before the object model and route structure are stable.

---

## 7. Validation Checklist Per Milestone

After each milestone:

- app builds successfully
- main routes render
- imports are clean
- no obvious dead links
- shared components reused where expected
- core typed schemas still valid
- relevant page-to-model mapping is preserved
- docs updated if assumptions changed

---

## 8. Progress Notes

### Milestone 1
Status: **done** (app shell, nav, role switcher, placeholder routes, minimal types & mock store)

Files touched:

- `package.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs`, `eslint.config.mjs`, `.gitignore`
- `src/app/globals.css`, `src/app/layout.tsx`, `src/app/page.tsx`
- `src/app/command-center/page.tsx`
- `src/app/lifecycle/page.tsx`, `opportunity-pool`, `new-product-incubation`, `launch-validation`, `growth-optimization`, `legacy-upgrade`, `review-capture`
- `src/app/projects/page.tsx`, `src/app/projects/[projectId]/page.tsx`
- `src/app/action-hub/page.tsx`, `src/app/governance/page.tsx`, `src/app/assets/page.tsx`
- `src/config/nav.ts`
- `src/domain/types/*` (enums, entity, kpi, action, agent, project-object, index)
- `src/state/app-store.tsx`, `src/state/mock-projects.ts`
- `src/components/layout/*`, `src/components/shell/page-placeholder.tsx`

Notes:

- **Tooling**: Repo folder name is not npm-safe; `package.json` `name` is `commerce-operating-os`. Next.js 15 + React 19 + Tailwind v4; manual scaffold because `create-next-app` rejected the directory name.
- **IA**: Left nav follows IA_AND_PAGES §1: hubs (Command Center, Projects, Action Hub, Governance, Assets) plus Lifecycle group (Overview, five stage routes, Review → `/lifecycle/review-capture`).
- **`/projects` list**: IA mapping table only lists `[projectId]` detail; M1 adds a **projects index** for the “Projects” primary nav and deep links to demo IDs — drop or replace if product prefers URL-only entry.
- **Mock store**: `src/state/app-store.tsx` — client `useSyncExternalStore` + `AppStoreProvider`; **RoleView** persisted under `localStorage` key `cos_role_view`. Documented here because AGENTS.md only specifies `src/domain/types` and `src/domain/mappers`, not store location.
- **Domain types**: M1 最初仅为 `ProjectObject` 必选字段；**Milestone 2** 已按 DATA_MODEL §16.1 补齐可选关系与关联类型（见 M2）。
- **Home**: `/` redirects to `/command-center`; role-specific landing can diverge in M3/M4.

Validation: `npm run build` and `npm run lint` pass.

### Ubuntu 一键部署升级（2026-04-27）
Status: **done**

- `install.sh` 改为 **Ubuntu-only**：启动先校验 `/etc/os-release`，非 Ubuntu 直接失败；默认通过 `apt-get` 安装编译依赖、`python3.11/3.12` 所需组件和 Playwright 运行库，并支持 `--skip-apt`。
- Python / venv 分拆：
  - 根目录 `.venv` 固定 `python3.11`
  - `third_party/MediaCrawler/.venv` 固定 `python3.11`
  - `third_party/TrendRadar/.venv` 固定 `python3.12`
- `third_party/TrendRadar` 改为部署期自动 clone，并固定 checkout 到 `b1d09d08ea27e67382c044ba67bbb0af2fd8a979`；`third_party/deer-flow`、`third_party/hermes-agent` 不纳入部署。
- 部署期生成 `config/runtime.server.yaml`，主服务通过 `INTEL_HUB_RUNTIME_CONFIG` 只读取这份服务器配置，不再默认使用开发态 `config/runtime.yaml`；服务器配置中移除了开发机绝对路径 `xhs_sources`。
- 新增服务器启动入口 `apps/intel_hub/api/server_entry.py`，systemd 改为调用该入口；开发态 `start.sh` 仍保留，但不再作为部署用入口。
- systemd 产物与命名：
  - `ontology-os.service`
  - `ontology-trendradar.service`
  - `ontology-trendradar.timer`
- 登录态部署方式改为 `--sessions-dir <path>` 导入已有 `storage_state`；导入目标统一为根目录 `data/sessions/`，并优先通过 symlink 将 `third_party/MediaCrawler/data/sessions` 对齐到同一路径。
- 服务器浏览器策略统一收口到 `BROWSER_HEADLESS`：
  - `POST /crawl-jobs` 默认写入 `headless`
  - `collector_worker` 在 Ubuntu CLI + 无登录态时会快速失败并提示先导入登录态
  - `XHSPublishService` / `NoteMetricsSyncer` 默认也读取同一环境变量
  - 服务器扫码登录接口改为明确返回“请导入登录态”，不再支持现场扫码
- 主系统运行依赖补齐到 `pyproject.toml`：
  - `feedparser`
  - `requests`
  - `dashscope`（通过 `vision` extra 暴露，安装脚本默认安装）
- `install.sh --doctor` 新增部署巡检：Ubuntu 版本、Python 3.11/3.12、三套 venv、TrendRadar/MediaCrawler、sessions、runtime.server、LLM keys 缺失项。

### Pre-M2：界面中文业务化命名（仅展示文案）

Status: **done**（路由、文件名、`src/domain/types`、`RoleView` 等标识未改）

范围：左侧一级/商品经营主线二级导航、顶部角色切换、`PagePlaceholder` 与壳层提示、mock 中与界面相关的说明与示例人名；新增 `LIFECYCLE_STAGE_LABELS` 供阶段中文展示（如上下文条），底层 `LifecycleStage` 枚举不变。

命名对齐（示例）：经营指挥台、商品经营主线、商品项目、动作中心、风险与审批、复盘沉淀、经验资产库；阶段：商机池、新品孵化、首发验证、增长优化、老品升级；角色：老板、产品研发总监、运营与营销总监、视觉总监。

Files touched:

- `src/config/nav.ts`（`LIFECYCLE_STAGE_LABELS`、导航中文标签）
- `src/state/mock-projects.ts`（`ROLE_LABELS` 与示例文案业务化）
- `src/components/layout/app-shell.tsx`, `side-nav.tsx`, `role-switcher.tsx`, `operating-context-strip.tsx`
- `src/components/shell/page-placeholder.tsx`
- `src/app/layout.tsx`（`metadata` 中文）
- `src/app/**/page.tsx`（各占位页标题与说明）

Validation: `npm run build` / `npm run lint` 通过后记录。

补充（对照 `lang.md`）：全站展示用语与《整站中英命名对照表》对齐做了一轮收敛，例如 **经营脉冲**（不用「今日脉冲」）、**待审批**（不用口语「待批」）、商机池场景的 **商机评分**、主线总览 **商品经营主线总览**、治理页 **风险与审批台**、避免文案里「商品项目对象」与「项目/对象」混称；一级导航仍用简短 **风险与审批**，与表中 Console/页面专名区分。

### Milestone 2
Status: **done**（商品经营主线总览、ProjectObject 类型落地、商品项目详情骨架、mock VM、中文 UI）

Files touched:

- `src/domain/types/enums.ts`（ConfidenceLevel、ReviewVerdict、Asset*、PolicyEnforcementMode）
- `src/domain/types/evidence.ts`, `decision.ts`, `opportunity.ts`, `product-definition.ts`, `expression.ts`, `exception.ts`, `review-asset.ts`, `realtime.ts`, `view-models.ts`
- `src/domain/types/action.ts`（ApprovalRecord、ExecutionLog）
- `src/domain/types/project-object.ts`（§16.1 可选字段）
- `src/domain/types/index.ts`
- `src/domain/mappers/display-zh.ts`（健康度/风险/审批/智能体/复盘/打样/表达就绪等中文标签）
- `src/domain/mappers/to-lifecycle-overview-vm.ts`, `to-project-page-vm.ts`
- `src/domain/selectors/group-by-stage.ts`, `index.ts`
- `src/state/mock-projects.ts`, `mock-exceptions.ts`
- `src/state/app-store.tsx`（`exceptions` 并列状态）
- `src/components/cards/management-panel.tsx`
- `src/components/lifecycle/lifecycle-overview-view.tsx`
- `src/components/project/project-detail-view.tsx`
- `src/app/lifecycle/page.tsx`, `src/app/projects/page.tsx`, `src/app/projects/[projectId]/page.tsx`

Notes:

- **LifecycleOverviewVM**：由 `toLifecycleOverviewVm(projects, exceptions)` 生成；`ExceptionItem` 无 `projectId` 的条目归入 **复盘沉淀** 阶段展示（全局兜底），已关联项目则按项目 `stage` 归类。
- **ProjectObjectPageVM**：`realtime` / `recentFeed` / `nextDecisionHint` 由 `toProjectPageVm` 从 `ProjectObject` 推导，非双写存储。
- **Mock 规模**：阶段覆盖六段 + `proj_m2_full` 全字段演示；未按 DATA_MODEL §19.1 的大规模种子执行，后续可再扩容。
- **详情页**：服务端 `getProjectById` + `notFound()`；与客户端 store 同源常量种子，M2 无服务端/客户端状态分叉。

Validation: `npm run build` and `npm run lint` pass.

### Milestone 3
Status: **done**（老板经营指挥台：`CEODashboardVM`、mapper、卡片与 `/command-center` 接入）

Files touched:

- `src/domain/types/view-models.ts`（`CEODashboardVM`）
- `src/domain/mappers/to-ceo-dashboard-vm.ts`（`toCeoDashboardVm`）
- `src/domain/mappers/display-zh.ts`（`triggeredByLabel`、`pulseCategoryLabel`、`signalFreshnessLabel`）
- `src/components/cards/pulse-brief-block.tsx`, `battle-project-card.tsx`, `ceo-approval-row.tsx`, `ceo-exception-row.tsx`, `resource-summary-panel.tsx`, `org-ai-summary-panel.tsx`
- `src/components/dashboards/ceo-command-center-view.tsx`
- `src/app/command-center/page.tsx`

Notes:

- **脉冲**：`PulseItem[]` 由全局例外（按严重度）、各项目 `latestPulse` / `keyBlocker`、待审批聚合条合成，列表上限 12 条；无数据时一条占位 `review` 脉冲。
- **关键战役（topProjects）**：按 `projectBattleScore` 排序取 5 条——`增长优化` +40、`首发验证` +20，`health`（critical→1）加权 ×15，再加 `priority`；偏「势能阶段 + 不健康」而非纯字典序。
- **待审批（topApprovals）**：扁平化 `approvalStatus === "pending"`，按 `risk` 降序、`requiresHumanApproval` 优先，取 6 条。
- **例外（topExceptions）**：按 `severity` 降序取 5 条。
- **`resourceSummary` / `orgAISummary`**：与当前 mock 的项目数、待批数、`agentStates` 运行/待人数量挂钩的**原型摘要**文案，不虚构金额与编制。
- **人在环路**：待批行对 `requiresHumanApproval` 展示「需您拍板」，例外行对 `requiresHumanIntervention` 展示「需人工介入」；`triggeredByLabel` 区分人为 / 经营建议 / 场景智能体 / 自动化规则。

Validation: `npm run build` and `npm run lint` pass.

### Milestone 4
Status: **done**（三类总监工作台：与老板台共用 `/command-center` + `roleView` 切换；共享脉冲底座与领域模型）

Files touched:

- `src/domain/types/view-models.ts`（`ProductRDDirectorVM`、`GrowthDirectorVM`、`VisualDirectorVM`，对齐 DATA_MODEL §18.2–18.4）
- `src/domain/mappers/pulse-shared.ts`（全量脉冲收集、`buildPulseBundleForRole`、`orderAndSlicePulseItems` 视角排序、`sortPendingActions`）
- `src/domain/mappers/to-ceo-dashboard-vm.ts`（改为依赖 `pulse-shared`，逻辑不变）
- `src/domain/mappers/to-product-rd-vm.ts`, `to-growth-vm.ts`, `to-visual-vm.ts`
- `src/domain/mappers/display-zh.ts`（`assetTypeLabel`）
- `src/components/cards/growth-plan-compare-block.tsx`, `growth-blocker-map.tsx`, `growth-agent-status-block.tsx`, `visual-version-pool-row.tsx`, `visual-asset-row.tsx`
- `src/components/dashboards/command-center-entry.tsx`, `product-rd-director-view.tsx`, `growth-director-view.tsx`, `visual-director-view.tsx`
- `src/app/command-center/page.tsx`（入口改为 `CommandCenterEntry`）
- `src/state/mock-projects.ts`（方案对比 / 视觉池：补充决策多选项、双主图版本、`proj_legacy` 表达规划等最小种子）

Notes:

- **role-as-view**：不新增 `/director/*` 路由；`CommandCenterEntry` 仅按 `roleView` 切换 VM 与视图，底层仍为 `ProjectObject[]` + `ExceptionItem[]`。
- **脉冲共享**：`collectAllPulseItems` 与 CEO 原先生成序一致；非 CEO 角色经 `orderAndSlicePulseItems` 按阶段/类别加权后截断 12 条，摘要文案按角色定制。
- **产品研发**：`topSamplingRisks` = 有 `definition` 的项目，按 `feasibilityRisk`、打样进行中、`blockingIssues` 加权排序取 5。
- **增长**：`blockers` 为全量例外按严重度排序；UI 用 `groupBlockersByStage` 映射阶段（无 `projectId` 归入复盘沉淀，与 M2 主线总览一致）；方案对比为「决策选项 ≥2 或视觉版本 ≥2」的首发∪增长项目原型规则。
- **视觉**：`creativeVersionPool` 跨项目扁平去重；`expressionProjects` 限定孵化/首发/增长/老品且存在 `expression`；`upgradeCandidates` = `legacy_upgrade` 且有表达规划。
- **mock**：未按 DATA_MODEL §19.1 大规模扩容；仅补足 M4 演示所需的对比与版本池条目。

Validation: `npm run build` and `npm run lint` pass.

### Milestone 5
Status: **done**（五阶段生命周期工作台 prototype：商机池 / 新品孵化 / 首发验证 / 增长优化 / 老品升级；复盘沉淀路由未改）

Files touched:

- `src/domain/types/view-models.ts`（`*StageWorkspaceVM` 五段页面层 VM）
- `src/domain/mappers/stage-pulse.ts`（`buildStagePulseBundle`、`exceptionsForLifecycleStage`、`collectStagePulseItems`）
- `src/domain/mappers/pulse-shared.ts`（`collectAllPulseItems` 可选 `approvalSummary`，支持「本阶段待审批」文案）
- `src/domain/mappers/to-lifecycle-stage-workspace-vm.ts`（五阶段 mapper）
- `src/domain/selectors/plan-compare-candidates.ts`（`filterPlanCompareCandidates`，供阶段页与增长方案对比卡共用）
- `src/domain/mappers/display-zh.ts`（`confidenceLevelLabel`、`opportunityRecommendationLabel`）
- `src/components/cards/growth-plan-compare-block.tsx`（改为引用 selector）
- `src/components/lifecycle/workspace/agent-strip.tsx`
- `src/components/lifecycle/opportunity-pool-workspace-view.tsx`, `new-product-incubation-workspace-view.tsx`, `launch-validation-workspace-view.tsx`, `growth-optimization-workspace-view.tsx`, `legacy-upgrade-workspace-view.tsx`
- `src/app/lifecycle/opportunity-pool/page.tsx`, `new-product-incubation/page.tsx`, `launch-validation/page.tsx`, `growth-optimization/page.tsx`, `legacy-upgrade/page.tsx`
- `src/state/mock-projects.ts`（`proj_demo_oppo` 增加 `opportunityAssessment`；`proj_incubation` 增加会签待批动作）

Notes:

- **阶段脉冲**：仅本阶段 `ProjectObject` + `projectId` 落在本阶段内的 `ExceptionItem`；**无 `projectId` 的全局例外不进入阶段脉冲**（仍在指挥台/主线总览等处可见）。
- **待审批汇总文案**：阶段内脉冲使用「本阶段待审批…」；全局指挥台仍为「全盘待审批…」。
- **孵化泳道**：`healthy` → 正常推进，`watch` → 需关注，`at_risk`/`critical` → 风险干预。
- **首发方案对比**：与 M4 相同规则（`filterPlanCompareCandidates`）。
- **增长优化动作列表**：待审批优先，其余按原顺序附带展示 `triggeredBy` / 审批 / 执行状态。
- **老品再上市验证**：`relaunchValidationBullets` 为固定骨架文案，非闭环复盘。
- **共享模块对照**：商机池 — `ManagementPanel`、`PulseBriefBlock`、`BattleProjectCard`、`CeoApprovalRow`、`CeoExceptionRow`、`AgentStrip`、`display-zh`；新品孵化 — 同上 + 三列泳道；首发验证 — 同上 + `GrowthPlanCompareBlock`；增长优化 — 同上 + 动作行内标签；老品升级 — 同上 + 升级方向列表与骨架清单。

Validation: `npm run build` and `npm run lint` pass.

### Milestone 6
Status: **done**（动作中心 + 风险与审批台 prototype；决策到动作生命周期与例外优先治理）

Files touched:

- `src/domain/types/policy-boundary.ts`（`PolicyBoundary`，对齐 DATA_MODEL §13.2）
- `src/domain/types/index.ts`（导出 policy-boundary）
- `src/domain/types/view-models.ts`（`ActionHubVM`、`GovernanceVM`、`ActionHubRow`、`GovernanceDecisionRow`）
- `src/state/mock-governance.ts`（`createMockPolicyBoundaries`）
- `src/state/app-store.tsx`（`policyBoundaries` 并列状态）
- `src/state/mock-projects.ts`（`proj_incubation` 低置信决策；`proj_m2_full` 多动作态、`approvals`、`executionLogs`）
- `src/domain/mappers/to-action-hub-vm.ts`, `to-governance-vm.ts`
- `src/domain/mappers/display-zh.ts`（`policyAppliesToLabel`、`policyEnforcementModeLabel`、`exceptionSourceLabel`）
- `src/components/governance/action-hub-action-row.tsx`, `execution-log-row.tsx`, `approval-drawer.tsx`, `policy-boundary-card.tsx`, `action-hub-view.tsx`, `governance-console-view.tsx`
- `src/app/action-hub/page.tsx`, `src/app/governance/page.tsx`

Notes:

- **动作区分（代码层）**：`ActionHubActionRow` 同时展示 `triggeredByLabel`（建议来源）、`executionModeLabel`（人工/智能体/自动）、`executionStatusLabel`、`approvalStatusLabel`；列表分区由 `toActionHubVm` 按 `ActionItem` 字段拆分——待批、智能体监控（`agent` + `queued`/`in_progress`）、执行中、高风险、自动完成、非自动完成、回滚。
- **治理例外优先**：`GovernanceConsoleView` 将 **例外队列** 置顶，其次智能体异常、规则边界命中，再收敛高风险待批与低置信决策；`toGovernanceVm` 对 `exceptions` 按严重度排序。
- **审计**：`ApprovalRecord` 与 `ExecutionLog` 从各 `ProjectObject.approvals` / `executionLogs` 扁平聚合；动作中心与风险台共用 `ExecutionLogRow` 展示逻辑。
- **审批抽屉**：原型 UI，按钮占位不产生状态变更。
- **低置信**：`decisionObject.confidence === "low"` 进入治理台列表（mock 在 `proj_incubation`）。

Validation: `npm run build` and `npm run lint` pass.

### Milestone 7
Status: **done**（复盘沉淀台 + 经验资产库 + review-to-asset 最小 ViewModel 与映射）

Files touched:

- `src/domain/types/view-models.ts`（`ReviewToAssetVM`、`ReviewCaptureWorkspaceVM`、`AssetHubVM`）
- `src/domain/mappers/to-review-capture-workspace-vm.ts`（含复盘项目分块与全库候选/已发布聚合）
- `src/domain/mappers/to-asset-hub-vm.ts`（`ASSET_HUB_TYPE_ORDER`、按 `AssetType` 分组）
- `src/domain/mappers/display-zh.ts`（`assetPublishStatusLabel`、`attributionCategoryLabel`；资产类型中文对齐「SOP 卡」「评测样本」）
- `src/state/mock-projects.ts`（`proj_review_cap`：多归因、多类型候选、已发布/已下线资产，用于闭环演示）
- `src/components/review/review-capture-view.tsx`（复盘台分区 UI）
- `src/components/assets/asset-hub-view.tsx`（资产库按类型双栏：已入库 / 候选）
- `src/app/lifecycle/review-capture/page.tsx`、`src/app/assets/page.tsx`（接入上述视图）

Notes:

- **页面层 review-to-asset**：复盘台按「结果复盘 → 归因 → 经验 → 打法 → 资产候选 → 发布确认」递进分区；徽标区分 AI 结构化、待沉淀/待人工、已正式入库；与经验资产库互为链接。
- **代码层 review-to-asset**：`ReviewToAssetVM` 将单项目的 `ReviewSummary` + `AssetCandidate[]` + `PublishedAsset[]` 捆成一条链；`ReviewCaptureWorkspaceVM.blocks[]` 为多项目工作台；`toAssetHubVm` 从全部 `ProjectObject` 扁平聚合候选与已发布，`AssetHubView` 仅消费 ViewModel。
- **Prototype**：无真实「发布」动作，状态以 mock 的 `approvalStatus` / `AssetPublishStatus` 驱动。

Validation: `npm run build` and `npm run lint` pass.

### 商品项目详情页（协作中心）补强
Status: **done**（主线协作摘要 + 协同状态条 + 决策与闭环一体化）

Files touched:

- `src/domain/types/view-models.ts`（`ProjectObjectPageVM.nextDecisionHint`）
- `src/domain/mappers/to-project-page-vm.ts`（`deriveNextDecisionHint`：待批动作 → 推荐方案 → 需人工决策 → 默认兜底）
- `src/domain/mappers/display-zh.ts`（`projectTypeLabel`、`personRoleLabel`）
- `src/components/project/project-detail-view.tsx`（分区重构；复用 `ActionHubActionRow`、`ExecutionLogRow`）

Notes:

- **新增关键分区**：项目协作摘要（类型/阶段/目标/健康/风险/阻塞/脉冲/下一关键决策点）、协同状态条（经营大脑与 `EvidencePack.refs`、场景 Agent、执行端计数、人工节点与干系人）、增强决策对象（方案 A/B/C、风险与预期收益、推荐与是否需批）、经营闭环（建议/待批/执行中/自动完成/回写/回滚动作 + 复盘摘要 + 资产候选 + 审计记录 + 可选最近动态）。
- **人 × 大脑 × Agent × 执行**：大脑用 `DecisionObject`+证据；Agent 用 `AgentState[]`；执行端用 `ActionItem` 聚合的件数与闭环列表（与动作中心同一套行列组件）；人工节点用 `stakeholders`、`ApprovalRecord` 与待批动作数量。
- **收敛**：移除原重复板块「实时状态」「独立动作列表」「独立智能体状态」「独立复盘与资产」的平铺，信息并入摘要、协同条与经营闭环，避免三遍展示。

Validation: `npm run build` and `npm run lint` pass.

### 主线联动（商品项目 ↔ 动作中心 ↔ 复盘沉淀）
Status: **done**（prototype 深链 + 查询参数收窄 + 来源上下文展示）

Files touched:

- `src/domain/mappers/to-action-hub-vm.ts`（`toActionHubVmForProject`）
- `src/domain/types/view-models.ts`（`ReviewCaptureWorkspaceVM.blocks` 增 `targetSummary` / `statusSummary` / `kpiSummary`）
- `src/domain/mappers/to-review-capture-workspace-vm.ts`（`formatKpiSummary` 填充块字段）
- `src/components/governance/action-hub-view.tsx`、`action-hub-action-row.tsx`
- `src/app/action-hub/page.tsx`（`Suspense` + `useSearchParams`）
- `src/components/project/project-detail-view.tsx`（「主线联动」入口）
- `src/components/review/review-capture-view.tsx`、`src/app/lifecycle/review-capture/page.tsx`

Notes:

- **URL 约定**：`/action-hub?projectId=<id>` 仅本项目动作与审计；`focus=pending` 仅待审批分区；`focus=execution` 将执行流水置顶并附「全部动作分区」链接；`/lifecycle/review-capture?projectId=<id>` 收窄复盘块，无匹配时提示并链回全量。
- **页面层闭环**：商品项目「主线联动」三链进动作中心 + 一进复盘台；动作卡展示来源项目/阶段/当前状态并链回项目详情；复盘块展示来源摘要、KPI、资产候选「关联项目」链。
- **数据**：单项目动作中心复用 `toActionHubVm([project])`。

Validation: `npm run build` and `npm run lint` pass.

### 协同可见性增强（四层分工在界面上的统一表达）
Status: **done**（与 AGENTS.md 第 4 条「区分人工决策 / 经营大脑 / 场景 Agent / 自动化执行」对齐）

Files touched:

- `src/components/cards/operating-layer-badge.tsx`（新建：`OperatingLayerBadge`、`OperatingLayerLegend`、`OperatingLayerLegendInline`、`triggeredByToLayer`、`exceptionSourceToLayer`、`describeActionProgressLine`）
- `src/components/governance/action-hub-action-row.tsx`、`action-hub-view.tsx`
- `src/components/governance/governance-console-view.tsx`、`execution-log-row.tsx`
- `src/components/cards/ceo-exception-row.tsx`
- `src/components/project/project-detail-view.tsx`
- `src/components/review/review-capture-view.tsx`

Notes:

- **视觉语言**：紫系「经营建议」、天蓝「智能体」、teal「自动化」、琥珀「人为发起」；徽章在深色界面上使用浅色字 + 半透明底（不依赖 `prefers-color-scheme`）；关键页顶部或协同区使用同一套 `OperatingLayerLegend`。
- **动作卡片**：每行动作以 `triggeredBy` 推导主徽章，并以 `describeActionProgressLine` 写清「谁以何种执行模式把状态/审批推到哪一步」，替代泛泛「已更新」。
- **执行流水**：`ExecutionLogRow` 用完整句式标注「人工执行方 / 场景 Agent / 自动执行端（actorId）于何时将动作置为何状态」。
- **风险台例外**：`exceptionSourceToLayer` 将 `ExceptionItem.source` 映射到主责任层；`requiresHumanIntervention` 且主层非「人为发起」时额外叠「人为发起」徽章。
- **复盘台**：Provenance 与闭环统计文案改为「经营大脑 · …」口径，header 下挂紧凑四层 inline 图例。
- **商品项目详情**：协同状态条内嵌全量图例，四个子卡片标题旁固定对应徽章；执行端统计用词区分自动化完成与人工/Agent 回写。

Validation: `npm run build` and `npm run lint` pass.

### 交互补强（Figma 对齐）
Status: **done**（不新开路由、不扩展领域 mock 业务范围；侧重单一视觉中心、摘要→抽屉、阶段/动作 rail、页级主动作）

Files touched（主要）:

- `src/components/shell/drawer-shell.tsx`、`src/components/governance/action-detail-drawer.tsx`、`src/components/governance/approval-drawer.tsx`（侧滑壳复用；审批按钮本地反馈）
- `src/components/cards/stage-progress-rail.tsx`、`src/components/governance/action-hub-progress-rail.tsx`、`src/components/cards/growth-dual-stage-rail.tsx`
- `src/components/cards/provenance-ribbon.tsx`、`src/components/review/review-capture-view.tsx`、`src/components/assets/asset-hub-view.tsx`（来源条深色可读共用）
- `src/components/shell/walkthrough-hint-panel.tsx`（`defaultCollapsed` + 展开/收起）
- `src/components/dashboards/ceo-command-center-view.tsx`、`growth-director-view.tsx`（脉冲优先顺序、主动作链接、列表 Top2 + 全量入口）
- `src/components/governance/action-hub-view.tsx`、`action-hub-action-row.tsx`
- `src/components/project/project-detail-view.tsx`（决策焦点、方案对比栅格、经营闭环 compact 行 + 双抽屉）

**原则 1–10 对照（简表）**

| # | 原则要点 | 落点 |
|---|----------|------|
| 1 | 脉冲优先 | CEO/增长：脉冲块置顶；走查默认折叠让出首屏 |
| 2 / 8 | 单一主动作 | 指挥台/增长/动作中心：链 `/action-hub?focus=pending` 等主按钮 |
| 3 | 降权次要区 | 项目详情协同图例收纳；动作中心图例默认折叠 |
| 4 | 决策焦点 | 项目详情「决策焦点」卡 + 主 CTA |
| 5 / 9 | 摘要 + 深钻 | 动作行 compact + `ActionDetailDrawer`；复盘首屏摘要 + 完整抽屉 |
| 6 | 对比分析 | 项目详情方案双列对比；增长「方案对比」紧随脉冲作分析区 |
| 7 | 阶段可见 | `StageProgressRail`、动作分区 rail、`GrowthDualStageRail` |
| 10 | 即时反馈 | `ApprovalDrawer` 同意/驳回短时 `aria-live` 提示（原型） |

Validation: `npm run build` and `npm run lint` pass.

### 交互/视觉系统融合（Enterprise + Linear + AI-native）
Status: **done**（仅设计令牌与壳层/通用容器；不改路由与领域模型）

Notes:

- **globals.css**：微调深色分层与阴影（Linear 式 elevation）、环境径向光 + 极轻紫系 `ai-tint`（AI 协同暗示）、`--accent-foreground` 与 `::selection`；主内容区 `.app-workspace` 细点阵（数据台可读性）；`.panel-top-sheen` 卡片顶栏微渐变边（智能层提示）；`.font-mono-data` 供 ID/指标等宽展示。
- **layout.tsx**：注入 `JetBrains_Mono` 为 `--font-mono`。
- **AppShell / SideNav / RoleSwitcher / OperatingContextStrip**：顶栏与侧栏层次、导航与视角切换的过渡与字距；主区去掉纯色底叠加以点阵。
- **ManagementPanel / WalkthroughHintPanel / DrawerShell**：与令牌对齐的 ring、顶栏 sheen、抽屉纵向渐变。

Validation: `npm run build` and `npm run lint` pass.

### 项目交互设计原则对齐（PROJECT_INTERACTION_DESIGN_PRINCIPLES）
Status: **done**（仅 UI/交互表现；**未改**领域类型与 mock 数据形状）

依据仓库根目录《PROJECT_INTERACTION_DESIGN_PRINCIPLES.md》落实要点：

- **脉冲驱动（§1.2.1）**：`PulseBriefBlock` 采用摘要区 + 快扫 KPI（高敏/风险阻塞/待决策计数）+ `PulseIndicator` + `pulse.generatedAt` 时间脚注；摘要包在 `AiSignalFrame`。
- **异常优先（§1.2.2）**：脉冲分项与指挥台 `CeoExceptionRow`、`CeoApprovalRow`、`BattleProjectCard` 使用 `visual-surfaces.ts` 按风险/健康度语义上色与边框（不改变排序逻辑，数据仍来自既有 VM）。
- **经营大脑可见性（§2.2）**：`AiSignalFrame`、`AiGlyph`；商品详情脉冲与复盘首屏结果摘要套同一语言。
- **三级信息（§4.1）**：脉冲块内明确「摘要 → 指标 → 列表」层级；复盘首屏继续Summary + 抽屉详情。
- **微交互（§8）**：卡片 `transition-colors duration-200`、链接 hover 与主按钮 `transition-colors`。

主要文件：`src/domain/mappers/visual-surfaces.ts`，`src/components/cards/pulse-brief-block.tsx`，`src/components/cards/ai-signal-frame.tsx`，`src/components/ui/pulse-indicator.tsx`、`ai-glyph.tsx`，`battle-project-card.tsx`，`ceo-exception-row.tsx`，`ceo-approval-row.tsx`，`project-detail-view.tsx`，`action-hub-view.tsx`，`review-capture-view.tsx`。

**置信度 % 与 Agent 动效（UI-only）**

- `display-zh`：`confidenceLevelPercent` / `confidenceLevelPercentLabel`（low/medium/high → 58% / 76% / 91% 等展示中值，**不新增**领域字段）。
- `AgentStatusIndicator`：`running` 旋转环、`waiting_human`/`blocked` 脉冲、`completed`/`failed`/`idle` 色点；用于 `AgentStrip`、`GrowthAgentStatusBlock`、商品详情协同条、经营主线总览智能体列表。
- 排版：`ManagementPanel` / 脉冲主标题 / `AiSignalFrame` / `.app-page-title` / 抽屉标题与正文整体放大一号，便于扫描。

Validation: `npm run build` and `npm run lint` pass.

### 走查模式补强（管理层主线走查辅助）
Status: **done**（轻量 UI；不改底层领域模型）

Files touched:

- `src/components/shell/walkthrough-hint-panel.tsx`（老板 / 三总监工作台顶部「走查提示」）
- `src/components/project/project-detail-view.tsx`（「当前一步看板」：阶段、最大问题、推荐动作、人工拍板语境）
- `src/components/lifecycle/lifecycle-overview-view.tsx`（「走查快速进入项目」：每阶段代表项目 + Top 风险/阻塞 + 阶段工作台链）
- `src/components/cards/pulse-brief-block.tsx`、`ceo-exception-row.tsx`、`ceo-approval-row.tsx`（关联 `relatedProjectId` / `projectId` / `sourceProjectId` 时进入项目详情）
- `src/components/cards/growth-blocker-map.tsx`（例外带来源项目时进入详情）
- `src/components/dashboards/ceo-command-center-view.tsx`、`growth-director-view.tsx`、`product-rd-director-view.tsx`、`visual-director-view.tsx`（挂载走查提示）

Notes:

- **适合主线走查的页面**：商品经营主线总览（阶段代表项目）、各总览工作台（脉冲与风险链到项目）、商品项目详情（当前一步看板 + 既有协作摘要/联动）。
- **非**正式 onboarding：提示文案为静态角色模板 + 现有字段推导看板。

Validation: `npm run build` and `npm run lint` pass.
