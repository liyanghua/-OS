# AGENTS.md

## Read First

### Intel Hub Source of Truth

For work under `apps/intel_hub/`, `config/`, `data/`, and `docs/`, use the `docs/` folder as source of truth:

1. `docs/README_PRODUCT.md`
2. `docs/ARCHITECTURE.md`
3. `docs/IA_AND_PAGES.md`
4. `docs/DATA_MODEL.md`
5. `docs/PLAN.md`
6. `docs/IMPLEMENT.md`
7. `docs/DECISIONS.md`

The root-level product docs describe the legacy Next.js prototype and should not be treated as the source of truth for `intel_hub` unless the user explicitly asks to work on that prototype.

When shipping `intel_hub` changes, update `docs/IMPLEMENT.md` progress notes instead of the legacy root `IMPLEMENT.md`.

UI display copy should default to business-friendly Simplified Chinese unless explicitly requested otherwise.
Do not revert existing Chinese UI labels back to English.
Prefer existing naming conventions already used in navigation, pages, cards, and status labels.
Current priority: improve the Project Object Page and related page links to support walkthrough-based validation of the lifecycle story, human/brain/agent/execution collaboration, and review-to-asset closure. Avoid broad feature expansion unless explicitly requested.

Before making any changes, read these files in the repo root:

1. `README_PRODUCT.md`
2. `ARCHITECTURE.md`
3. `IA_AND_PAGES.md`
4. `DATA_MODEL.md`
5. `PLAN.md`
6. `IMPLEMENT.md`
7. `DECISIONS.md`
8. `Guidelines.md`（界面字体、颜色、卡片与按钮层级；与 `src/app/globals.css` 令牌一致）

Treat them as the product and implementation source of truth.
Do not invent a parallel folder structure. Follow the documented src/ layout unless the docs are explicitly changed first.

---

## Product Context

This repo is for an **AI-native lifecycle-driven commerce operating system**.

It is:

- **lifecycle-driven**
- **project-object-centered**
- **pulse-driven**
- **exception-first**
- **human-in-the-loop**
- **agent-orchestrated**
- **review-to-asset-loop**

It is **not**:

- a generic BI dashboard
- a generic task manager
- a generic chat assistant shell
- a collection of unrelated feature pages

The system is built around:

- lifecycle stages
- project objects
- management frontends
- decision objects
- action lifecycle
- governance
- review and asset capture

Management users are:

- CEO
- Product R&D Director
- Growth Director
- Visual Director

Execution is delegated to agents and runtime layers, so the frontend must focus on:

- command
- orchestration
- governance
- review
- reusable operating assets

---

## Core Product Rules

### 1. Lifecycle is the primary structure
Main lifecycle stages:

- `opportunity_pool`
- `new_product_incubation`
- `launch_validation`
- `growth_optimization`
- `legacy_upgrade`
- `review_capture`

Do not replace lifecycle structure with department-based or module-based navigation.

### 2. Project Object is the collaboration center
All meaningful work should connect back to a `ProjectObject`.

Do not create page-local concepts that bypass the project object model unless absolutely necessary.

### 3. Role is a view, not a separate product
CEO, Product R&D Director, Growth Director, and Visual Director should share the same underlying object model.

Role-specific experiences should differ by:

- default summaries
- priorities
- page emphasis
- ViewModels

Not by creating separate disconnected systems.

### 4. Distinguish four operating layers clearly
The product should always preserve the distinction between:

- human decisions
- decision brain recommendations
- scenario agent progress
- automation execution results

Do not collapse these into one generic status.

### 5. Exception-first management UI
Management pages should emphasize:

- pulse
- risks
- blockers
- pending approvals
- live health
- exceptions
- agent state

Do not overload management pages with low-value execution detail.
UI display copy should default to business-friendly Simplified Chinese unless explicitly requested otherwise.
Prefer business-facing labels over technical jargon.

### 6. Review must lead to assets
Review is only useful if it improves the next cycle.

Review pages must support:

- lessons learned
- reusable strategy extraction
- asset candidates
- asset publishing

---

## Implementation Rules

### 1. Stay within milestone scope
Only implement the current milestone or explicitly requested scope.

Do not proactively expand into unrelated pages, flows, or refactors.

### 2. Prefer reusable typed components
Use:

- shared typed models
- shared cards
- shared panels
- reusable layouts

Avoid page-specific one-off structures when a shared component pattern is possible.

### 3. Keep domain models centralized
Canonical domain models belong under:

