# Instructions

以下用 `text` 标记的代码块是发给 AI coding 助手的可复制英文 prompt。**每一轮**开头都带同一组产品设计原则，请在实现与文案中一贯落实。

## 第一步

```text
Read README_PRODUCT.md, ARCHITECTURE.md, IA_AND_PAGES.md, DATA_MODEL.md, PLAN.md, IMPLEMENT.md, and DECISIONS.md first.

Non-negotiable product principles (every milestone—reflect in IA, components, routes, placeholders, mocks, and copy):
- lifecycle-driven
- project-object-centered
- pulse-driven
- exception-first
- human-in-the-loop
- agent-orchestrated
- live operating state
- review-to-asset loop

Follow IMPLEMENT.md Core Rules, Frontend Design Rules, and Code Rules. Scope strictly to Milestone 1 in PLAN.md only.

Left navigation labels, grouping, and routes must align with IA_AND_PAGES.md §1 Global Navigation and the lifecycle/core hub structure in §3 Core Pages. M1 delivers placeholder pages and shell only.

We are building an AI-native commerce operating system; the principles above are the design contract.
Management users are CEO, Product R&D Director, Growth Director, and Visual Director.
Execution is delegated to agents and runtime layers, so the frontend should focus on command, orchestration, governance, and review.

For M1, implement layout shell and navigation only; defer full in-page AI modules. When you add AI later, follow IMPLEMENT.md Frontend Design Rules (embed in-page; avoid a generic global chat dock).

Start with Milestone 1 only:
- scaffold the app shell
- implement left navigation based on lifecycle/core hubs per IA_AND_PAGES.md
- implement top role switcher
- create placeholder pages for all core routes
- use reusable typed components
- keep diffs scoped

After changes: complete the **Validation Checklist** in IMPLEMENT.md (app builds, main routes render, imports clean, no obvious dead links, shared components reused where expected, core typed schemas valid, update docs if assumptions changed); update **Progress Notes → Milestone 1** in IMPLEMENT.md.
```

## M2

```text
Read README_PRODUCT.md, ARCHITECTURE.md, IA_AND_PAGES.md, DATA_MODEL.md, PLAN.md, IMPLEMENT.md, and DECISIONS.md first.

Non-negotiable product principles (every milestone—reflect in IA, components, routes, placeholders, mocks, and copy):
- lifecycle-driven
- project-object-centered
- pulse-driven
- exception-first
- human-in-the-loop
- agent-orchestrated
- live operating state
- review-to-asset loop

Implement Milestone 2 only:
- lifecycle overview page
- typed Project Object schema integration
- project object detail page skeleton
- mock data store for project objects and lifecycle states

Keep implementation scoped and reusable.

After changes: complete the **Validation Checklist** in IMPLEMENT.md; update **Progress Notes → Milestone 2** in IMPLEMENT.md.
```

## M3

```text
Read README_PRODUCT.md, ARCHITECTURE.md, IA_AND_PAGES.md, DATA_MODEL.md, PLAN.md, IMPLEMENT.md, and DECISIONS.md first.

Non-negotiable product principles (every milestone—reflect in IA, components, routes, placeholders, mocks, and copy):
- lifecycle-driven
- project-object-centered
- pulse-driven
- exception-first
- human-in-the-loop
- agent-orchestrated
- live operating state
- review-to-asset loop

Implement Milestone 3 only:
- CEO Command Center

Use pulse cards, battle cards, resource cards, approval cards, and org/AI efficiency cards.
Do not implement unrelated director pages yet.

After changes: complete the **Validation Checklist** in IMPLEMENT.md; update **Progress Notes → Milestone 3** in IMPLEMENT.md.
```

## M4

```text
Read README_PRODUCT.md, ARCHITECTURE.md, IA_AND_PAGES.md, DATA_MODEL.md, PLAN.md, IMPLEMENT.md, and DECISIONS.md first.

Non-negotiable product principles (every milestone—reflect in IA, components, routes, placeholders, mocks, and copy):
- lifecycle-driven
- project-object-centered
- pulse-driven
- exception-first
- human-in-the-loop
- agent-orchestrated
- live operating state
- review-to-asset loop

Implement Milestone 4 only:
- Product R&D Director Desk
- Growth Director Desk
- Visual Director Desk

Reuse shared layout and card components.
Keep role views different in defaults, but based on the same project object model.

After changes: complete the **Validation Checklist** in IMPLEMENT.md; update **Progress Notes → Milestone 4** in IMPLEMENT.md.
```

## M5

```text
Read README_PRODUCT.md, ARCHITECTURE.md, IA_AND_PAGES.md, DATA_MODEL.md, PLAN.md, IMPLEMENT.md, and DECISIONS.md first.

Non-negotiable product principles (every milestone—reflect in IA, components, routes, placeholders, mocks, and copy):
- lifecycle-driven
- project-object-centered
- pulse-driven
- exception-first
- human-in-the-loop
- agent-orchestrated
- live operating state
- review-to-asset loop

Implement Milestone 5 only:
- Opportunity Pool
- New Product Incubation
- Launch Validation
- Growth Optimization
- Legacy Upgrade

Each page must embody the principles above: show lifecycle position, project-object context, pulse and exceptions, human decisions vs agent-orchestrated work, and live operating state; surface AI recommendations and agent state where relevant.

After changes: complete the **Validation Checklist** in IMPLEMENT.md; update **Progress Notes → Milestone 5** in IMPLEMENT.md.
```

## M6

```text
Read README_PRODUCT.md, ARCHITECTURE.md, IA_AND_PAGES.md, DATA_MODEL.md, PLAN.md, IMPLEMENT.md, and DECISIONS.md first.

Non-negotiable product principles (every milestone—reflect in IA, components, routes, placeholders, mocks, and copy):
- lifecycle-driven
- project-object-centered
- pulse-driven
- exception-first
- human-in-the-loop
- agent-orchestrated
- live operating state
- review-to-asset loop

Implement Milestone 6 only:
- Action Hub
- Governance Console

Make the UI exception-first and show agent-orchestrated execution clearly.
Clearly distinguish AI suggestions, pending approvals, agent progress, automation results, rollback history, and live operating state.

After changes: complete the **Validation Checklist** in IMPLEMENT.md; update **Progress Notes → Milestone 6** in IMPLEMENT.md.
```

## M7

```text
Read README_PRODUCT.md, ARCHITECTURE.md, IA_AND_PAGES.md, DATA_MODEL.md, PLAN.md, IMPLEMENT.md, and DECISIONS.md first.

Non-negotiable product principles (every milestone—reflect in IA, components, routes, placeholders, mocks, and copy):
- lifecycle-driven
- project-object-centered
- pulse-driven
- exception-first
- human-in-the-loop
- agent-orchestrated
- live operating state
- review-to-asset loop

Implement Milestone 7 only:
- Review to Asset Loop
- Asset Hub

This milestone is the primary home of the review-to-asset loop: support review summary, attribution, reusable strategy extraction, asset candidates, and published assets—still tied to project objects and lifecycle.

After changes: complete the **Validation Checklist** in IMPLEMENT.md; update **Progress Notes → Milestone 7** in IMPLEMENT.md.
```
