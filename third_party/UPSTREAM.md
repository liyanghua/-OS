# Third-Party Upstream Pins

This repository uses an adapter-first integration model. Business code only depends on local adapters under `apps/content_planning/adapters/`; upstream frameworks are vendored for reference, targeted extraction, and future runtime hardening.

## deer-flow

- Upstream: [bytedance/deer-flow](https://github.com/bytedance/deer-flow)
- Local path: `third_party/deer-flow`
- Current role:
  - workflow graph concepts
  - multi-agent orchestration patterns
  - planner/coordinator decomposition
- Integration boundary:
  - `DeerFlowAdapter`
  - `DiscussionOrchestrator`
  - `PlanGraph` / `graph_executor`

## hermes-agent

- Upstream: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- Local path: `third_party/hermes-agent`
- Current role:
  - memory recall / compression
  - skill extraction
  - lesson writeback
  - waiting-for-human state modeling
- Integration boundary:
  - `HermesAdapter`
  - `AgentMemory`
  - evaluation learning loop

## Upgrade policy

- Prefer pinning upstream commits instead of tracking moving branches.
- Keep upstream usage behind adapters; do not import third-party internals directly from product routes or services.
- If upstream APIs change, update adapters first and keep product-facing contracts stable.