- `src/domain/types/*`

View-specific formatting belongs in:

- `src/domain/mappers/*`

Do not duplicate domain types across page folders.

### 4. Use ViewModels for page shaping
If a page needs custom formatting or grouping, create a ViewModel mapper instead of mutating canonical domain types.

### 5. Keep routing predictable
Expected route families include:

- `src/app/command-center/*`
- `src/app/lifecycle/*`
- `src/app/projects/*`
- `src/app/action-hub/*`
- `src/app/governance/*`
- `src/app/assets/*`

Do not invent parallel route systems unless requested.

### 6. Use mock data unless real integration is explicitly in scope
For prototype stages, prefer:

- typed mock seeds
- mock stores
- simulated real-time updates

Do not block implementation on real APIs unless explicitly asked.

### 7. Embedded AI, not floating generic chat
AI should appear through:

- pulse cards
- decision cards
- evidence panels
- confidence labels
- review suggestions
- asset capture suggestions

Do not default to a floating generic assistant UI.

### 8. Live operating state matters
Where relevant, pages should show:

- project health
- risk level
- blockers
- pending approvals
- agent state
- recent execution updates
- signal freshness

---

## Code Style Rules

### 1. Be conservative with changes
Keep diffs scoped and localized.

### 2. Do not rewrite unrelated files
If a file is unrelated to the current milestone, leave it alone unless necessary for build or consistency.

### 3. Prefer explicit, readable code
Use clear names and predictable structure over clever abstractions.

### 4. Keep the UI management-oriented
Cards and sections should support decision-making, not just data display.

### 5. Preserve naming consistency
Use the naming already established in docs and domain models:
- ProjectObject
- DecisionObject
- ActionItem
- AgentState
- ReviewSummary
- AssetCandidate
- PublishedAsset

Do not invent near-duplicate naming.

---

## Required Workflow for Every Task

For every implementation task:

1. Read `AGENTS.md` and the referenced docs first.
2. Confirm the current milestone or scope.
3. Inspect existing code before adding new structures.
4. Implement only the requested scope.
5. Reuse existing components and types where possible.
6. Run validation after changes.
7. Update `IMPLEMENT.md` progress notes.

---

## Validation Requirements

After making changes, run relevant validation.

At minimum, ensure:

- app builds successfully
- imports resolve
- routes render
- no dead links in the implemented area
- no obvious type mismatches
- reusable components are used where expected

If validation cannot be run, say so clearly and explain why.

---

## Documentation Update Rules

Update documentation when:

- a structural assumption changes
- a route plan changes
- a major component ownership changes
- a domain model changes
- a milestone is completed

At minimum, update:

- `IMPLEMENT.md`
- and, if needed, the source-of-truth doc that changed

---

## Product-to-Code Mapping Reminder

Use this as a guide:

- CEO Command Center → `src/app/command-center/*`, `src/components/dashboards/*`
- Lifecycle Overview → `src/app/lifecycle/page.tsx`, `src/components/lifecycle/*`
- Opportunity Pool → `src/app/lifecycle/opportunity-pool/*`
- New Product Incubation → `src/app/lifecycle/new-product-incubation/*`
- Launch Validation → `src/app/lifecycle/launch-validation/*`
- Growth Optimization → `src/app/lifecycle/growth-optimization/*`
- Legacy Upgrade → `src/app/lifecycle/legacy-upgrade/*`
- Project Object Page → `src/app/projects/[projectId]/*`, `src/components/project/*`
- Action Hub → `src/app/action-hub/*`, `src/components/governance/*`
- Governance Console → `src/app/governance/*`
- Review Capture → `src/app/lifecycle/review-capture/*`, `src/components/review/*`
- Asset Hub → `src/app/assets/*`

---

## If Something Is Ambiguous

If docs are ambiguous:

1. Prefer `README_PRODUCT.md` and `ARCHITECTURE.md` for product intent.
2. Prefer `DATA_MODEL.md` for object shape and naming.
3. Prefer `IA_AND_PAGES.md` for page purpose and scope.
4. Prefer `IMPLEMENT.md` for milestone boundaries.
5. Record any important assumption in `IMPLEMENT.md`.

Do not silently invent a conflicting product structure.

---

## Default Instruction for Current Phase

Unless explicitly told otherwise, optimize for:

- prototype quality
- architectural clarity
- strong object model alignment
- reusable UI structure
- clean milestone-by-milestone progress

Not for:

- polished production backend
- real integrations
- premature optimization
- feature sprawl
