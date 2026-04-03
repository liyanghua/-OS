# Information Architecture and Pages

## 1. Global Navigation

一级导航建议如下：

- Command Center
- Lifecycle
- Projects
- Action Hub
- Governance
- Review
- Assets

## 2. Role Views

顶部角色切换：

- CEO
- Product R&D Director
- Growth Director
- Visual Director

角色视图只改变默认首页、默认排序和默认摘要，不改变底层对象。

---

## 3. Core Pages

### 3.1 CEO Command Center

Goal:
- show top business pulse
- show top opportunities, top risks, top pending approvals
- show battle status and resource allocation
- show organization and AI efficiency

Core modules:
- Business pulse cards
- Battle cards
- Growth engine cards
- Resource allocation cards
- High-risk approval cards
- Org/AI efficiency cards

Core models:
- `PulseBundle`
- `ProjectObject[]`
- `ActionItem[]`
- `ExceptionItem[]`

---

### 3.2 Product R&D Director Desk

Goal:
- review opportunity pool
- review new product incubation pipeline
- compare product definition options
- track sampling and feasibility risk
- review legacy upgrade opportunities

Core modules:
- Opportunity pulse
- Opportunity list
- Incubation board
- Product definition panel
- Sampling risk panel
- Upgrade candidate panel

Core models:
- `PulseBundle`
- `ProjectObject[]`
- `DecisionObject`
- `ProductDefinition`
- `SamplingReview`

---

### 3.3 Growth Director Desk

Goal:
- review launch and growth pulse
- identify top product opportunities/risks
- compare optimization plans
- approve key actions
- track blockers and agent state

Core modules:
- Growth pulse
- Project battle list
- Plan comparison
- Approval queue
- Blocker map
- Agent state cards
- Live KPI cards

Core models:
- `PulseBundle`
- `ProjectObject[]`
- `ActionItem[]`
- `ExceptionItem[]`
- `AgentState[]`
- `ProjectRealtimeSnapshot`

---

### 3.4 Visual Director Desk

Goal:
- review visual expression priorities
- compare visual versions
- identify visual upgrade opportunities
- track template reuse and visual asset quality

Core modules:
- Expression pulse
- Launch expression prep
- Version comparison
- Legacy visual upgrade
- Template reuse
- AI visual recommendations

Core models:
- `PulseBundle`
- `ProjectObject[]`
- `ExpressionPlan`
- `CreativeVersion[]`
- `PublishedAsset[]`

---

### 3.5 Lifecycle Overview

Goal:
- show all projects across lifecycle stages
- show bottlenecks, approvals, health and live state
- serve as operating map of the system

Core modules:
- Lifecycle flow
- Stage counts
- Bottleneck heatmap
- Approval density
- Agent activity
- Stage health summary

Core models:
- `ProjectObject[]`
- `LifecycleOverviewVM`
- `ProjectRealtimeSnapshot[]`
- `ExceptionItem[]`
- `ActionItem[]`

---

### 3.6 Opportunity Pool

Goal:
- maintain opportunity candidates
- score and rank them
- turn opportunity into project

Core modules:
- Opportunity pulse
- Opportunity card list
- Trend / competitor / demand blocks
- Priority ranking
- Suggested project creation

Core models:
- `ProjectObject[]`
- `OpportunitySignal[]`
- `OpportunityAssessment`
- `DecisionObject`

---

### 3.7 New Product Incubation

Goal:
- move opportunity into launchable product project

Core modules:
- Incubation swimlane
- Product definition cards
- Sampling risk
- Sign-off checkpoints
- AI-generated definitions

Core models:
- `ProjectObject[]`
- `ProductDefinition`
- `SamplingReview`
- `DecisionObject`
- `ActionItem[]`

---

### 3.8 Launch Validation

Goal:
- validate whether launched product is worth scaling

Core modules:
- Launch pulse
- Launch project list
- Goal vs result
- Content / visual version comparison
- Diagnosis block
- Scale / adjust / pause recommendation

Core models:
- `ProjectObject[]`
- `ExpressionPlan`
- `CreativeVersion[]`
- `DecisionObject`
- `ProjectRealtimeSnapshot`

---

### 3.9 Growth Optimization

Goal:
- optimize mature and high-potential products
- support explosive growth strategy

Core modules:
- Growth pulse
- Product battle zone
- Diagnosis cards
- Optimization action queue
- Content / visual optimization
- Live project health

Core models:
- `ProjectObject[]`
- `DecisionObject`
- `ActionItem[]`
- `AgentState[]`
- `ProjectRealtimeSnapshot`

---

### 3.10 Legacy Upgrade

Goal:
- identify and execute upgrade opportunities for legacy products

Core modules:
- Upgrade pulse
- Upgrade candidates
- Upgrade value assessment
- Upgrade direction options
- Relaunch validation
- Historical upgrade cases

Core models:
- `ProjectObject[]`
- `DecisionObject`
- `ProductDefinition`
- `ExpressionPlan`
- `ReviewSummary`

---

### 3.11 Project Object Page

Goal:
- unify all collaboration around one project object


Core modules:
- Project header
- Decision object
- Product definition
- Expression section
- Action section
- Live state section
- Review and assets section
- Role view switch

Core models:
- `ProjectObject`
- `DecisionObject`
- `ProductDefinition`
- `ExpressionPlan`
- `ActionItem[]`
- `AgentState[]`
- `ReviewSummary`
- `AssetCandidate[]`
- `ProjectRealtimeSnapshot`

---

### 3.12 Action Hub

Goal:
- manage decision-to-action lifecycle

Core modules:
- Pending approvals
- In-progress actions
- Auto-executed actions
- Result writebacks
- Rollback actions
- Execution feed
- Audit trail

Core models:
- `ActionItem[]`
- `ApprovalRecord[]`
- `ExecutionLog[]`

---

### 3.13 Governance Console

Goal:
- manage exceptions, high-risk items, low-confidence suggestions, and agent failures

Core modules:
- Exception queue
- High-risk approvals
- Low-confidence suggestions
- Agent failures
- Policy / boundary panel
- Audit records

Core models:
- `ExceptionItem[]`
- `ActionItem[]`
- `DecisionObject[]`
- `PolicyBoundary[]`
- `ExecutionLog[]`

---

### 3.14 Review to Asset Loop

Goal:
- turn outcome into learning and reusable assets

Core modules:
- Result summary
- Attribution
- Lessons
- Reusable strategy extraction
- Asset candidates
- Approval for standardization
- Published assets

Core models:
- `ReviewSummary`
- `AttributionFactor[]`
- `AssetCandidate[]`
- `PublishedAsset[]`

---

### 3.15 Asset Hub

Goal:
- manage reusable operating assets

Core modules:
- Cases
- Rules
- Templates
- Skills
- SOP cards
- Evaluation sets
- Candidate assets

Core models:
- `PublishedAsset[]`
- `AssetCandidate[]`

---

## 4. Product-to-Page Mapping

This section explains how product goals map to pages and objects.

| Product Goal | Primary Page / Area | Core Objects |
|---|---|---|
| Show executive business pulse, key risks, and strategic approvals | `CEO Command Center` | `PulseBundle`, `ProjectObject`, `ActionItem`, `ExceptionItem` |
| Review opportunities, incubation status, and definition quality | `Product R&D Director Desk`, `Opportunity Pool`, `New Product Incubation` | `ProjectObject`, `OpportunityAssessment`, `DecisionObject`, `ProductDefinition`, `SamplingReview` |
| Review launch, growth, blockers, approvals, and battle priorities | `Growth Director Desk`, `Launch Validation`, `Growth Optimization` | `ProjectObject`, `DecisionObject`, `ActionItem`, `ProjectRealtimeSnapshot`, `ExceptionItem` |
| Review expression strategy, version performance, and reusable visual assets | `Visual Director Desk` | `ProjectObject`, `ExpressionPlan`, `CreativeVersion`, `PublishedAsset` |
| Show lifecycle distribution, bottlenecks, and health | `Lifecycle Overview` | `ProjectObject`, `ProjectRealtimeSnapshot`, `ActionItem`, `ExceptionItem` |
| Center all collaboration around one project | `Project Object Page` | `ProjectObject`, `DecisionObject`, `ProductDefinition`, `ExpressionPlan`, `ActionItem`, `ReviewSummary` |
| Manage action lifecycle from suggestion to rollback | `Action Hub` | `ActionItem`, `ApprovalRecord`, `ExecutionLog` |
| Handle exceptions, policy boundaries, and high-risk actions | `Governance Console` | `ExceptionItem`, `PolicyBoundary`, `DecisionObject`, `ActionItem` |
| Turn review into reusable operating assets | `Review to Asset Loop`, `Asset Hub` | `ReviewSummary`, `AssetCandidate`, `PublishedAsset` |

---

## 5. Page-to-Code Mapping

This section exists to guide implementation and keep Codex aligned.

| Page / Area | Intended Code Locations |
|---|---|
| CEO Command Center | `src/app/command-center/page.tsx`, `src/components/dashboards/*`, `src/components/cards/*` |
| Product R&D Director Desk | `src/app/command-center/page.tsx` or future `src/app/director/product-rd/page.tsx`, `src/components/dashboards/*`, `src/components/cards/*` |
| Growth Director Desk | `src/app/command-center/page.tsx` or future `src/app/director/growth/page.tsx`, `src/components/dashboards/*`, `src/components/cards/*` |
| Visual Director Desk | `src/app/command-center/page.tsx` or future `src/app/director/visual/page.tsx`, `src/components/dashboards/*`, `src/components/cards/*` |
| Lifecycle Overview | `src/app/lifecycle/page.tsx`, `src/components/lifecycle/*`, `src/domain/mappers/*` |
| Opportunity Pool | `src/app/lifecycle/opportunity-pool/page.tsx`, `src/components/cards/*`, `src/components/project/*` |
| New Product Incubation | `src/app/lifecycle/new-product-incubation/page.tsx`, `src/components/project/*`, `src/components/cards/*` |
| Launch Validation | `src/app/lifecycle/launch-validation/page.tsx`, `src/components/project/*`, `src/components/cards/*` |
| Growth Optimization | `src/app/lifecycle/growth-optimization/page.tsx`, `src/components/project/*`, `src/components/cards/*` |
| Legacy Upgrade | `src/app/lifecycle/legacy-upgrade/page.tsx`, `src/components/project/*`, `src/components/cards/*` |
| Review Capture | `src/app/lifecycle/review-capture/page.tsx`, `src/components/review/*`, `src/components/cards/*` |
| Project Object Page | `src/app/projects/[projectId]/page.tsx`, `src/components/project/*`, `src/domain/mappers/to-project-page-vm.ts` |
| Action Hub | `src/app/action-hub/page.tsx`, `src/components/governance/*`, `src/components/cards/*` |
| Governance Console | `src/app/governance/page.tsx`, `src/components/governance/*` |
| Asset Hub | `src/app/assets/page.tsx`, `src/components/review/*`, `src/components/cards/*` |

---

## 6. Global UI Requirements

Every important page should support:
- pulse-driven summary
- risk / confidence labels
- evidence panel
- approval state
- project health
- agent state or execution feed if relevant
- clear distinction between:
  - human decisions
  - AI recommendations
  - agent progress
  - automation results