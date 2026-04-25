# 本体大脑情报中枢 V0.9 — AI-native 多角色协同交互架构

> V0.9 AI-native 协同架构升级：协同网关 + Lead Agent + SSE 实时流 + 多轮对话 + Plan Graph + Agent Memory + Skill Registry + 前端富交互。
> V0.3 核心升级：把小红书笔记从"内容样本"编译成"经营决策资产"。

## 机会卡 Agent 单条优先与按来源笔记分组（2026-04-25 续）

### 痛点

1. 默认 `max_notes=30` 一把跑完，VLM/LLM 串行调用耗时长，业务用户首屏看不到任何卡片就要等很久；想"先看 1 条预览，满意了再加跑"做不到。
2. 桌布、假发等类目下 `compile_xhs_opportunities` 会同笔记产出多张差异化卡（visual / selling / scene），但列表页 `{% for card in cards %}` 平铺，看不出"这几张其实是同一篇笔记的 3 个角度"，差异更看不出来。

### 关键改动

- `apps/intel_hub/services/opportunity_gen_agent.py`：
  - `__init__` 默认 `max_notes=1`；新增 `skip_note_ids: Iterable[str] = ()` 与 `note_id_filter: str | None = None`；
  - M1 在 `raw_dicts` 切片前先按 `note_id_filter` 命中或 `skip_note_ids` 排除，全部被排除时区分 `error_kind = "all_consumed"`（已跑完所有笔记）/ `"note_not_found"`（指定 note_id 未命中）/ `"no_source"`（类目本身无原始笔记）三种语义，前端可分别给出友好引导；
  - M5 在维持全局 `data/output/xhs_opportunities/opportunity_cards.json` 合并写的同时，额外把本次任务卡片快照写到 `data/output/xhs_opportunities/runs/{lens_id}_{task_id}.json`，方便审计单次任务产物。
- `apps/intel_hub/api/app.py`：
  - 模块级 `StartAgentRunRequest` 默认 `max_notes=1`，新增 `skip_note_ids: list[str] = []` / `note_id: str | None = None`，POST handler 透传到 Agent；
  - `xhs_opportunities` handler 新增 `note_groups`：用 `_get_notes()` 建 note_id → 元信息索引，按 `card.source_note_ids[0]` 分组并 join `title / cover_url / desc / source_keyword`，组内按 `confidence DESC`、组间按"组内最高 confidence DESC"排序；同时输出 `lens_notes_total` 给前端"再跑全部"动态显示上限。
- 模板：
  - `apps/intel_hub/api/templates/_xhs_opportunity_card.html`（新文件）：把单卡片 HTML 抽出来，左上加 angle chip = `TYPE_LABEL[opportunity_type]` + `· content_angle`（如「视觉钩子 · 撞色对比」），同组卡片差异一眼可辨；
  - `apps/intel_hub/api/templates/xhs_opportunities.html`：空态 CTA 改为「立即生成机会卡（先跑 1 条预览）」并显式 `max_notes: 1`；非空态在列表头插入 `lens-incremental-bar`（「Agent 已为本类目生成 X 张机会卡 · 再跑 5 条 / 再跑全部」）；列表渲染从 `{% for card in cards %}` 改为 `{% for group in note_groups %}` 的 `note-group` 容器，组头展示来源笔记缩略图 + 标题链接 + 「本笔记产出 N 张机会卡」徽标；
  - `apps/intel_hub/api/templates/_opportunity_agent_drawer.html`：
    - 内部累计 `state.processedNoteIds: Set<string>`（监听 `agent_run:item_progress` 抽 `note_id`），抽屉副标题显示「本类目共有 N 篇笔记可用 · 已处理 M 篇」；
    - `done` 态 CTA 改为「查看本批结果 / 再跑下一条 / 再跑 5 条 / 再跑全部（最多 30 条）」，全部沿用同一个 `OpportunityAgentRunner.start({lens_id, max_notes, skip_note_ids: [...processedNoteIds]})` 入口；
    - `failed` 态对 `all_consumed` / `note_not_found` 给独立标题与样式（不再误导成"去素材中心补料"）。
- 事件协议保持兼容：`agent_run:failed.error_kind` 扩展为 `"no_source" | "all_consumed" | "note_not_found" | "cancelled" | "unknown"`。

### 验证

- `pytest apps/intel_hub/tests/test_opportunity_gen_agent.py` 8/8 PASSED：
  - 新增 `test_default_max_notes_is_one` / `test_note_id_filter_picks_specified_note` / `test_skip_note_ids_excludes_processed` / `test_skip_all_emits_all_consumed` / `test_run_writes_task_scoped_snapshot`；
  - 老用例（无源、5 段事件序列、互斥）仍全绿。
- `pytest apps/intel_hub/tests/test_api.py::OpportunityAgentRunsTests` 8/8 PASSED：
  - `test_start_agent_run_default_max_notes_is_one` / `test_start_agent_run_passes_skip_note_ids_to_agent`：用 `_StubAgent` 拦截构造参数，断言默认 `max_notes=1` 且 `skip_note_ids` 透传到 Agent；
  - `test_xhs_opportunities_groups_cards_by_source_note`：通过临时 `mediacrawler_sources` jsonl 注入 mock 笔记，断言渲染包含 `note-group` 容器、「本笔记产出 2 张机会卡」徽标，以及 `opportunity_type` / `content_angle` 派生的 angle chip。
- 全量 `pytest apps/intel_hub/tests/test_api.py apps/intel_hub/tests/test_opportunity_gen_agent.py` 43/43 PASSED，无回归。

### 不做（明确边界）

- 不引入新 schema 字段（`differentiator` 等），差异展示完全依赖现有 `opportunity_type` + `content_angle`；
- 不改 `compile_xhs_opportunities` / `merge_opportunities` 的合卡策略，单笔记多卡仍由编译器决定；
- 不动 review-to-asset 评分链路；
- 增量补跑通过 `XHSReviewStore.sync_cards_from_json` 的 `INSERT OR REPLACE` 自然累加，不需要额外的"批次"概念。

---

## 机会卡生成 Agent 与可观测抽屉（2026-04-25）

### 痛点

`/xhs-opportunities?lens=wig` 等无机会卡的类目当前只展示「暂无机会卡数据。请先运行 `python -m apps.intel_hub.workflow.xhs_opportunity_pipeline`」这类纯技术提示。业务用户既看不懂这条命令，也无法在 UI 内自助触发；而流水线本身已具备从 jsonl → VLM/LLM 三维信号 → 类目透视五层引擎的能力，缺的只是一条「按类目一键启动 + 实时可观测」的入口。

### 关键改动

- 新增 `apps/intel_hub/services/agent_run_registry.py`：
  - `AgentRunSnapshot`：task_id / lens_id / status / 5 里程碑（探查与解析、信号提取、跨模态与映射、机会卡编译、透视聚合与入库）/ counters（笔记数、VLM/LLM 调用、机会卡数）/ recent_events / error；
  - `AgentRunRegistry` 进程内单例：同 `lens_id` 互斥（重复启动抛 `RuntimeError`），提供 `start / get / get_active_by_lens / request_cancel / mark_done / mark_failed / mark_cancelled / update_milestone / bump_counters / append_event`，`MAX_KEEP_TASKS=16` 自动淘汰已结束任务；
  - 取消采用「软信号」：Agent 在每个里程碑头部 `is_cancelled` 检查后早退，并 emit `agent_run:failed{error_kind:"cancelled"}`。
- 新增 `apps/intel_hub/services/opportunity_gen_agent.py`：
  - `OpportunityGenAgent.run()` 把 `xhs_opportunity_pipeline` 的内部步骤函数（`load_and_parse_notes` 内联、`extract_visual_signals` / `extract_selling_theme_signals` / `extract_scene_signals` / `validate_cross_modal_consistency` / `project_xhs_signals` / `compile_xhs_opportunities` / `apply_lens_bundles_to_cards` / `CategoryLensEngine.run`）切片成 5 段，每段切口 emit；
  - jsonl 默认目录为 `data/fixtures/mediacrawler_output/xhs/jsonl`，不存在再回退 `third_party/MediaCrawler/data/xhs/jsonl`；按 `lens_id` 路由筛选笔记，无命中即 emit `agent_run:failed{error_kind:"no_source", suggested_url:"/notes?lens=…"}`；
  - 持久化路径与 CLI 等价：写 `data/output/xhs_opportunities/opportunity_cards.json`（按 `opportunity_id` 与原文件 merge，避免覆盖其他 lens 的卡）+ `lens_bundles/{lens_id}.json`，再走 `XHSReviewStore.sync_cards_from_json`；
  - LLM/VLM 调用沿用 `apps/intel_hub/extraction/llm_client.py` 的 DashScope + 缺 KEY 自动降级路径，不引入新的 provider；
  - 仅 M2 信号提取保留 `asyncio.to_thread`（VLM/LLM 真正可能耗时），其余里程碑同步直跑 + `await asyncio.sleep(0)` 让出，避免 TestClient/portal 下 `to_thread` 调度延迟。
- API 层（`apps/intel_hub/api/app.py`）新增 4 条路由（紧邻 `/content-planning/stream/{opportunity_id}`）：
  - `POST /xhs-opportunities/agent-runs`：body `{lens_id, max_notes?}`，调 `agent_run_registry.start()` + `asyncio.create_task(agent.run())`，返回 `{task_id, lens_id, lens_label, status, stream_url}`；同 lens 已有 in-flight 任务时 409；
  - `GET /xhs-opportunities/agent-runs/{task_id}`：返回 `AgentRunSnapshot.to_dict()`，未知任务 404；
  - `GET /xhs-opportunities/agent-runs/{task_id}/stream`：复用 `apps.content_planning.gateway.sse_handler.sse_stream`，channel key = `f"agent_run:{task_id}"`，自动拿到最近 20 条 history 实现刷新页面续接；
  - `POST /xhs-opportunities/agent-runs/{task_id}/cancel`：触发软取消，未知任务 404。
  - `xhs_opportunities` handler 的渲染上下文新增 `lens_label / active_agent_task_id / empty_state_kind`（`global_empty` vs `lens_empty`）。
- 模板：
  - `apps/intel_hub/api/templates/xhs_opportunities.html` L240-243 旧空态文案重写为业务化 `empty-card`：徽标 + 标题 + 「视觉/卖点/场景三维 + 类目透视五层」简介 + 5 段流水线徽标 + 三个 CTA（「立即生成机会卡」/「先去素材中心补料 →」/「了解类目透视 →」），未选 lens 时按钮禁用并提示先选类目；模板末尾 `include "_opportunity_agent_drawer.html"`，并在有 `active_agent_task_id` 时通过 `OpportunityAgentRunner.attach({task_id})` 自动续接抽屉；
  - 新增 `apps/intel_hub/api/templates/_opportunity_agent_drawer.html`：以 `pw-drawer` 为范的右侧抽屉，含实时计数（笔记 / VLM / LLM / 机会卡）、5 段进度卡（spinner/check + 进度条）、暗色实时事件日志（最近 200 条）、完成绿卡 + 失败红卡（`no_source` 时一键跳 `/notes?lens=…`）；JS 暴露 `window.OpportunityAgentRunner = { start, attach, cancel, close }`，`EventSource` 异常 3s 重连，`agent_run:done` 后 1.5s 自动跳 `jump_url`。
- 事件协议（payload 至少包含 `task_id, lens_id`）：
  - `agent_run:started {lens_label, max_notes, milestones[]}`
  - `agent_run:stage_started {stage_id, label, total_items, milestone}`
  - `agent_run:item_progress {stage_id, note_id, note_title, ok, latency_ms?, used_vlm?, used_llm?, visual_count?, selling_count?, scene_count?, card_count?, consistency?}`
  - `agent_run:stage_completed {stage_id, summary}`
  - `agent_run:done {cards_total, lens_score, decision, jump_url}`
  - `agent_run:failed {error_kind: "no_source"|"cancelled"|"unknown", message, suggestion, suggested_url}`
- Stage 权重（仅用于前端进度可视化，不参与持久化）：M1 探查 10% / M2 信号提取 50% / M3 跨模态 10% / M4 机会卡编译 15% / M5 透视聚合与入库 15%。

### 验证

- `pytest apps/intel_hub/tests/test_opportunity_gen_agent.py` 3/3 PASSED：
  - 无源笔记时 emit `agent_run:failed{error_kind:"no_source", suggested_url:"/notes?lens=wig"}`；
  - 完整 5 段事件序列 + `opportunity_cards.json` 落地 + `sync_cards_from_json` 被调一次；
  - 同 lens 重复 `start()` 抛 `RuntimeError`，不同 lens 互不影响。
- `pytest apps/intel_hub/tests/test_api.py::OpportunityAgentRunsTests` 5/5 PASSED：
  - 空态页面包含「立即生成机会卡」「OpportunityAgentRunner」「/xhs-opportunities/agent-runs」，且不再含「请先运行 python -m …」；
  - `POST /xhs-opportunities/agent-runs` 正常启动且 lens=wig 时 8s 内进入 `failed{error_kind:"no_source"}`；
  - 同 lens 已占用时 409；未知 task_id 的 GET / cancel 均返回 404。
- 全量 `pytest apps/intel_hub/tests/test_api.py apps/intel_hub/tests/test_opportunity_gen_agent.py` 35/35 PASSED，无回归。

### 不做（明确边界）

- 不改 `xhs_opportunity_pipeline` 本体（仅在 Agent 中复用其内部步骤函数），CLI `python -m apps.intel_hub.workflow.xhs_opportunity_pipeline` 仍可独立运行；
- 不接 `FileJobQueue` 或 `collector_worker`：Agent 不主动触发采集，无源时引导用户去 `/notes?lens=…` 自助；
- 不做跨进程任务持久化：注册表是进程内单例，重启后历史任务清空（已结束的任务保留 16 条用于断线重连可看完）；
- 抽屉只 include 在 `xhs_opportunities.html`，不进 `base.html` 全局 fab，避免与 `crawl-observer-drawer` 争抢心智。

---

## 视觉工作台数据接力与参考图健壮性（2026-04-25）

### 痛点

1. 进入 `/planning/{id}/visual-builder` 时，fixture 来源笔记的 `cover_image`（如 `https://example.com/img1.jpg`）会被原样塞进多模态生图请求，触发 OpenRouter `400 Unable to extract dimensions from input image: 404 Not Found`。
2. 策划台已有 `titles / body / image_briefs / saved_prompts / quick_draft`，但视觉工作台首屏不带，右栏 Prompt Builder 空白，标题/正文要重新跑 quick-draft，体验割裂。

### 关键改动

- 新增 `apps/content_planning/utils/ref_image_filter.py`：`is_usable_ref_url` / `filter_usable_ref_urls`，统一识别 `example.com` / `mock-cdn.example.com` / 空串 / 非 http(s) 协议等不可用 URL。配套单测 `apps/content_planning/tests/test_ref_image_filter.py`（5 例）。
- 三个生图调用点接入过滤：
  - `apps/intel_hub/api/app.py::_persist_source_images`：cover/image_urls 在尝试下载前先过滤；过滤后无可用图时 `cover_image=""`、`image_urls=[]`，并打 `ref_quality:"unusable_fixture"`。
  - `apps/content_planning/api/routes.py::_build_rich_prompts`：构造 `ref_image_urls` 时统一 `filter_usable_ref_urls`；ref_image 模式但全被过滤时给 `gen_mode_effective="prompt_only"`。
  - `apps/content_planning/services/image_generator.py::_generate_openrouter_once`：再次校验 `prompt.ref_image_url`，本地路径与合法 http(s) 才走多模态分支，否则降级为 prompt_only。
- 视觉工作台首屏 ctx 大幅扩容（`apps/intel_hub/api/app.py::visual_builder_page`）：
  - 从 `ContentPlanStore` / session 拉取 `quick_draft / titles / body / image_briefs / saved_prompts / generated_images`；
  - 服务端预合成 `initial_prompts`（`saved_prompts` 优先、否则 `_build_rich_prompts(pre_mode)`）；
  - 计算 `ref_count / has_ref_images / gen_mode_effective`；
  - 以 `window.__VB_BOOTSTRAP__` 一次性注入模板，避免前端再 roundtrip。
  - 同步修复 `_persist_source_images` 与主路由对 `source_images` 的缓存读取（之前依赖 `get_session_data`，但其不返回 `source_images_json`，等于每次都重新生成）。
- `apps/intel_hub/api/templates/visual_builder.html`：
  - 顶栏增加「已接力策划台结果」徽标 + 参考图数量徽标；
  - bootstrap 直填预览画布与 Prompt 槽位，命中 `quick_draft` 时隐藏「一键生成」冷启动按钮；
  - `ref_count==0` 时自动选中 `prompt_only` 并禁用 `ref_image` 选项；
  - 来源图 `<img>` 加 `onerror` 自动隐藏失效缩略图，并显示「参考图无效，仅做文本参考」提示；
  - 右栏新增「上次已生成 N 张图」小卡，链接 `/content-planning/assets/{id}`；
  - `Prompt Builder` 标题加来源徽标（来自 saved_prompts / 自动合成）。
- `apps/intel_hub/api/templates/planning_workspace.html`：两处跳转 URL 加 `?from=planning`，按钮文案改为「进入视觉工作台（已接力策划结果）」/「视觉工作台会自动带入此处的标题/正文/参考图，无需重新生成」。

### 验证

- `pytest apps/content_planning/tests/test_ref_image_filter.py` 5/5 PASSED。
- `pytest apps/intel_hub/tests/test_api.py::VisualBuilderBootstrapTests` 3/3 PASSED：
  - `bootstrap` 关键字段齐全（`quick_draft / titles / body / image_briefs / saved_prompts / initial_prompts / ref_count / gen_mode_effective / latest_generated_images`）；
  - 注入 `example.com` cover → `ref_count=0`，`gen_mode_effective="prompt_only"`；
  - 注入合法 xhscdn cover → `ref_count>0`，`gen_mode_effective="ref_image"`。
- `pytest apps/intel_hub/tests apps/content_planning/tests`：仅 `test_mediacrawler_loader` / `test_source_router` 4 例（platform 命名 xiaohongshu→xhs）+ `test_image_generator` 6 例（外部网络/已存在的连通性问题）失败，均与本次改动无关，已 git stash 验证为预存在问题。

### 显式不做

- 不重写 `content_planning v6` 生图 API 的响应结构，仅追加 `gen_mode_effective` 字段。
- 不动 Growth Lab workspace 的画布/生图路径。
- 不引入新存储；`saved_prompts` / `generated_images` 继续走现有 `ContentPlanStore`。
- 若 `quick_draft` 缺失，仍保留「一键生成」按钮，不强制跳转。

---

## 主视角主线重组（2026-04-25）

### 本次目标

围绕用户主视角把页面 IA 收敛成"三主线 + 一个统一资产中枢"：
- 主线 1 内容生产：素材中心 → 类目透视 → 机会卡 → 策划台 → 视觉 → 资产
- 主线 2 增长实验室：雷达 → 编译 → 主图 → 前 3 秒 → 测试板 → 资产
- 主线 3 套图工作台：无限画布 + Agent → 资产
- 三条主线产物在 `/asset-workspace` 统一沉淀为 `SystemAsset`

### 关键实现

| 范围 | 文件 | 变更 |
|---|---|---|
| 文档 + 顶栏 | `docs/IA_AND_PAGES.md`、`apps/intel_hub/api/templates/base.html`、`apps/intel_hub/api/templates/dashboard.html` | IA 文档重写为三主线模型；顶栏改为「内容生产 ▾ / 增长实验室 ▾ / 套图工作台」+「系统资产 / 结果反馈」快速入口，激活态由 `pathname+search` 客户端 JS 自动设置；首页改为三张主线入口卡。 |
| 主线 1 联动 | `apps/intel_hub/api/app.py`、`apps/intel_hub/api/templates/notes.html`、`note_detail.html`、`xhs_opportunities.html`、`xhs_opportunity_detail.html` | `/notes` 新增 `lens` 查询参数（lens 全量从 `config_loader.load_category_lenses()` 加载），顶部"平台 + 类目透视" Tab；笔记详情加 lens 直达卡（含类目透视/机会卡/同 lens 笔记入口）；`/xhs-opportunities` 的 `type chip` 跟随 lens 动态变化（`lens_type_nav`），分页保留 `lens` 参数；机会详情促升后主 CTA 改为 `/planning/{id}`，brief/strategy/plan/assets/visual-builder 作为策划台内的二级入口保留。 |
| 主线 2 & 3 主线条 | `apps/growth_lab/templates/_lane_bar.html`（新增）、`apps/growth_lab/templates/{radar,compiler,main_image_lab,first3s_lab,board,asset_graph,workspace}.html` | 新增主线条 partial：lane 2 渲染线性步骤条（雷达→编译→主图→前 3 秒→测试板→资产）+「推送到系统资产」CTA；lane 3（workspace）独立标识 + 5 输出能力 chips；各页面通过 `{% set lane_step = "..." %}` + `{% include "_lane_bar.html" %}` 接入。 |
| 统一资产数据层 | `apps/intel_hub/domain/system_asset.py`（新增）、`apps/intel_hub/services/system_asset_service.py`（新增）、`data/runtime_data/system_assets.json`（按需创建） | 新增 `SystemAsset` Pydantic 模型（`asset_id / source_lane / source_ref / lens_id / asset_type / title / thumbnails / status / lineage / created_at`）；`SystemAssetService.list_assets(lane, lens, status, asset_type)` 聚合三处来源（content-planning `asset_bundle` / growth_lab `asset_performance_cards` / workspace `workspace_plans`）+ 显式 register 的 JSON 持久化；`register/remove` 写入 `data/runtime_data/system_assets.json`。 |
| 资产工作台改造 | `apps/intel_hub/api/app.py`（`GET /asset-workspace`、`GET /api/system-assets` 新增）、`apps/intel_hub/api/templates/asset_workspace_list.html` | `/asset-workspace` 改为 SystemAsset 统一视图：顶部 Tab（全部 / 图文笔记 / 增长实验 / 套图）+ 二级筛选（lens / status / asset_type）+ 卡片化展示（缩略图 + lane pill + status pill + lineage 跳链 + 主 CTA）；新增 `GET /api/system-assets` JSON API（同样支持 `lane / lens / status / asset_type` 过滤）。 |

### 验证结果

- TestClient 冒烟（六段主线）：`/`、`/notes`、`/notes?lens=tablecloth`、`/xhs-opportunities`、`/xhs-opportunities?lens=tablecloth`、`/asset-workspace`、`/asset-workspace?lane=content_note|growth_lab|workspace_bundle`、`/api/system-assets`、`/api/system-assets?lane=growth_lab` 均返回 200。
- `apps/intel_hub/tests/test_api.py`：21 项通过（同步修正一个 pre-existing 用例：`view_result_url` 期望值同步更新为 `/notes?platform=xhs&category=...`）。
- 与本次重组无关的预存失败：`test_mediacrawler_loader.py`/`test_source_router.py`（platform 命名约定 `xiaohongshu` vs `xhs`）、`test_image_generator.py`（外部 API 联调，沙箱无网络），均不属本次范围。
- `SystemAssetService.register/remove` 单跑通过：写入 `data/runtime_data/system_assets.json` 后列表可见，删除后回退。
- `ReadLints`：本次改动无新增 lints。

### 显式不做

- 未合并 `/planning/{id}/visual-builder` 与 `/growth-lab/workspace` 的底层实现（仍属 C 档），但二者在主线导航与资产写出层已被统一。
- 未重写 growth_lab 内部业务管线、未拆现有 `/content-planning/*` 分步页（保留作为策划台内二级入口）。

## 类目透视引擎 A-G 上线（2026-04-19）

### 本次目标

- 让机会卡的「从小红书笔记到机会卡」链路具备类目视角：借 VLM 从图片取洞察、以类目词库做文本统计，按 `docs/knowledge_base/Category.md` 的"五层机会卡模型"装配。
- 打通 `_business_signals` → `Signal` → `ontology_projector` 的视觉字段接力断层。
- UI 上在机会卡列表页与详情页直接读到五层结果，不只看打分。

### 关键实现（按 Phase A-G）

| 阶段 | 关键文件 | 变更 |
|---|---|---|
| A | `apps/intel_hub/domain/category_lens.py`、`config/category_lenses/*.yaml`、`apps/intel_hub/config_loader.py`、`apps/intel_hub/ingest/mediacrawler_loader.py`、`apps/intel_hub/api/app.py`、`apps/intel_hub/api/templates/category_lens*.html` | 新增 `CategoryLens` / `LensInsightBundle` 等 Pydantic 对象；`wig.yaml`、`tablecloth.yaml`、`_keyword_routing.yaml` 落地；loader 支持按关键词路由；`/category-lenses` 只读列表+详情页。 |
| B | `apps/intel_hub/schemas/signal.py`、`apps/intel_hub/normalize/normalizer.py`、`apps/intel_hub/projector/ontology_projector.py` | `Signal` 新增 `lens_id` + `business_signals`；normalizer 透传；projector 的 haystack 加入视觉/痛点/疑问字段以恢复视觉→本体映射。 |
| C | `apps/intel_hub/schemas/content_frame.py`、`apps/intel_hub/extractor/visual_analyzer.py`、`apps/intel_hub/workflow/refresh_pipeline.py` | BSF 新增 `visual_people_state/trust_signals/trust_risk_flags/content_formats/product_features/insight_notes`；`visual_analyzer` 按 `CategoryLens.visual_prompt_hints` 动态拼 prompt 并做采样；pipeline 默认开启视觉（`--disable-vision` 关闭）。 |
| D | `apps/intel_hub/extractor/signal_extractor.py`、`apps/intel_hub/extractor/comment_classifier.py`、`apps/intel_hub/analysis/lens_keyword_stats.py` | 文本抽取改为"lens 优先 + 桌布兜底"；新增 `body_content_pattern_signals / body_user_expression_hits / body_emotion_signals / comment_classification_counts / comment_trust_barrier_signals`；新增 TF-IDF 模块 `compute_lens_hot_keywords`。 |
| E | `apps/intel_hub/engine/category_lens_engine.py`、`apps/intel_hub/workflow/refresh_pipeline.py`、`apps/intel_hub/workflow/xhs_opportunity_pipeline.py` | 新增 `CategoryLensEngine` 聚合 Layer1-5 + EvidenceScore + RecommendedAction；两条主流水线都会按 `lens_id` 分组调用引擎，产物保存到 `storage/runtime_data/lens_bundles/` 或 `data/output/xhs_opportunities/lens_bundles/`。 |
| F | `apps/intel_hub/schemas/opportunity.py`、`apps/intel_hub/compiler/opportunity_compiler.py`、`apps/intel_hub/workflow/xhs_opportunity_pipeline.py` | `XHSOpportunityCard` 新增 `lens_id / lens_version / lens_layer1~5 / lens_evidence_score / lens_recommended_action`；新增 `apply_lens_bundle(s)_to_card`，把五层结果写回 Card 并按权重融合 `opportunity_strength_score`；叙事字段（hook/audience/scene 等）若空则用 bundle 回填。 |
| G | `apps/intel_hub/api/app.py`、`apps/intel_hub/api/templates/xhs_opportunities.html`、`apps/intel_hub/api/templates/xhs_opportunity_detail.html` | 机会卡列表页新增「类目透视摘要」区块 + `lens` 过滤条 + 卡片级 lens 标签；详情页新增独立"类目透视 / 五层模型"卡片：五维分数 + Layer1 内容信号 + Layer2 本体收敛 + Layer3 用户任务 + Layer4 商品映射 + Layer5 内容执行。 |

### 验证结果

- `python -m apps.intel_hub.workflow.xhs_opportunity_pipeline --jsonl-dir data/fixtures/mediacrawler_output/xhs/jsonl`：5 篇笔记 → 10 张 card → 1 个 lens bundle（`tablecloth`，分 7.23，决策「进入测试」）；所有 card.lens_id 正确填充，`lens_layer*_*` 非空。
- `data/output/xhs_opportunities/lens_bundles/tablecloth.json`：五层结构完整，`layer1_signals.hot_keywords` / `layer3_user_jobs` / `layer5_content_execution` 均有数据。
- TestClient 烟测：`GET /xhs-opportunities`（HTML）含"类目透视摘要"、`lens` 过滤条、Card 级 lens 标签；`GET /xhs-opportunities/{id}`（HTML）含"类目透视 — {lens_id}"、第 1/3/5 层区块、五维分数与钩子文本。
- `ReadLints`：本次改动无新增 lints。
- 环境依赖缺口：DashScope VLM/LLM 需要代理才能调通；`visual_analyzer.analyze_note_images` 已实现 graceful degradation（仅告警，不中断 pipeline）。

## Intel Hub 抖音接入 + 平台隔离（2026-04-24）

### 本次目标

- 在现有采集链路中接入抖音（dy）关键词抓取。
- 小红书与抖音采集数据按平台强隔离（状态、进度、查询与分类统计）。
- 素材详情支持抖音视频播放/下载入口。

### 关键实现

| 文件 | 变更 |
|---|---|
| `apps/intel_hub/api/app.py` | 新增平台归一化与状态文件分流（`crawl_status_xhs.json` / `crawl_status_dy.json`）；`/crawl-status`、`/crawl-jobs/{id}/progress` 按任务平台读取；`/notes` 新增 `platform` 过滤并限定分类统计在当前平台；任务结果链接增加平台参数。 |
| `apps/intel_hub/workflow/collector_worker.py` | 执行平台优先取 `job.platform`；每个任务写入对应平台状态文件，避免跨平台串进度。 |
| `apps/intel_hub/ingest/mediacrawler_loader.py` | 扩展 dy 字段兼容：`aweme_id`、`aweme_url`、`video_download_url`、`cover_url`、`digg_count/create_time`；统一映射到 notes 可消费结构并保留平台标识。 |
| `apps/intel_hub/api/templates/notes.html` | 采集入口增加平台选择（小红书/抖音）；列表查询与分类导航按平台隔离；分页与搜索参数全链路带 `platform`。 |
| `apps/intel_hub/api/templates/note_detail.html` | 新增短视频展示块（`video_url`）及下载链接。 |
| `config/runtime.yaml` | 新增抖音数据源：`third_party/MediaCrawler/data/douyin/jsonl`。 |
| `third_party/MediaCrawler/run_queue_worker.py` | 批处理脚本对齐平台来源（`first.platform` 优先）并按平台拆状态文件。 |

### 验证结果

- `python -m compileall`：上述 Python 改动文件编译通过。
- `ReadLints`：改动文件无新增 lints。
- TestClient 烟测通过：
  - `POST /crawl-jobs`（`platform=dy`）可入队且 payload/Job 记录平台一致。
  - `GET /crawl-jobs/{id}/progress` 返回平台字段及平台化结果链接。
- `GET /notes?platform=xhs|dy` 可按平台独立返回数据和分类统计。

## Intel Hub 复用旧版小红书成功采集路线（2026-04-24）

### 本次目标

- 保留当前 `POST /crawl-jobs` 入队、应用内单 worker 串行消费、`/crawl-observer` 与右侧观察窗。
- 仅回退 `keyword_search` 的真实执行入口，复用此前已验证成功的 MediaCrawler 原生小红书抓取路线。

### 关键实现

| 文件 | 变更 |
|---|---|
| `apps/intel_hub/workflow/crawl_runner.py` | 重构为纯命令构造/子进程启动薄层，不再在主应用进程 import MediaCrawler；统一构造 legacy 命令。 |
| `apps/intel_hub/workflow/collector_worker.py` | `execute_keyword_search()` 改为调用 legacy runner 子进程；继续保留 session、heartbeat、失败告警、批次 `pipeline_refresh` 逻辑。 |
| `third_party/MediaCrawler/legacy_intel_hub_runner.py` | 新增 MediaCrawler 侧薄 runner，在 MediaCrawler 自己目录与 `.venv` 内设置 `config`、注入 `CrawlStatusReporter`、调用 `main.py` 语义。 |
| `third_party/MediaCrawler/run_with_status.py` | 降级为兼容壳，统一转发到 `legacy_intel_hub_runner.py`，不再承载主执行逻辑。 |
| `apps/intel_hub/tests/test_api.py` | 新增 legacy 执行入口测试，断言使用 `third_party/MediaCrawler/.venv/bin/python`、`third_party/MediaCrawler/legacy_intel_hub_runner.py`、固定 `cwd=third_party/MediaCrawler`，并覆盖平台状态文件路径。 |

### 当前边界

- 右侧观察窗、`/notes`、`/dashboard` 继续消费同一个 `/crawl-observer`，本轮不改 UI 状态口径。
- 多任务仍按 FIFO 串行执行，整批 crawl 完成后只触发一次 `pipeline_refresh`。
- 本轮不重写 MediaCrawler 的 selector 或 `DataFetchError` 逻辑，只把执行层恢复到之前成功的运行边界。

### 验证

- `python -m unittest apps.intel_hub.tests.test_api.ApiSurfaceTests.test_process_one_job_uses_custom_status_and_alert_paths apps.intel_hub.tests.test_api.ApiSurfaceTests.test_crawl_runner_builds_legacy_main_semantics_command apps.intel_hub.tests.test_api.ApiSurfaceTests.test_execute_keyword_search_uses_legacy_mediacrawler_main_runner -v`
- `.venv/bin/python -m unittest apps.intel_hub.tests.test_api.ApiSurfaceTests.test_embedded_worker_auto_consumes_and_enqueues_single_pipeline_refresh apps.intel_hub.tests.test_api.ApiSurfaceTests.test_crawl_observer_returns_batch_queue_summary apps.intel_hub.tests.test_api.ApiSurfaceTests.test_create_crawl_job_reuses_open_batch_group_id -v`
- 上述测试均通过；API 组测试存在既有 sqlite `ResourceWarning`，但未影响结果。

## 发布超时修复 + AI 发布内容生成升级 (2026-04-17)

### Bug 修复

- 前端 `startPublishPolling()` 增加 `errCount` 计数器：连续 10 次非 200 响应自动终止轮询并显示友好提示（"发布状态丢失，请检查创作者后台"），替代之前的静默丢弃行为
- `maxMs` 从 180s 提升到 300s，适配网络慢时发布流程耗时
- 根因：uvicorn StatReload 导致内存中 `_publish_jobs` 丢失，前端轮询收到 404 后静默跳过直到超时

### AI 发布内容生成

| 文件 | 改动 |
|---|---|
| `apps/growth_lab/services/publish_content_compiler.py` | **新增** — LLM 驱动的小红书发布内容编译器，基于卖点规格+钩子脚本+专家批注生成标题/正文/话题 |
| `apps/growth_lab/api/routes.py` | `/publish-preview` 端点优先调用 `PublishContentCompiler.compile()`，LLM 失败时 fallback 到原 `build_publish_content()` 规则拼接；新增 `regenerate` 参数支持前端 AI 重写 |
| `apps/growth_lab/templates/first3s_lab.html` | 发布弹窗新增 "AI 重写" 按钮 + AI 生成状态提示；支持多次 LLM 重新生成 + 手动编辑 |

### 设计决策

- `build_publish_content()` 保留为 fallback，LLM 不可用时自动降级
- 不做 job 持久化到 DB（前端防御已足够）
- 不做发布内容多版本管理（当前阶段不需要）

---

## 热点驱动裂变系统 growth_lab (2026-04-16)

### 概述

新建 `apps/growth_lab/` 模块，实现「热点驱动主图/前3秒裂变与测款放大系统」。
产品主链：TrendSignal → Opportunity → SellingPointSpec → VariantSpec → TestTask → ResultSnapshot → AmplificationPlan → AssetGraph。
与原 content_planning（Expert 模式）并存，路由前缀 `/growth-lab/*`。

### 新增模块结构

| 目录 | 说明 |
|---|---|
| `apps/growth_lab/schemas/` | 6 个 schema 文件：TrendOpportunity, SellingPointSpec, MainImageVariant, First3sVariant, TestTask, AssetPerformance |
| `apps/growth_lab/services/` | 7 个 service：SellingPointCompiler, MainImageVariantCompiler, VariantBatchQueue, First3sVariantCompiler, AmplificationPlanner, VideoProcessor, AssetGraphService |
| `apps/growth_lab/adapters/` | 2 个 adapter：opportunity_adapter (XHS→TrendOpp 映射), invokeai_provider (InvokeAI 本地推理骨架+mock) |
| `apps/growth_lab/storage/` | GrowthLabStore (SQLite, 9 张表, 自迁移) |
| `apps/growth_lab/api/routes.py` | 36 个路由 (6 页面 + 30 API) |
| `apps/growth_lab/templates/` | 6 个 HTML 页面：radar, compiler, main_image_lab, first3s_lab, board, asset_graph |

### 新增 Schemas (10 个核心对象)

| 对象 | 文件 | 说明 |
|---|---|---|
| `TrendOpportunity` | `schemas/trend_opportunity.py` | 统一机会对象，含 freshness/relevance/actionability 三维评分 |
| `SellingPointSpec` | `schemas/selling_point_spec.py` | 结构化卖点+多平台表达(PlatformExpressionSpec) |
| `MainImageVariant` | `schemas/main_image_variant.py` | 主图裂变版本，含 VariantVariable + ImageVariantSpec |
| `VariantVariable` | `schemas/main_image_variant.py` | 9 维裂变变量（模特/构图/场景/字卡/色彩/风格...） |
| `First3sVariant` | `schemas/first3s_variant.py` | 前3秒裂变版本，含 HookPattern + HookScript + ClipAssemblyPlan |
| `TestTask` | `schemas/test_task.py` | 测试任务管理单元 |
| `ResultSnapshot` | `schemas/test_task.py` | 结果快照（CTR/流量/转化率/退款率） |
| `AmplificationPlan` | `schemas/test_task.py` | 放大计划（放大/再裂变/换方向） |
| `AssetPerformanceCard` | `schemas/asset_performance.py` | 带业绩绑定的资产卡 |
| `PatternTemplate` | `schemas/asset_performance.py` | 可复用模式模板 |

### 新增 API (36 路由)

| 前缀 | 端点数 | 核心功能 |
|---|---|---|
| `/growth-lab/radar` | 6 | 机会列表/详情/创建/收藏/晋升/intel_hub同步 |
| `/growth-lab/compiler` | 4 | 卖点列表/详情/创建/LLM编译 |
| `/growth-lab/lab` | 5 | 主图变体CRUD + 批量生成 + 批次状态 |
| `/growth-lab/first3s` | 3 | 前3秒变体列表/详情/钩子生成 |
| `/growth-lab/board` | 5 | 测试任务CRUD + 结果录入 + 放大建议 |
| `/growth-lab/assets` | 7 | 资产卡/模板列表 + 高表现沉淀 + 模式提取 + 推荐 + 视频处理 |
| `/growth-lab/loop` | 1 | 资产→Radar反馈闭环 |
| 页面路由 | 6 | radar/compiler/lab/first3s/board/asset_graph |

### 关键设计决策

| 编号 | 决策 |
|---|---|
| D-030 | 新链路命名空间 `/growth-lab/*`，与 `/content-planning/*` 并存 |
| D-031 | 新模块 `apps/growth_lab/`，独立 schemas/services/routes |
| D-032 | 存储继续 SQLite, `data/growth_lab.sqlite` |
| D-033 | 批量生成队列 VariantBatchQueue (ThreadPoolExecutor + 内存状态) |
| D-034 | InvokeAI adapter 模式，不 fork 源码，通过 REST API 调用 |
| D-035 | 视频处理 Phase 3 引入 ffmpeg + whisper，优雅降级 |
| D-036 | 前端继续 Jinja2 + 原生 JS/CSS |
| D-037 | TrendOpportunity 与 XHSOpportunityCard 通过 adapter 映射，不改原对象 |

### 改动的文件

| 文件 | 改动 |
|---|---|
| `apps/intel_hub/api/app.py` | 挂载 growth_lab_router |

---

## 生图提示词可观测性 + 质量升级 (2026-04-12)

### 概述

解决生图提示词不可观测、质量低两个核心问题：新增 Prompt Inspector 面板（查看/编辑最终 prompt + 参考图 + 来源追溯），重构提示词融合管线从策划全链路（Brief + Strategy + Plan + ImageBrief + Template）萃取高价值信息构建富 prompt，新增生成历史面板支持多轮对比。

### 新增文件

| 文件 | 说明 |
|---|---|
| `apps/content_planning/services/prompt_composer.py` | PromptComposer 融合层：按 6 层优先级（ImageBrief → Plan → Strategy → Brief → Draft → Template）从策划全链路数据构建结构化富 prompt，支持来源追溯和渐进降级 |

### 新增模型

| 模型 | 文件 | 说明 |
|---|---|---|
| `PromptSource` | `image_generator.py` | 追溯单条 prompt 片段的来源（field 路径 + 内容 + 优先级） |
| `RichImagePrompt` | `image_generator.py` | 融合后的结构化 prompt（正向/负向/风格标签/来源分解/参考图），含 `to_image_prompt()` 转换 |

### 新增 API

| 端点 | 方法 | 说明 |
|---|---|---|
| `/v6/image-gen/{id}/preview-prompts` | POST | 预览融合后的 prompt（不触发生图），供 Prompt Inspector 展示 |
| `/v6/image-gen/{id}/history` | GET | 返回完整生成历史（每轮含 prompt_log + results + provider + gen_mode） |

### 改造的端点

| 端点 | 改动 |
|---|---|
| `POST /v6/image-gen/{id}` | 改用 `_build_rich_prompts` → `compose_image_prompts` 融合管线；支持 `edited_prompts` 覆盖；生成记录追加到历史（带 timestamp） |
| `GET /v6/image-gen/{id}/status` | 兼容新历史格式（带 timestamp 的多轮记录）和旧格式（slot_id 直接列表） |

### 前端

- **Prompt Inspector 弹窗**：点击"生成配图"→先弹出 Inspector→每个 slot 卡片含：参考图缩略图、可编辑 prompt textarea、negative prompt、来源标签（颜色编码）、风格标签、可展开来源详情→确认后携带编辑结果发送
- **生成历史面板**：可折叠的历史轮次列表，每轮显示时间戳、provider/mode/编辑标记、成功率、结果缩略图（可点击切换预览）、可展开 prompt 详情

### 融合优先级

1. `image_briefs` (ImageSlotBrief) — subject/composition/props/color_mood/avoid_items
2. `plan.image_plan` (ImageSlotPlan) — visual_brief/must_include/avoid_elements
3. `strategy` (RewriteStrategy) — image_strategy/positioning_statement/scene_emphasis/avoid_elements
4. `brief` (OpportunityBrief) — cover_direction/visual_direction/visual_style_direction/avoid_directions
5. `draft` (quick_draft) — cover_image_prompt
6. `match_result` — template_name（风格锚点）

---

## 笔记预览修复 + AI 图片生成 (2026-04-12)

### 概述

修复笔记预览生成 BUG（异常黑洞 + 前端静默失败），新增 DashScope 通义万相文生图能力，支持从策划工作台一键生成配图并通过 SSE 推送实时进度。

### BUG 修复

| 问题 | 修复 |
|---|---|
| `_handle_flow_error` 不捕获 Pydantic ValidationError，导致 500 | 增加通用 Exception 兜底 + 显式捕获 ValidationError 返回 400 |
| 前端 fetch 失败时静默吞掉错误 | 解析 error.detail 展示红色 toast |
| LLM 降级无感知 | draft 增加 `mode` 字段（llm / rule_fallback），前端显示降级提示 |

### 新增文件（1 个）

| 文件 | 说明 |
|---|---|
| `apps/content_planning/services/image_generator.py` | DashScope 通义万相文生图服务：async_call + 轮询 + 文件保存 + 批量生成 + 进度回调 |

### 修改文件（6 个）

| 文件 | 改动 |
|---|---|
| `apps/content_planning/api/routes.py` | `_handle_flow_error` 增加通用异常兜底；`v6_quick_draft` 增加 ValidationError 捕获；新增 `POST /v6/image-gen/{id}` + `GET /v6/image-gen/{id}/status` 端点 |
| `apps/content_planning/services/quick_draft_generator.py` | generate() 和 _rule_fallback() 返回 dict 增加 `mode` 字段 |
| `apps/content_planning/storage/plan_store.py` | 新增 `generated_images_json` 列映射、JSON 反序列化、ALTER TABLE 迁移 |
| `apps/intel_hub/api/app.py` | 挂载 `data/generated_images/` 为 `/generated-images/` 静态目录 |
| `apps/intel_hub/api/templates/_preview_canvas.html` | 升级支持真实图片（cover_image/content_image）、加载动画、updateImage/setImageLoading API |
| `apps/intel_hub/api/templates/planning_workspace.html` | 增加"生成配图"按钮 + SSE 监听 image_gen_progress/image_gen_complete 事件 + 错误 toast |

### 图片生成架构

- 引擎：DashScope 通义万相 `wanx2.1-t2i-turbo`（fallback `wanx-v1`）+ OpenRouter/Gemini Nano
- 进度推送：复用 EventBus + SSE，前端 EventSource 监听 image_gen_progress 事件
- 存储：`data/generated_images/{opportunity_id}/` + FastAPI StaticFiles 挂载
- 持久化：planning_sessions.generated_images_json + quick_draft.images 关联

### 双模式生图 (2026-04-12)

| 模式 | 参数值 | 说明 |
|---|---|---|
| 参考图+提示词 | `gen_mode=ref_image` | 从原始笔记 `note_context.cover_image` / `image_urls` 取参考图，结合 brief 提示词生成新图。DashScope 使用 `wanx2.1-imageedit` + `stylization_all`；OpenRouter/Gemini 使用多模态 `image_url` + text 输入 |
| 纯提示词 | `gen_mode=prompt_only` | 仅使用 brief 提取的文字描述直接生成（默认行为） |

改动文件：
- `image_generator.py`：`ImagePrompt` 新增 `ref_image_url` 字段；`_generate_openrouter()` 支持多模态输入（图+文）；`_generate_dashscope()` 有参考图时切 `wanx2.1-imageedit`
- `routes.py`：`POST /v6/image-gen/{id}` 接受 `gen_mode` 参数；参考图模式自动从 `IntelHubAdapter.get_source_notes()` → `note_context.cover_image` 获取原图 URL
- `planning_workspace.html`：新增模式选择下拉 `#sel-gen-mode`（参考图+提示词 / 纯提示词），状态提示含参考图数量

---

## V6 小红书内容生产链重构 (2026-04-11)

### 概述

在现有模型基础上新增 ExpertScorecard（8 维专家评分）+ NoteToCardFlow（上游编排），串联完整的 RawNote → Card(enriched) → Scorecard → Brief 生产链路。每阶段具备门控评估，确保 production-ready 效果。

### 新增文件（5 个）

| 文件 | 说明 |
|---|---|
| `apps/content_planning/schemas/expert_scorecard.py` | ExpertScorecard + ScorecardDimension 模型，8 维评分 + 加权汇总 + recommendation 映射 |
| `apps/content_planning/services/expert_scorer.py` | ExpertScorer 服务，对机会卡进行 8 维规则评分 |
| `apps/content_planning/services/note_to_card_flow.py` | NoteToCardFlow 上游编排：ingest eval → enrich card → score → scorecard eval |
| `config/scorecard_weights.yaml` | 评分维度权重 + recommendation 阈值 + confidence 组件配置 |
| `apps/intel_hub/api/templates/_scorecard_panel.html` | 前端 ExpertScorecard 面板：雷达图 + 维度条 + 证据详情 + 优化建议 |

### 修改文件（7 个）

| 文件 | 改动 |
|---|---|
| `apps/intel_hub/schemas/opportunity.py` | XHSOpportunityCard 新增 V6 语义字段组（audience/scene/pain_point/hook/selling_points 等 13 个字段） |
| `apps/content_planning/schemas/opportunity_brief.py` | OpportunityBrief 新增 V6 production-ready 字段（title_directions/cta/visual_direction 等 15 个字段） |
| `apps/content_planning/schemas/evaluation.py` | StageEvaluation.stage Literal 扩展为包含 ingest/scorecard |
| `apps/content_planning/evaluation/stage_evaluator.py` | 新增 IngestEvaluator + ScorecardEvaluator；CardEvaluator 扩展 3 维度；BriefEvaluator 扩展 3 维度 |
| `apps/content_planning/services/brief_compiler.py` | compile() 支持 scorecard 参数，新增 _apply_scorecard 方法 |
| `apps/content_planning/storage/plan_store.py` | 新增 expert_scorecards 表 + save_scorecard/load_scorecard/load_scorecards_by_opportunity |
| `apps/content_planning/api/routes.py` | 新增 7 个 V6 端点（ingest-eval/enrich-card/score/scorecard/compile-brief/run-pipeline/pipeline-status） |

### 前端集成

| 文件 | 改动 |
|---|---|
| `apps/intel_hub/api/templates/opportunity_workspace.html` | 嵌入 _scorecard_panel + JS 初始化加载/生成评分卡 |
| `apps/intel_hub/api/templates/planning_workspace.html` | Brief 编辑表单新增 V6 字段组 + V6 pipeline status 面板 + 一键全链路按钮 |

### V6 API 端点

| 方法 | 路由 | 说明 |
|---|---|---|
| POST | `/content-planning/v6/ingest-eval/{id}` | 原始笔记数据完整度评估 |
| POST | `/content-planning/v6/enrich-card/{id}` | V6 语义字段增强机会卡 |
| POST | `/content-planning/v6/score/{id}` | 生成 ExpertScorecard |
| GET | `/content-planning/v6/scorecard/{id}` | 获取 ExpertScorecard |
| POST | `/content-planning/v6/compile-brief/{id}` | 基于 scorecard 编译 brief |
| POST | `/content-planning/v6/run-pipeline/{id}` | 一键全链路 |
| GET | `/content-planning/v6/pipeline-status/{id}` | 链路状态 |

---

## Council 多角色 SOUL 与圆桌协议 (2026-04-11)

- **SOUL**：`apps/content_planning/agents/souls/{role}/SOUL.md`，`SoulLoader` + Hermes 风格 `soul_context_hermes`（扫描/截断）。
- **运行**：`CouncilAgentRunner` 将 SOUL、按角色记忆块、`prior_statements` 注入单次专家回合；`DiscussionOrchestrator`：`fast` = Round1 + 综合，`deep` = Round1 并行 + Round2 互见 + `lead_synthesizer` SOUL 综合。
- **记忆**：各角色独立写入 `council_opinion`；`council_memory_block` 与机会维度检索辅助 Council 上下文。
- **API/UI**：`CouncilParticipantSpec.soul_tagline`（`routes._run_stage_discussion` 注入）；`planning_workspace.html` 委员会抽屉使用 `discussion.messages`，分「第一轮」「第二轮（补充/反驳）」并展示参与者一句定位。

---

## Agent 一键策划全链路升级 (2026-04-10)

### 概述

将分步手动策划流程升级为 Agent 驱动的一键全链路模式。用户触发后，GraphExecutor 自动编排 7 个 Agent 节点（趋势分析 → Brief → 模板匹配 → 策略 → 计划编译 → 视觉规划 → 资产组装），通过 SSE 实时推送进度，最终产出 product-ready 资产包。

### 新增文件

| 文件 | 说明 |
|---|---|
| `apps/content_planning/services/agent_pipeline_runner.py` | AgentPipelineRunner 编排器核心，桥接 GraphExecutor + Flow Session + EventBus |
| `apps/content_planning/agents/plan_compiler.py` | PlanCompilerAgent：在策略和视觉之间编译 NewNotePlan |
| `apps/intel_hub/api/templates/_agent_pipeline_panel.html` | 前端一键触发 + SSE 实时节点进度面板 |

### 修改文件

| 文件 | 改动 |
|---|---|
| `apps/content_planning/agents/graph_executor.py` | execute/\_run\_node 增加 on\_node\_start/complete/fail 回调；\_propagate\_output 补全 trend\_analyst/plan\_compiler/template 自动选择 |
| `apps/content_planning/agents/plan_graph.py` | 新增 `build_agent_pipeline_graph`（7 节点，含 plan\_compiler） |
| `apps/content_planning/api/routes.py` | 新增 POST trigger / GET status / POST cancel / batch 端点 |
| `apps/intel_hub/api/app.py` | xhs\_opportunity\_detail 传递 is\_promoted + opportunity\_id |
| `apps/intel_hub/api/templates/xhs_opportunity_detail.html` | 嵌入 \_agent\_pipeline\_panel |
| `apps/intel_hub/api/templates/content_brief.html` | 嵌入 \_agent\_pipeline\_panel |
| `apps/intel_hub/api/templates/content_strategy.html` | 嵌入 \_agent\_pipeline\_panel |
| `apps/intel_hub/api/templates/content_plan.html` | 嵌入 \_agent\_pipeline\_panel |
| `apps/intel_hub/api/templates/content_assets.html` | 嵌入 \_agent\_pipeline\_panel |
| `apps/intel_hub/api/templates/xhs_opportunities.html` | 「一键策划」按钮改为 Agent 管线触发；批量操作栏增加「批量 Agent 策划」 |

### API 端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/content-planning/{opp_id}/agent-pipeline` | POST | 触发 Agent 全链路，立即返回 run\_id |
| `/content-planning/{opp_id}/agent-pipeline/status` | GET | 查询管线 + 各节点状态 |
| `/content-planning/{opp_id}/agent-pipeline/cancel` | POST | 取消执行中管线 |
| `/content-planning/batch-agent-pipeline` | POST | 批量触发 |
| `/content-planning/batch-agent-pipeline/status` | POST | 批量状态查询 |

### SSE 事件类型

`agent_pipeline_started`、`agent_node_started`、`agent_node_completed`、`agent_node_failed`、`agent_pipeline_completed`、`agent_pipeline_failed`、`agent_pipeline_cancelled`

### 架构决策

- GraphExecutor 增强而非替代：回调钩子 + 传播映射扩展
- 7 节点管线（新增 plan\_compiler）确保 visual\_director 获取 context.plan
- template\_planner 传播时自动从匹配结果选中首模板填入 context.template
- Agent 管线是增量能力，手动分步流程保持可用
- lifecycle\_status 自动推进：brief/strategy/plan → in\_planning，asset → ready

---

## V0.9 进展 — AI-native 协同架构升级 (2026-04-09)

### Brief 三入口与 Council 合并升级 **已完成** (2026-04-10)

| 项 | 说明 |
|---|---|
| Advisory Session 结构化产出 | `discussion.py`：`CouncilSynthesisBundle`、立场 JSON（stance/claim）、共识与 agreements/disagreements/open_questions/recommended_next_steps/alternatives；Brief 字段 `proposed_updates` 白名单过滤 |
| 决策分型与可应用性 | `reconcile_council_decision_type`（advisory/conflicted/insufficient_context/applyable）+ `compute_applyability`（direct/partial/none），写入 `StageProposal` / `AgentDiscussionRecord` |
| Brief 快照注入 | `RequestContextBundle.council_brief_snapshot` + `council_locked_fields_hint`，routes 侧 `_format_brief_snapshot_for_council` |
| API | `POST /content-planning/proposals/{id}/apply-as-draft`、`POST .../escalate-rewrite-brief`；`generate-brief` 可传 `council_escalation_notes`；`StageDiscussionRequest` 支持 `parent_discussion_id` / `target_sub_object_type`（Follow-up / 子对象预留） |
| SSE | 讨论流程发布 `council_phase`（collecting_opinions / synthesizing_consensus / session_ready） |
| 前端 Brief 页 | `content_brief.html`：Insight/Council/Conversation 文案、`renderDiscussion`、决策徽章、Apply as Draft / Escalate、对话「转为 Council 问题」、SSE 订阅 `council_phase` |

### Council v2（HTTP + SSE + Brief UI）**已完成** (2026-04-10)

| 批次 | 内容 |
|---|---|
| 1 | Schema：`CouncilSession` / `CouncilObservability`（`schemas/council_v2.py`）；`StageProposal`/`AgentDiscussionRecord` 扩展；`_run_stage_discussion` 四段返回；编排器 specialist/synthesis 计时与 degraded |
| 2 | SSE：`council_*` 10 类事件经 `event_bus`；`routes` 内 `_on_council_event`；持久化后 `council_proposal_ready` + `council_session_completed`；异常 `council_session_failed`；与 `council_phase` 双发兼容 |
| 3 | 前端：`content_brief.html` 状态机（FSM 文案）、SSE 增量行、`renderCouncilPanelsFromHttp`（session/可观测/共识/分歧）、CTA 按 `decision_type`×`applyability`、`转为 Variant` → `POST .../asset-bundle/.../generate-variant` |
| 4 | 可观测卡片（参与者降级/耗时）、契约见 **D-017**；`test_stage_workflow_api` 断言 `session`/`observability` 与事件历史中含 `council_proposal_ready`、`council_session_completed` |
| 跨页复用 | Strategy/Plan/Asset 的 Council 页可复用同一 HTTP/SSE 契约；`target_sub_object_type` 已在请求体预留 |
| Brief 右栏统一对话 | `content_brief.html`：`#ws-unified-thread` 承载 Chat + Council SSE；`council_phase` 仅更新状态条、不与 v2 事件重复刷行；HTTP 结束后以折叠块追加完整记录；`StageDiscussionRequest.include_chat_context` 默认 true，将 `AgentThread.context_summary()` 拼入 Council 问题（链式） |
| Strategy / Note Plan 右栏对齐 Brief | `content_strategy.html`（`#pw-unified-thread`）、`content_plan.html`（`#cw-unified-thread`）与 Brief 同模式：共享 `static/js/council_right_rail.js`（`CouncilRightRail.init`）、不订阅 `chat_response` SSE、Council `POST` 带 `include_chat_context: true`、HTTP 后折叠「服务端完整讨论记录」；Plan 页 API 前缀沿用模板 `cpApi`/`api_prefix` |

### Intel Hub：品牌配置只读页模板 (2026-04-10)

| 项 | 说明 |
|---|---|
| `brand_config.html` | 继承 `base.html`；单列卡片（`body .shell` max-width 900px）；上下文变量 `workspace_id`、`brand`、`guardrails`、`voice`、`audiences`、`objectives`；护栏标签色：禁用表达红 / 必提要点绿 / 风险词琥珀 |
| `_brand_context_bar.html` | Brief / Strategy / Plan / Assets 四工作台在 `_progress_bar.html` 之后共用品牌摘要条与 `guardrail_warnings`；链至 `/brand-config/{brand_id}`；可选 `guardrail_summary`（禁用/必提条数） |

### Intel Hub：Phase 3 工作区页面模板 (2026-04-10)

| 模板 | 变量摘要 |
|---|---|
| `workspace_home.html` | `workspace_id`、`workspace_name`、`stats`（`total_opportunities` / `in_planning` / `pending_approval` / `published` / `total_feedback`）；导航链至 pipeline / approvals / feedback |
| `opportunity_pipeline.html` | `workspace_id`、`stages[]`（`stage_name`、`stage_label`、`items[]`：`opportunity_id`、`title`、`status`、`updated_at`）；横向看板列 |
| `review_approval.html` | `workspace_id`、`approval_requests[]`（`request_id`、`object_type`、`object_id`、`requested_by`、`status`、`requested_at`、`notes`）；状态徽章 pending/approved/rejected/withdrawn |

### Phase 3 剩余：B2B 协同存储 + 生命周期状态 + 交付门控 API (2026-04-10)

| 项 | 说明 |
|---|---|
| 统一 `lifecycle_status` | `OpportunityBrief` / `RewriteStrategy` / `NewNotePlan` / `AssetBundle` 增加 `lifecycle_status`（默认 `new`） |
| B2B SQLite 表 | `object_assignments`、`object_comments`、`workspace_timeline`、`approval_requests`、`readiness_checklists`；`B2BPlatformStore` 对应 save/list/get |
| Intel Hub 路由 | `POST /objects/{type}/{id}/assign`、`POST/GET .../comments`、`POST /approvals/{request_id}/decision`、`GET /b2b/workspaces/{id}/timeline`；交付门控 `GET|PUT /objects/{type}/{id}/readiness` |
| `_plan_store` | `create_app` 内在 B2B 路由之前初始化 `_plan_store`，修复 `/b2b/.../feedback` 与 `/pipeline` 引用未定义变量问题 |

### Phase 0：基础修复 **已完成**

| 项 | 状态 | 说明 |
|---|---|---|
| AgentContext 完整化 | **已完成** | `run-agent` 端点现在通过 adapter 注入 card/source_notes/review_summary/template/titles/body/image_briefs/asset_bundle |
| append_version 接线 | **已完成** | `build_brief`/`build_strategy`/`build_plan` 成功后自动调用 `_snapshot_version` 写入版本历史 |
| ObjectLock enforcement | **已完成** | `_apply_locks` 方法在重生成时保留已锁定字段值不被覆盖 |
| runAgent 前端接线 | **已完成** | 4 个工作台的 AI Chips 全部接线到 `run-agent` API，结果包含 agent_name/置信度/动态 chips |
| BriefUpdateRequest 契约修复 | **已完成** | 新增 `why_worth_doing`/`competitive_angle` 字段 + flow editable 白名单 |
| GenerateStrategyRequest 契约修复 | **已完成** | 新增 `tone_hint` 字段 |

### Phase 1：协同网关 + SSE 流式 **已完成**

| 项 | 状态 | 说明 |
|---|---|---|
| Event Bus | **已完成** | `apps/content_planning/gateway/event_bus.py` — 进程内事件总线，按 opportunity_id 订阅/发布，保留 50 条历史 |
| Session Manager | **已完成** | `apps/content_planning/gateway/session_manager.py` — 多角色协同会话，消息记录与角色过滤 |
| SSE Handler | **已完成** | `apps/content_planning/gateway/sse_handler.py` — StreamingResponse SSE 流，历史重放 + 心跳 + 实时推送 |
| SSE 路由 | **已完成** | `GET /content-planning/stream/{id}` — 对象级 SSE 事件流 |
| Timeline 路由 | **已完成** | `GET /content-planning/timeline/{id}` — 历史消息 + 事件 |
| Lead Agent | **已完成** | `apps/content_planning/agents/lead_agent.py` — 总调度 Agent，关键词 + Skill + 上下文三层路由 |
| Agent Timeline UI | **已完成** | 4 个工作台右栏新增 SSE 订阅的实时时间线 + 对话输入框 |
| 事件注入 | **已完成** | `run-agent` 返回时自动发布 `agent_result` 事件到 Event Bus |

### Phase 2：多轮对话 + 对象上下文 **已完成**

| 项 | 状态 | 说明 |
|---|---|---|
| AgentMessage / AgentThread | **已完成** | `agents/base.py` 新增多轮对话线程模型，支持 context_summary() |
| BaseAgent.run_turn | **已完成** | 注入对话历史到 extra，子类可重写实现更丰富多轮行为 |
| Chat 端点多轮升级 | **已完成** | `POST /content-planning/chat/{id}` 使用 AgentThread 维护上下文 |
| Thread 查询端点 | **已完成** | `GET /content-planning/threads/{id}` — 最近 30 条消息 + 轮次数 |
| Session Manager 增强 | **已完成** | 角色过滤、时间线序列化、对话导出 |
| Object Events 广播 | **已完成** | 7 个 build/regenerate 方法在 _persist 后自动 emit_object_updated |

### Phase 3：Plan Graph 编排 + Memory **已完成**

| 项 | 状态 | 说明 |
|---|---|---|
| Plan Graph | **已完成** | `agents/plan_graph.py` — LangGraph 风格状态图，6 节点标准流水线，依赖检查 + 就绪发现 + 状态流转 |
| Agent Memory | **已完成** | `agents/memory.py` — SQLite 持久化跨会话记忆，store/recall/search + auto extract from results |
| Skill Registry | **已完成** | `agents/skill_registry.py` — 5 个内置 Skill（深度分析/Brief对比/策略辩论/视觉迁移/批量变体）+ YAML 加载 + 关键词匹配 |
| Lead Agent 增强 | **已完成** | Skill-based 路由 + 自动 Memory 提取 |
| Graph 端点 | **已完成** | `GET /content-planning/graph/{id}` |
| Memory 端点 | **已完成** | `GET /content-planning/memory/{id}` |
| Skills 端点 | **已完成** | `GET /content-planning/skills` |

### Phase 4：前端富交互 **已完成**

| 项 | 状态 | 说明 |
|---|---|---|
| 版本 Diff 视图 | **已完成** | Brief 版本列表增加"对比上版"按钮，逐字段红删绿增对比 |
| 多策略对比 | **已完成** | Strategy 页面新增双列对比面板（调性/钩子/CTA） |
| 协同面板 | **已完成** | Plan 页面新增参与者标签（人/Agent）+ 流水线状态图 |
| Skills 面板 | **已完成** | Asset 页面展示可用技能列表（名称/描述/触发词） |

### 新增文件清单

```
apps/content_planning/gateway/
  __init__.py           — 协同网关模块入口
  event_bus.py          — 进程内事件总线（ObjectEvent + EventBus 单例）
  session_manager.py    — 多角色协同会话管理
  sse_handler.py        — SSE StreamingResponse 端点

apps/content_planning/agents/
  lead_agent.py         — 总调度 Agent（路由 + 委派 + 记忆提取）
  plan_graph.py         — LangGraph 风格状态图编排
  memory.py             — SQLite 跨会话 Agent 记忆
  skill_registry.py     — 可扩展 Skill 注册系统
```

### 新增 API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/content-planning/stream/{id}` | SSE 实时事件流 |
| GET | `/content-planning/timeline/{id}` | 协同时间线 |
| POST | `/content-planning/chat/{id}` | 对象上下文对话 |
| GET | `/content-planning/threads/{id}` | 对话线程历史 |
| GET | `/content-planning/graph/{id}` | Plan Graph 状态图 |
| GET | `/content-planning/memory/{id}` | Agent 记忆查询 |
| GET | `/content-planning/skills` | 可用 Skills 列表 |

### 验证结果

- 235 tests 全部通过
- 所有新模块导入正确
- Plan Graph 6 节点 5 边正确构建
- Agent Memory SQLite CRUD 验证通过
- Skill Registry 5 个默认 Skill 加载成功

---
> V0.3+ 增量：评论-笔记自动关联 / 千问 VL 视觉分析 / 端到端验证通过。
> V0.4  RSS 趋势情报：接入 awesome-tech-rss + awesome-rss-feeds，新增「科技趋势」「新闻媒体」原生浏览页。
> V0.5  XHS 三维结构化机会卡流水线：视觉/卖点/场景三维提取 → 本体映射 → 机会卡生成。
> V0.5.1 四 Extractor 分层升级 + 跨模态校验器。
> V0.6  Ontology Pipeline 升级：cross_modal 贯穿全链路 + Projector 拆子函数 + Compiler 增强。
> V0.7  Opportunity Review MVP：机会卡检视 + 人工反馈 + 聚合统计 + 升级判定闭环。
> V0.8  B2B Pilot Foundation：workspace / brand / campaign / membership / connector / queue / approval / usage。
> 详见 [PLAN_V2_COMPILATION_CHAIN.md](./PLAN_V2_COMPILATION_CHAIN.md) / [XHS_OPPORTUNITY_PIPELINE.md](./XHS_OPPORTUNITY_PIPELINE.md)

## V0.8 进展 — B2B Pilot Foundation (2026-04-08)

| 项 | 状态 | 说明 |
|---|---|---|
| 平台对象 | **已完成** | 新增 `apps/b2b_platform/`，包含组织、工作区、品牌、活动、成员、连接器、机会队列、审批、用量与发布结果对象 |
| 平台存储 | **已完成** | `B2BPlatformStore` 使用 SQLite，支持 bootstrap / auth / queue / approvals / usage / snapshot |
| 内容策划对象升级 | **已完成** | `OpportunityBrief` / `RewriteStrategy` / `NewNotePlan` / `AssetBundle` / `PlanLineage` 新增 tenant context 字段 |
| 会话持久化升级 | **已完成** | `ContentPlanStore` 新增 tenant context 和 `asset_bundle_json` |
| API 增量 | **已完成** | 新增 `/b2b/*` 与 `POST /content-planning/xhs-opportunities/{id}/approve` |
| 计量 | **已完成** | brief / strategy / plan / generation / asset export 自动记录 `UsageEvent` |

## V0.7 进展 — Opportunity Review MVP (2026-04-03)

| 项 | 状态 | 说明 |
|---|---|---|
| Schema 设计 | **已完成** | 新增 `OpportunityReview` (`schemas/opportunity_review.py`); `XHSOpportunityCard` +7 聚合字段 (review_count/manual_quality_score_avg/actionable_ratio/evidence_sufficient_ratio/composite_review_score/qualified_opportunity/opportunity_status) |
| 存储层 | **已完成** | 新增 `XHSReviewStore` (`storage/xhs_review_store.py`): SQLite 两表 (xhs_opportunity_cards + xhs_reviews); sync_cards_from_json / list_cards / save_review / update_card_review_stats / get_review_summary |
| 聚合服务 | **已完成** | 新增 `review_aggregator.py`: 单卡聚合 (composite = 0.5×quality + 0.3×actionable + 0.2×evidence) + 全局统计 + needs_optimization 判定 |
| 升级服务 | **已完成** | 新增 `opportunity_promoter.py`: 5 项阈值全满足 → promoted; 有 review 未达标 → reviewed; 无 review → pending_review |
| API 端点 | **已完成** | 改造 GET /xhs-opportunities 从 store 读取; 新增 GET /{id} 详情 + POST /{id}/reviews 反馈 + GET /{id}/reviews 查询 + GET /review-summary 全局统计 |
| HTML 页面 | **已完成** | 改造 xhs_opportunities.html (状态筛选 + 聚合摘要 + 卡片链接); 新增 xhs_opportunity_detail.html (三区: 详情/聚合/反馈表单 + JS 异步提交) |
| 测试 | **已完成** | 3 个新测试文件共 26 测试: test_opportunity_review.py (13) + test_review_aggregator.py (6) + test_opportunity_promoter.py (7) — 全部通过 |
| 文档 | **已完成** | 新增 OPPORTUNITY_REVIEW.md; 更新 DATA_MODEL.md / IMPLEMENT.md / DECISIONS.md (D-019) |

## V0.6 进展 — Ontology Pipeline 升级 (2026-04-03)

| 项 | 状态 | 说明 |
|---|---|---|
| Schema 升级 | **已完成** | `XHSOntologyMapping` +`source_signal_summary`; `XHSOpportunityCard` +`content_pattern_refs`/`value_proposition_refs`/`audience_refs`; `suggested_next_step` 改为 `list[str]` |
| Config 补全 | **已完成** | `ontology_mapping.yaml` +`risk_claim_unverified`/`need_size_fit`; `opportunity_rules.yaml` +cross_modal 阈值/merge_rules |
| Projector 重构 | **已完成** | `project_xhs_signals()` 拆 8 子函数 (`map_styles`/`map_scenes`/`map_needs`/`map_risks`/`map_visual_patterns`/`map_content_patterns`/`map_value_propositions`/`map_audiences`) + `build_source_signal_summary` + `build_evidence_refs`; 新增 `cross_modal` 参数用于 risk 增补 |
| Compiler 升级 | **已完成** | `compile_xhs_opportunities()` 新增 `cross_modal` 参数; 三个 `_try_*_opportunity` 利用 cross_modal 评分调节 confidence; 新增 `merge_opportunities()` 去重; title/summary 升级为结构化中文; 所有卡片填充新增 refs 字段 |
| Pipeline 串联 | **已完成** | `project_xhs_signals()` 和 `compile_xhs_opportunities()` 均传入 `cross_modal=validation` |
| 测试 | **已完成** | 新增 `test_ontology_projector.py` (12 tests) + `test_xhs_opportunity_pipeline.py` (10 tests); 升级 `test_xhs_opportunity_compiler.py` (17 tests, 含 merge_opportunities + 新字段) — 全部 39 测试通过 |
| 文档 | **已完成** | 更新 XHS_OPPORTUNITY_PIPELINE.md / DATA_MODEL.md / DECISIONS.md (D-018) / IMPLEMENT.md |

## V0.5.1 进展 — 四 Extractor 分层升级 + 跨模态校验器 (2026-04-03)

| 项 | 状态 | 说明 |
|---|---|---|
| LLM 客户端封装 | **已完成** | `extraction/llm_client.py`: DashScope 文本 LLM + VLM 封装，无 key 静默降级 |
| Schema V2 扩展 | **已完成** | `xhs_signals.py` 三个 Schema 向后兼容扩展 + `xhs_validation.py` CrossModalValidation |
| visual_extractor V2 | **已完成** | 三层架构 (metadata + VLM + merge)，修复 visual_scene_signals bug，新增评分字段 |
| selling_theme_extractor V2 | **已完成** | 三层架构 (claimed + comment + classify)，新增卖点分类 (click/conversion/productizable/content_only) |
| scene_extractor V2 | **已完成** | 四层架构 (explicit + infer + goals + combos)，新增隐式推断和场景机会提示 |
| cross_modal_validator | **已完成** | 新增三种校验 (visual_support + comment + scene_alignment) + 总一致性评分 |
| Pipeline 集成 | **已完成** | 插入 Step 2.5 cross_modal_validation，PipelineResult 新增字段，导出更新 |
| 测试更新 | **已完成** | 三个 extractor 测试扩展新字段断言 + cross_modal_validator 测试 + 端到端编译器通过 |
| 文档 | **已完成** | XHS_OPPORTUNITY_PIPELINE.md 更新四维架构说明 + IMPLEMENT.md V0.5.1 进展 |

## V0.5 进展 — XHS 三维结构化机会卡流水线 (2026-04-03)

| 项 | 状态 | 说明 |
|---|---|---|
| Schema 层 | **已完成** | 6 个新文件: `xhs_raw.py`, `xhs_parsed.py`, `xhs_signals.py`, `evidence.py`, `ontology_mapping_model.py`, `opportunity.py` |
| 解析器 | **已完成** | `parsing/xhs_note_parser.py`: raw dict → XHSNoteRaw → XHSParsedNote，含评论关联 |
| 三维提取器 | **已完成** | `extraction/`: visual_extractor + selling_theme_extractor + scene_extractor，各含 evidence_refs |
| 本体映射 | **已完成** | `ontology_projector.py` 新增 `project_xhs_signals`；`ontology_mapping.yaml` 补充 5 个 canonical refs |
| 机会编译器 | **已完成** | `opportunity_compiler.py` 新增 `compile_xhs_opportunities`；`config/opportunity_rules.yaml` 三类规则 |
| 流水线入口 | **已完成** | `workflow/xhs_opportunity_pipeline.py`: 批量 + 单篇模式，输出 JSON + Markdown |
| 测试 | **已完成** | 5 个测试文件: parser / visual / selling / scene / compiler 端到端 |
| 文档 | **已完成** | `XHS_OPPORTUNITY_PIPELINE.md` + DATA_MODEL / DECISIONS / IMPLEMENT 更新 |

## V0.4 进展 — RSS 趋势情报 (2026-04-03)

| 项 | 状态 | 说明 |
|---|---|---|
| RSS 源配置 | **已完成** | `config/rss_feeds_tech.yaml` (46 feeds) + `config/rss_feeds_news.yaml` (30 feeds) |
| TrendRadar 启用 RSS | **已完成** | `config.yaml` rss.enabled → true，feeds 列表合并 40 个高优先级源 |
| RSS 数据加载器 | **已完成** | `ingest/rss_loader.py`: 直读 TrendRadar `output/rss/*.db`，按 category 过滤 |
| API 路由 | **已完成** | `/rss/tech` + `/rss/news`：支持分页、搜索、feed 来源筛选 |
| UI 模板 | **已完成** | `rss_feed.html`: 卡片网格、feed 标签筛选、摘要截断、原文链接 |
| 导航栏 + Dashboard | **已完成** | 新增「科技趋势」「新闻媒体」导航；Dashboard 统计卡片 |
| 一键执行脚本 | **已完成** | `scripts/run_rss_fetch_and_pipeline.py`: feedparser 独立抓取 + Pipeline 编译 |
| 端到端验证 | **已完成** | 39 源成功 / 1 失败, 1936 条目; Dashboard 科技 1514 / 新闻 424 |

## V0.3+ 进展 (2026-04-03)

| 项 | 状态 | 说明 |
|---|---|---|
| 评论-笔记关联 | **已完成** | `mediacrawler_loader.py` V2: 自动扫描 `search_comments_*.jsonl` 构建 `{note_id: [comments]}` 索引，注入 raw dict |
| 千问 VL 视觉分析 | **已完成** | `extractor/visual_analyzer.py`: 用 `dashscope` + `qwen-vl-max` 提取 6 维视觉信号（风格/场景/构图/色彩/材质/表达） |
| Pipeline 集成 | **已完成** | `refresh_pipeline.py` 支持 `enable_vision` 参数；视觉信号合并到 `BusinessSignalFrame` |
| 演示脚本升级 | **已完成** | `run_pipeline_stage_demo.py` V2: `--enable-vision`，评论统计，决策资产统计 |
| 端到端验证 | **已完成** | 79 条笔记 → 65 Signal → 54 Opportunity + 44 Insight + 12 VisualPattern + 29 DemandSpec；78/79 笔记关联 1174 条评论；评论信号 180 次命中 |

## V0.3 新增能力

### 四层编译链

| 层 | 模块 | 输入 → 输出 |
|---|---|---|
| Layer 1 内容解析 | `extractor/content_parser.py` | raw dict → `NoteContentFrame` |
| Layer 2 经营信号抽取 | `extractor/signal_extractor.py` | `NoteContentFrame` → `BusinessSignalFrame` |
| Layer 3 本体映射 | `projector/ontology_projector.py` (V2) | Signal → 多维 refs (scene/style/need/risk/material/content/visual/audience) |
| Layer 4 决策资产编译 | `compiler/*_compiler.py` (5 种) | Signal → 5 类决策卡片 |

### 5 类决策资产

| 卡片类型 | 编译器 | 服务角色 |
|---|---|---|
| OpportunityCard | `opportunity_compiler.py` | CEO, 营销, 产品, 视觉 |
| RiskCard | `risk_compiler.py` | CEO, 产品, 视觉, 营销 |
| InsightCard | `insight_compiler.py` | CEO, 营销, 产品 |
| VisualPatternAsset | `visual_pattern_compiler.py` | 视觉总监, 营销总监 |
| DemandSpecAsset | `demand_spec_compiler.py` | 产品总监, CEO |

### 10+ 类本体对象

`ontology_mapping.yaml` 扩展覆盖：scenes / styles / needs / risk_factors / materials / content_patterns / visual_patterns / audiences

### 多维 watchlist

`watchlists.yaml` 从 4 条扩展到 18 条，覆盖 10 种 watchlist_type。

---

## 当前目录结构

```text
apps/
  b2b_platform/
    __init__.py
    schemas.py
    storage.py
  intel_hub/
    api/
      app.py                         # +RSS 路由 /rss/tech, /rss/news
      templates/
        rss_feed.html                # V0.4 RSS 卡片网格模板
    compiler/
      dedupe.py
      demand_spec_compiler.py    # V0.3 DemandSpecAsset 编译器
      insight_compiler.py        # V0.3 InsightCard 编译器
      opportunity_compiler.py    # + V0.5 compile_xhs_opportunities()
      priority_ranker.py
      risk_compiler.py
      visual_pattern_compiler.py # V0.3 VisualPatternAsset 编译器
    extraction/                  # V0.5 三维提取器（与 extractor/ 独立）
      llm_client.py              # V0.5.1 统一 LLM/VLM 客户端封装
      visual_extractor.py        # V2 视觉维度提取（三层: metadata+VLM+merge）
      selling_theme_extractor.py # V2 卖点主题提取（三层: claimed+comment+classify）
      scene_extractor.py         # V2 场景维度提取（四层: explicit+infer+goals+combos）
      cross_modal_validator.py   # V0.5.1 跨模态一致性校验器
    extractor/                   # V0.3 四层编译链 Layer 1+2
      content_parser.py          # Layer 1 内容解析
      signal_extractor.py        # Layer 2 经营信号抽取
      comment_classifier.py      # 评论级信号分类
      visual_analyzer.py         # V0.3+ 千问VL视觉分析（dashscope qwen-vl-max）
    parsing/                     # V0.5 XHS 笔记解析器
      xhs_note_parser.py         # raw dict → XHSNoteRaw → XHSParsedNote
    ingest/
      trendradar_loader.py
      mediacrawler_loader.py     # V2: 自动关联评论 + image_list 传递
      rss_loader.py              # V0.4: 直读 TrendRadar RSS SQLite，按 category 过滤
      source_router.py           # 统一 raw signal 收集路由
      xhs_loader.py              # 小红书评论级数据加载（兼容旧路径）
      xhs_aggregator.py          # 评论聚合为笔记级信号（兼容旧路径）
    normalize/
      normalizer.py
    projector/
      canonicalizer.py
      entity_resolver.py
      ontology_projector.py
      topic_tagger.py
    schemas/
      cards.py                   # + InsightCard, VisualPatternAsset, DemandSpecAsset
      content_frame.py           # V0.3 NoteContentFrame + BusinessSignalFrame
      enums.py                   # + OpportunityType, RiskType, InsightType, TargetRole, CommentSignalType
      evidence.py                # V0.5 XHSEvidenceRef（轻量证据追溯）
      evidence_ref.py
      ontology_mapping_model.py  # V0.5 XHSOntologyMapping
      opportunity.py             # V0.5 XHSOpportunityCard
      review.py
      signal.py                  # + V2 多维 refs (scene/style/need/risk/material/...)
      watchlist.py
      xhs_raw.py                 # V0.5 XHSNoteRaw / XHSComment / XHSImageFrame
      xhs_parsed.py              # V0.5 XHSParsedNote
      xhs_signals.py             # V0.5.1 VisualSignals / SellingThemeSignals / SceneSignals V2
      xhs_validation.py          # V0.5.1 CrossModalValidation
    storage/
      repository.py
    workflow/
      refresh_pipeline.py
    tests/
config/
  watchlists.yaml
  ontology_mapping.yaml
  scoring.yaml
  dedupe.yaml
  runtime.yaml                      # trendradar + mediacrawler + xhs_sources 多源配置
                                     # + b2b_platform_db_path
third_party/
  TrendRadar/                       # git clone（.gitignore 排除）
    .venv/                          # 独立 Python 3.11 虚拟环境
    config/config.yaml              # 桌布配置
    config/frequency_words.txt      # 桌布词包
    output/                         # 真实抓取产出
  MediaCrawler/                     # git clone（.gitignore 排除）
    data/xhs/jsonl/                 # 原生 JSONL 输出
    database/sqlite_tables.db       # SQLite 输出
data/
  fixtures/
    mediacrawler_output/xhs/jsonl/  # MediaCrawler fixture 数据
data/
  fixtures/
    trendradar_output/
    trendradar_realistic/
    trendradar_tablecloth/
  raw/
docs/
  README_PRODUCT.md
  ARCHITECTURE.md
  IA_AND_PAGES.md
  DATA_MODEL.md
  PLAN.md
  IMPLEMENT.md
  DECISIONS.md
  examples/
```

## 已实现模块

- **小红书 / MediaCrawler → Signal / 卡片 全流程说明**（阶段、配置、Watchlist 角色）：见 [`docs/DATA_PIPELINE_XHS_INTEL_HUB.md`](./DATA_PIPELINE_XHS_INTEL_HUB.md)。
- **B2B 试点平台骨架**：workspace / brand / campaign / approval / usage 已落地。

## B2B Pilot Quick Start

1. 启动 API：`uvicorn apps.intel_hub.api.app:app --reload`
2. 调 `POST /b2b/bootstrap` 初始化 workspace
3. 用返回的 `workspace_id / api_token` 调 `POST /b2b/workspaces/{workspace_id}/opportunities/{opportunity_id}/queue`
4. 调 `content-planning` 路由时带上：
   - `X-Workspace-Id`
   - `X-User-Id`
   - `X-Api-Token`
   - 可选：`X-Brand-Id` / `X-Campaign-Id`
5. 可用新增接口：
   - `GET /b2b/workspaces/{workspace_id}/usage`
   - `GET /b2b/workspaces/{workspace_id}/approvals`
   - `GET /b2b/workspaces/{workspace_id}/snapshot`
   - `POST /content-planning/xhs-opportunities/{opportunity_id}/approve`

- `ingest/trendradar_loader.py`
  - 最新批次选择
  - `.json` / `.jsonl` / `.db` 分支
  - `news_items` / `rss_items` 专用映射
- `ingest/xhs_loader.py`
  - 读取 review_intel capture 目录（events.jsonl）
  - 读取 MediaCrawler 原生 store jsonl / sqlite
  - RawReviewEvent → intel_hub raw dict 映射
- `ingest/xhs_aggregator.py`
  - 按 note_id 聚合评论为笔记级信号
  - top N 高互动评论拼接为正文
  - 聚合 metrics（engagement / comment_count / avg_likes）
- `normalize/normalizer.py`
  - 去空、去重、时间标准化、附带 raw source metadata
- `projector/canonicalizer.py`
  - alias -> canonical entity 归一
- `projector/entity_resolver.py`
  - 输出 `raw_entity_hits` / `canonical_entity_refs`
- `projector/topic_tagger.py`
  - 通用 topic tagging
  - 桌布 demo 的轻量 topic tags 规则
- `compiler/dedupe.py`
  - 显式规则 dedupe
- `compiler/opportunity_compiler.py`
- `compiler/risk_compiler.py`
  - 输出 `dedupe_key` / `merged_signal_ids` / `merged_evidence_refs`
- `storage/repository.py`
  - SQLite 自迁移
  - review writeback
  - `review_status` / `reviewer` / `platform` 查询
- `api/app.py`
  - GET 列表
  - POST review
  - HTML 展示 review 字段与桌布快捷过滤

## 如何运行

### 1. 创建本地 Python 3.11 虚拟环境

```bash
python3.11 -m venv .venv311
.venv311/bin/pip install fastapi pydantic pyyaml uvicorn jinja2 httpx
```

说明：

- 目标设计仍尽量对齐 TrendRadar 生态。
- 当前工作站验证使用 `python3.11`。

### 2. 刷新数据

```bash
.venv311/bin/python -m apps.intel_hub.workflow.refresh_pipeline
```

`refresh_pipeline` 在 **INFO** 日志下会输出 `[intel_hub.pipeline]` 各阶段统计（原始采集、归一化、本体投影、打分、聚类/卡片、持久化）。模块入口已 `basicConfig(INFO)`。

用 **MediaCrawler 产出**（默认 `third_party/MediaCrawler/data/xhs/jsonl`，不读 fixture）跑通并观察日志：

```bash
.venv311/bin/python apps/intel_hub/scripts/run_pipeline_stage_demo.py
# 或指定目录: --mediacrawler-jsonl path/to/jsonl

# RSS 趋势抓取 + Pipeline 一键执行
.venv311/bin/python -m apps.intel_hub.scripts.run_rss_fetch_and_pipeline
# 仅抓取 RSS 不运行 Pipeline:
.venv311/bin/python -m apps.intel_hub.scripts.run_rss_fetch_and_pipeline --skip-pipeline
```

### 3. 启动本地服务

```bash
.venv311/bin/uvicorn apps.intel_hub.api.app:app --reload
```

### 4. 运行测试

```bash
.venv311/bin/python -m unittest discover -s apps/intel_hub/tests -v
```

## 真实 TrendRadar output 验证方式

1. 修改 `config/runtime.yaml` 中的 `trendradar_output_dir`
2. 指向真实的 `output/` 根目录
3. 运行 refresh pipeline
4. 检查：
   - `data/intel_hub.sqlite`
   - `data/raw/latest_raw_signals.jsonl`
   - API / HTML 页面是否能读到结果

当前仓库内未提供真实目录，仅提供：

- `data/fixtures/trendradar_output/output`
- `data/fixtures/trendradar_realistic/output`
- `data/fixtures/trendradar_tablecloth/output`
- 测试内动态生成的 `.db` fixture

## Tablecloth Demo Quick Start

### 1. 准备外部 TrendRadar 配置

- 参考：
  - `docs/examples/trendradar_tablecloth_config_snippet.yaml`
  - `docs/examples/frequency_words_tablecloth_v1.txt`
- 建议：
  - `report.mode = current`
  - `report.display_mode = keyword`
  - `filter.method = keyword`
  - 默认启用 `zhihu/douyin/bilibili/tieba/toutiao/weibo`

### 2. 运行外部 TrendRadar

- 由外部 TrendRadar 仓库负责抓取和 output 落盘。
- 本仓库不包含 TrendRadar 源码，不直接修改其 `config/config.yaml`。

### 3. 指向 output 并刷新 intel_hub

```bash
.venv311/bin/python -m apps.intel_hub.workflow.refresh_pipeline
```

如需指向真实 output，请修改 `config/runtime.yaml` 中的 `trendradar_output_dir`。

### 4. 在 UI 查看桌布情报

- `/signals?entity=category_tablecloth`
- `/signals?entity=category_tablecloth&platform=weibo`
- `/opportunities?entity=category_tablecloth`
- `/risks?entity=category_tablecloth`

若还没有真实 output，可先用 `data/fixtures/trendradar_tablecloth/output` 进行本地验证。

## `.db` 解析说明

- 优先识别：
  - `news_items`
  - `platforms`
  - `rank_history`
  - `rss_items`
  - `rss_feeds`
- 若表或列缺失：
  - best effort 返回可用字段
  - 最终回退通用 SQLite 扫描

best effort 字段包括：

- `source_url`
- `source_name`
- `platform`
- `title`
- `summary`
- `raw_text`
- `published_at`
- `captured_at`
- `author`
- `account`
- `metrics`
- `rank`
- `keyword`
- `watchlist_hits`
- `raw_source_type`

## 配置文件位置

- `config/runtime.yaml`
- `config/watchlists.yaml`
- `config/ontology_mapping.yaml`
- `config/scoring.yaml`
- `config/dedupe.yaml`
- `docs/examples/trendradar_tablecloth_config_snippet.yaml`
- `docs/examples/frequency_words_tablecloth_v1.txt`

## 数据输出位置

- SQLite：`data/intel_hub.sqlite`
- Raw snapshot：`data/raw/latest_raw_signals.jsonl`

## API 清单

- `GET /signals`
- `GET /opportunities`
- `GET /risks`
- `GET /watchlists`
- `POST /opportunities/{id}/review`
- `POST /risks/{id}/review`

列表过滤：

- `page`
- `page_size`
- `entity`
- `topic`
- `platform`
- `review_status`
- `reviewer`

兼容别名：

- `status` 仍兼容旧调用，但新文档统一使用 `review_status`

## TrendRadar Real Run

### 目录结构

```text
third_party/
  TrendRadar/               # git clone（.gitignore 排除）
    .venv/                  # Python 3.11 独立虚拟环境
    config/config.yaml      # 桌布配置（已修改）
    config/frequency_words.txt  # 桌布词包
    output/
      news/2026-04-02.db    # 真实抓取产出（SQLite）
      html/                 # HTML 报告
```

### 环境搭建

```bash
mkdir -p third_party
git clone --depth 1 https://github.com/sansan0/TrendRadar.git third_party/TrendRadar
python3.11 -m venv third_party/TrendRadar/.venv
third_party/TrendRadar/.venv/bin/pip install requests pytz PyYAML feedparser json-repair tenacity
```

说明：litellm 安装耗时过长且非核心抓取依赖，创建了 stub 包以满足 import。AI 功能在 config.yaml 中已全部禁用。

### TrendRadar 配置要点

已修改 `third_party/TrendRadar/config/config.yaml`：

- `filter.method: keyword`（关键词匹配，不用 AI）
- `report.mode: current`
- `schedule.enabled: false`
- `rss.enabled: false`
- `notification.enabled: false`
- `ai_analysis.enabled: false`
- `ai_translation.enabled: false`
- 平台仅保留 6 个：zhihu / douyin / bilibili-hot-search / tieba / toutiao / weibo

已覆盖 `third_party/TrendRadar/config/frequency_words.txt`：桌布品类词包（核心品类词、风格词、痛点/卖点词、内容意图词）。

### 运行命令

```bash
cd third_party/TrendRadar
.venv/bin/python -m trendradar
```

运行入口：`trendradar/__main__.py`（不是 main.py）。

### 产出

- `third_party/TrendRadar/output/news/{date}.db`：SQLite，表 `news_items` / `platforms` / `rank_history`
- `third_party/TrendRadar/output/html/{date}/`：HTML 报告

### 对接 intel_hub

`config/runtime.yaml` 已修改：

```yaml
trendradar_output_dir: third_party/TrendRadar/output
```

### Pipeline 运行结果（2026-04-02）

```json
{"raw_count": 170, "signal_count": 170, "opportunity_count": 0, "risk_count": 1}
```

- 6 个平台共抓取 170 条热榜数据
- 170 条全部进入 signal 库
- 热榜内容以泛话题为主，桌布品类在热榜命中率极低（0 条频率词匹配）
- 新增 1 条风险卡（bilibili 平台监管信号）

### UI 访问

```bash
.venv311/bin/uvicorn apps.intel_hub.api.app:app --reload --port 8500
```

- 仪表盘：`http://127.0.0.1:8500/`
- 全部信号：`http://127.0.0.1:8500/signals`
- 按平台过滤：`http://127.0.0.1:8500/signals?platform=bilibili`
- 机会卡：`http://127.0.0.1:8500/opportunities`
- 风险卡：`http://127.0.0.1:8500/risks`

## 当前限制

- 热榜泛内容对桌布品类几乎无命中，需补充垂类内容源。
- 关键词噪音：`防水`/`推荐`/`测评`等高频通用词可能在其他场景引入非桌布内容。
- risk 卡可能为空：桌布场景在默认平台上的风险信号密度低。
- 单次快照：current 模式只看当前榜单，不保留历史趋势。
- litellm 使用 stub：AI 分析/翻译功能在当前环境中不可用。
- review 只更新 card，不更新 signal/evidence。
- HTML 页面目前只展示 review，不提供提交表单。
- dedupe 仍是显式规则，不处理复杂语义相似度。
- XHS 二级评论（fetch_replies）尚未接入。
- XHS 笔记正文（desc）尚未作为独立 Evidence 记录。
- XHS 抓取需要浏览器登录和 Cookie，非全自动化。

## TODO

- ~~补充垂类内容源（如小红书 RSS / 自定义爬虫）以提升桌布信号命中率。~~（已通过 MediaCrawler 集成完成）
- ~~实现 source_router 统一收集入口。~~（已完成）
- 在 MediaCrawler 真实 output 上验证 `mediacrawler_loader` 字段映射准确性。
- 增加 review 历史和 signal/evidence 级反馈。
- 真实回归桌布词包噪音并迭代关键词共现规则。
- 实现定时自动执行 TrendRadar + MediaCrawler 抓取 + pipeline 刷新。
- 扩展 MediaCrawler 到更多平台（抖音/快手/B站）。
- 增量加载优化（基于文件名日期/mtime 过滤，避免重复加载历史文件）。
- XHS：接入 review_intel/cleaners 的 spam_score / quality_score。

## Progress Notes

### 2026-04-02

- V0.1：新增 `intel_hub` Python 模块、配置、文档和样例数据。
- V0.1：跑通从 TrendRadar-style output 到 Signal/Evidence/Card/SQLite/API/UI 的最小闭环。

### 2026-04-02 V0.2

- 增加真实 output 兼容增强，`.db` 支持公开 schema 专用映射。
- 增加 review writeback、review 过滤和 POST review API。
- 增加 canonical entity projection 与显式 card dedupe。
- 增加 loader/review/entity/dedupe/pipeline/API 回归测试。

### 2026-04-02 Tablecloth Demo

- 新增桌布情报配置样例和词包 V1。
- 新增 `category_tablecloth` watchlist 与 ontology mapping。
- 新增桌布 fixture、桌布 pipeline 测试和 `platform` 过滤能力。
- 页面支持通过 `entity=category_tablecloth` 和 `platform=` 查看桌布 signals / opportunities / risks。

### 2026-04-02 TrendRadar Real Run

- 克隆 TrendRadar 到 `third_party/TrendRadar`，.gitignore 排除。
- 建立独立 Python 3.11 venv，安装核心依赖，创建 litellm stub。
- 配置 TrendRadar：keyword filter / current mode / 6 平台 / 桌布词包。
- 首轮真实抓取：6 平台 170 条热榜数据 → `output/news/2026-04-02.db`。
- `config/runtime.yaml` 指向真实 output，pipeline 成功读取 170 条 raw → 170 signals + 1 risk card。
- UI 验证：所有端点（/、/signals、/opportunities、/risks）返回 200。
- 确认热榜泛内容对桌布品类命中率极低，需补充垂类源。

### 2026-04-02 XHS MediaCrawler 集成

- 新增 `ingest/xhs_loader.py`：支持读取 review_intel capture（events.jsonl）、MediaCrawler store jsonl、store sqlite 三种格式。
- 新增 `ingest/xhs_aggregator.py`：按 note_id 聚合评论为笔记级信号，top N 高互动评论拼接正文。
- 修改 `config/runtime.yaml`：新增 `xhs_sources` 和 `xhs_aggregation` 配置段。
- 修改 `config_loader.py`：`RuntimeSettings` 增加 `xhs_sources`/`xhs_aggregation` 字段。
- 修改 `refresh_pipeline.py`：TrendRadar 加载后自动合并 XHS 信号。
- 修改 `normalizer.py`：置信度计算增加 comment_count + avg_likes 路径。
- 修改 `topic_tagger.py`：增加小红书评论专属标签规则（用户真实体验/购买意向/负面反馈/推荐种草）。
- 修改 `ontology_mapping.yaml`：增加 `xiaohongshu` platform_ref（synonyms: xhs/小红书/红书）。
- 修改 `watchlists.yaml`：`category_tablecloth.source_refs` 增加 `mediacrawler_xhs`。
- Pipeline 验证（fixture 15 条评论 → 3 篇笔记 → 3 条聚合信号 + 3 张桌布机会卡）。
- UI 验证：`/signals?platform=xiaohongshu` 可正确过滤查看。
- 数据源路径：`/Users/yichen/Desktop/OntologyBrain/MediaCrawler-main/review_intel_capture`。

### 2026-04-02 MediaCrawler Source Adapter 集成

- 克隆 MediaCrawler 到 `third_party/MediaCrawler`，`.gitignore` 排除。
- 新增 `ingest/mediacrawler_loader.py`：读取 MediaCrawler 原生笔记级输出（JSONL/JSON/SQLite），映射为 intel_hub raw signal dict。
  - 自动检测目录下的文件类型
  - JSONL：过滤含 `note_id` 的笔记记录
  - JSON：解析数组格式
  - SQLite：查询 `xhs_note` 表
  - 字段映射：title/desc/note_url/nickname/time/metrics/tag_list/source_keyword
- 新增 `ingest/source_router.py`：统一 raw signal 收集路由。
  - `collect_raw_signals(settings)` 替代 pipeline 中的硬编码分支
  - 按配置依次调用 trendradar_loader / mediacrawler_loader / xhs_capture
  - 支持 `fixture_fallback` 回退
- 修改 `config/runtime.yaml`：新增 `mediacrawler_sources` 配置段（enabled/platform/output_path/fixture_fallback）。
- 修改 `config_loader.py`：`RuntimeSettings` 增加 `mediacrawler_sources` 字段。
- 重构 `refresh_pipeline.py`：移除硬编码 loader 分支，改为 `collect_raw_signals(settings)`。
- 增强 `topic_tagger.py`：
  - 桌布规则增加：拍照出片、价格敏感、尺寸适配
  - 已有规则扩充关键词（风格偏好加"复古"/"法式"，材质偏好加"硅胶"/"皮革"等）
  - 修复 `is_xhs` 检测：支持 `platform_refs` 为 `"xiaohongshu"` 的情况
- 新增 fixture：`data/fixtures/mediacrawler_output/xhs/jsonl/` 下 5 条笔记 + 4 条评论。
- 新增测试：
  - `test_mediacrawler_loader.py`：12 个测试（JSONL/JSON/SQLite/edge cases）
  - `test_source_router.py`：6 个测试（双源/单源/disabled/fallback/空）
  - `test_xhs_tablecloth_pipeline.py`：2 个端到端测试
- Pipeline 验证：fixture 5 条笔记 → 5 条 xiaohongshu signals + category_tablecloth 实体 + 8 张 opportunity cards。
- 全量 38 个测试通过，无回归。

### 2026-04-02 MediaCrawler 真实抓取验证

- 运行命令：`uv run main.py --platform xhs --lt qrcode --type search --save_data_option jsonl`
- 配置关键词：桌布,餐桌布,防水桌布（base_config.py）
- 真实产出：20 条笔记 + 99 条评论 → `third_party/MediaCrawler/data/xhs/jsonl/`
- mediacrawler_loader 映射验证：全部 20 条笔记正确映射，0 条评论泄漏
- Pipeline 端到端：193 signals（170 TrendRadar + 20 MediaCrawler + 3 XHS聚合），23 opportunities，1 risk

### 2026-04-02 MediaCrawler 抓取健壮性 + 可观测性

**问题诊断**：单条笔记获取失败（`raise Exception`）导致 `asyncio.gather` 整页崩溃，后续关键词不执行。

**改动清单**：

1. `third_party/MediaCrawler/media_platform/xhs/core.py`（最小补丁）：
   - `get_note_detail_async_task`：末尾增加 `except Exception` 兜底，单条失败返回 `None`
   - `search()`：增加 `except Exception` 关键词级隔离，单关键词失败不终止后续
   - `batch_get_note_comments`：`asyncio.gather` 增加 `return_exceptions=True`
   - 注入全局 `_crawl_reporter` + `set_crawl_reporter()` 函数
   - `search()` 5 处状态上报 hook：set_keywords/keyword_started/notes_found/note_saved/note_failed/comments_saved/keyword_finished

2. `apps/intel_hub/workflow/crawl_status.py`（新增）：
   - `CrawlStatus` dataclass：run_id/status/keywords/notes_saved/notes_failed/errors 等
   - `CrawlStatusReporter`：原子写入 `data/crawl_status.json`（write-to-temp + os.replace）
   - `NoopReporter`：空操作，未注入 reporter 时默认行为

3. `apps/intel_hub/workflow/crawl_runner.py`（新增）：
   - 薄包装脚本，初始化 reporter → 注入 MediaCrawler → 运行抓取 → 更新状态
   - CLI：`python -m apps.intel_hub.workflow.crawl_runner --keywords "桌布,餐桌布"`
   - 支持 `--auto-pipeline` 抓取完成后自动触发 refresh_pipeline

4. `apps/intel_hub/api/app.py`：
   - 新增 `GET /crawl-status` 端点，读取 `data/crawl_status.json`
   - Dashboard 路由注入 crawl 状态数据

5. `apps/intel_hub/api/templates/dashboard.html`：
   - 新增「采集器状态」卡片（空闲/采集中/已完成/失败 四种状态）
   - 显示：关键词进度、已抓笔记数、失败数、评论批次、进度条
   - 内嵌 JS 轮询 `/crawl-status`（运行中 3s，非运行 10s）
   - 运行中时卡片带脉冲动效

### 2026-04-03 MediaCrawler 稳定性改造蓝图实施

完整实施 4 阶段蓝图，将 MediaCrawler 从单机脚本升级为 5 层架构：Source Worker / Session Service / Job Queue / Raw Lake / intel_hub。

**Phase 1: Playwright 原生能力补齐**

1. **storage_state 导出/复用** (`core.py`):
   - 登录成功后自动导出 `data/sessions/xhs_state.json` + `.meta.json`（含 `exported_at`）
   - 下次启动时优先尝试复用 storage_state，pong 失败才走 QR 登录
   - 超过 24h 的 storage_state 标记为 stale

2. **失败 tracing 归档** (新增 `tools/trace_manager.py`):
   - `TraceManager`: 对采集失败任务自动截图 + 保存 trace（可选）
   - 归档到 `data/traces/{date}/{note_id}_{time}/`（screenshot.png + meta.json）
   - 超过 7 天自动清理
   - `get_note_detail_async_task` 中 DataFetchError/Exception 触发 capture

3. **BrowserContext 隔离** (`core.py`):
   - 非 CDP 模式下每次 run 创建独立 context（从 storage_state 初始化）
   - CDP 模式下存储 browser 引用供后续隔离
   - `close()` 优先关闭隔离 context

**Phase 2: Session Service + 选择器版本化**

4. **Session Service** (新增 `apps/intel_hub/workflow/session_service.py`):
   - `AccountSession` dataclass: account_id/platform/storage_state_path/status/cooldown
   - `SessionService`: acquire_session/release_session/mark_relogin_needed
   - 连续失败 3 次标记 `needs_relogin`，自动冷却 15 分钟
   - 持久化到 `data/sessions/session_registry.json`

5. **选择器版本化** (新增 `media_platform/xhs/extractors/`):
   - `registry.py`: `ExtractorRegistry` — validate -> extract -> fallback 链
   - `search_v1.py` / `note_detail_v1.py` / `comment_v1.py`: 三种页面类型 v1 抽取器
   - 每个 extractor 带 `last_verified_at` 时间戳
   - `get_extractor(page_type, data)` 按优先级匹配

6. **可观测性增强** (`crawl_status.py` + `dashboard.html`):
   - CrawlStatus 扩展: traces_saved/trace_dir/session_id/extractor_versions/duration_seconds/avg_note_delay_seconds
   - CrawlStatusReporter 新增: trace_captured/set_session_id/set_extractor_versions/duration 自动计算
   - Dashboard 新增 4 列: Trace归档/耗时/平均延迟/会话

**Phase 3: Job Queue + Worker 解耦**

7. **任务模型** (新增 `apps/intel_hub/workflow/job_models.py`):
   - `CrawlJob` dataclass: job_id/platform/job_type/payload/priority/status/retry_count
   - 支持 keyword_search / note_detail / comments / pipeline_refresh
   - mark_running/mark_completed/mark_failed 状态机

8. **文件队列** (新增 `apps/intel_hub/workflow/job_queue.py`):
   - `FileJobQueue`: 基于 JSON 文件的 PoC 队列（接口兼容 RQ/Celery）
   - enqueue/dequeue/complete/fail/retry/list_jobs/stats
   - 线程安全（threading.Lock）+ 原子写入

9. **采集 Worker** (新增 `apps/intel_hub/workflow/collector_worker.py`):
   - `execute_keyword_search`: 配置 MC → inject reporter → run crawl → release session
   - `process_one_job`: dequeue → execute → complete/fail
   - `worker_loop`: 持续轮询消费
   - 自动 enqueue `pipeline_refresh` 当所有 crawl job 完成

10. **调度器** (新增 `apps/intel_hub/workflow/scheduler.py`):
    - `SchedulerDaemon`: 守护线程，按 `config/crawl_schedule.yaml` 创建任务
    - `run_all_schedules`: 手动触发所有调度
    - 每日去重（同名 schedule 每天最多运行一次）

11. **配置文件**:
    - `config/crawl_schedule.yaml`: daily_keyword_scan + weekly_deep_scan
    - `config/keywords.yaml`: 关键词列表

12. **API 端点** (`app.py`):
    - `POST /crawl-jobs`: 提交采集任务
    - `GET /crawl-jobs`: 列出任务（支持 status 过滤）
    - `GET /crawl-jobs/{job_id}`: 查询单个任务
    - `POST /crawl-jobs/{job_id}/retry`: 手动重试
    - `GET /sessions`: 列出会话状态
    - `GET /alerts`: 获取系统告警

**Phase 4: Raw Lake + Pipeline 自动化 + 告警**

13. **Raw Lake 增量扫描** (`source_router.py`):
    - 新增 `_collect_raw_lake()`: 扫描 `data/raw_lake/{platform}/{date}/{run_id}/`
    - 按 `metadata.json` 的 `ingested` 标记跳过已处理 run
    - 处理后自动标记 `ingested: true`

14. **告警系统** (新增 `apps/intel_hub/workflow/alerting.py`):
    - `Alert` dataclass + `AlertManager`
    - 告警类型: session_needs_relogin / extractor_mismatch / crawl_failure / pipeline_error
    - 持久化到 `data/alerts.json`，Dashboard 轮询展示
    - 支持 resolve 标记已处理

15. **Dashboard 告警卡片** (`dashboard.html`):
    - 新增「系统告警」卡片，轮询 `/alerts` 每 15s
    - 红色边框 + 未解决告警计数 + 最近 5 条详情

**验证**: 全量 38 个测试通过，所有模块 import 成功，FastAPI 18 条路由注册正常。

### 2026-04-24 采集可观测性统一 + 全局右侧进度窗

- 新增 `GET /crawl-observer` 聚合接口，统一返回：
  - `active_job`
  - `queue`
  - `crawl`
  - `pipeline`
  - `derived_state`
  - `stalled_reason`
  - `actions`
- `derived_state` 首版固定为：
  - `idle`
  - `queued`
  - `crawling`
  - `crawl_completed_waiting_pipeline`
  - `pipeline_running`
  - `result_ready`
  - `failed`
  - `stalled`
- `stalled_reason` 首版固定为：
  - `worker_not_running`
  - `status_stale`
  - `pipeline_not_ready`
- `CrawlJob` 扩展字段：
  - `job_group_id`：把同一条采集链路里的 crawl job 与 `pipeline_refresh` 关联起来
  - `display_keyword`：直接提供前端展示文案
  - `last_heartbeat_at`：由 worker 处理过程中刷新，用于 stalled 判定
- `FileJobQueue` 增加：
  - heartbeat 更新
  - 最近活动 job 选择
  - 按 `job_group_id` 查询关联任务
- `collector_worker.py` 调整：
  - 处理 `keyword_search` 时写 heartbeat
  - 自动创建 `pipeline_refresh` 时继承 `job_group_id`
  - 执行 `pipeline_refresh` 时也写 heartbeat
- UI 侧统一为一套口径：
  - `base.html` 新增全局右侧“采集观察窗”，开始采集后自动弹出，可收起，可跨页面恢复
  - `notes.html` 不再独立维护主状态源，改为通过 `window.CrawlObserver` 触发和消费全局观察状态
  - `dashboard.html` 顶部采集状态卡改为轮询 `/crawl-observer`，点击卡片可直接展开右侧观察窗
- 首版继续使用轮询，不引入 SSE：
  - 活跃状态 3s
  - 空闲/完成状态 10s
- worker 存活不做真实进程探测，首版通过“pending 超时未消费”与“heartbeat/crawl status 超时未更新”推断卡住状态。

---

**桌布主图模板提取配置（2026-04-04）**

- 新增 `config/template_extraction/`：`label_taxonomy.yaml`（四层全量标签）、`feature_rules.yaml`、`clustering_params.yaml`、`template_defaults.yaml`（六套模板默认字段，对齐 `docs/template_define.md` / `docs/compile_template.md`）。

## 模板提取流水线 (Template Extraction Pipeline) 进展

### V1.0 骨架完成 (2026-04-03)

已完成：

- schemas: 7 个 Pydantic 数据模型 (labels, labeled_note, cover_features, gallery_features, cluster_sample, template, agent_plan)
- config: 4 个 YAML 配置文件 (label_taxonomy, feature_rules, clustering_params, template_defaults)
- labeling: 四层标签体系 + 规则标注器 + VLM 标注器(mock) + 标注流水线
- features: 图像/文本/标签特征提取 + 图组分析 + 特征流水线
- clustering: 两阶段聚类 (封面原型 + 图组策略) + 报告生成 + 聚类流水线
- templates: 模板编译器 + 验证器 + 6 套模板 mock JSON
- agent: 模板检索 + 模板匹配 + 主图方案编译
- evaluation: 标注/聚类/模板质量评估 + 验收报告生成
- docs: TEMPLATE_EXTRACTION.md + ANNOTATION_GUIDE.md
- tests: 6 个测试文件覆盖所有模块

待办：

- 接入真实 VLM 标注
- 接入图像 embedding
- 真实数据端到端验证
- UMAP+HDBSCAN 聚类对比

## 内容策划编译链 (Content Planning Pipeline) 进展

### V1.0 完整链路实现 (2026-04-04)

已完成全链路：promoted 机会卡 → OpportunityBrief → 选模板 → RewriteStrategy → NewNotePlan → LLM 生成标题/正文/图片指令。

#### 目录结构

- `apps/content_planning/` 独立内容策划编译层，不侵入 intel_hub / template_extraction

#### Phase 1: Schema 层

- `schemas/opportunity_brief.py` — OpportunityBrief（结构化机会摘要，后续步骤的统一锚点）
- `schemas/rewrite_strategy.py` — RewriteStrategy（Brief + 模板 → 可执行改写方向）
- `schemas/note_plan.py` — TitlePlan / BodyPlan / NewNotePlan（标题/正文/图片三维策划）
- `schemas/content_generation.py` — TitleGenerationResult / BodyGenerationResult / ImageBriefGenerationResult（LLM 生成产物）
- `schemas/template_match_result.py` — TemplateMatchResult / TemplateMatchEntry（结构化匹配结果）
- 修改 `MainImagePlan` 新增 `opportunity_id` / `brief_id` / `strategy_id` 可选回溯字段

#### Phase 2: Adapter + BriefCompiler

- `adapters/intel_hub_adapter.py` — IntelHubAdapter（桥接 review_store / pipeline_details / raw notes）
- `services/brief_compiler.py` — BriefCompiler（规则优先，逐字段从机会卡提炼 Brief）

#### Phase 3: TemplateMatcher 改造

- `template_matcher.py` 新增 `brief: OpportunityBrief | None` 参数
- brief-aware 精准打分（content_goal / target_scene / visual_style / template_hints / avoid_directions）
- 向后兼容：brief 为 None 时完全走旧逻辑
- 修复 `phrase[:4]` bug（按字符截取改为按 bigram token 匹配）

#### Phase 4: RewriteStrategyGenerator

- `services/strategy_generator.py` — 规则优先的改写策略生成，预留 `_llm_enhance` 接口
- 从 Brief + 模板规则合成 positioning / hook / tone / keep / replace / enhance / avoid / 标题/正文/图片策略

#### Phase 5: NewNotePlanCompiler

- `services/new_note_plan_compiler.py` — 整合 Brief + Strategy + Template 编译完整策划
- 复用 `MainImagePlanCompiler` 生成图片策划，自动填充回溯 ID

#### Phase 6: LLM 驱动内容生成器

- `services/title_generator.py` — LLM 优先的标题生成（5 条候选 + 切入角度 + 理由），规则降级
- `services/body_generator.py` — LLM 优先的正文生成（开头/段落/CTA/语气自检），规则降级
- `services/image_brief_generator.py` — LLM 优先的图片执行指令生成（每张图的主体/构图/道具/色调），规则降级
- 三个生成器均复用 `llm_client.call_text_llm` + `parse_json_response`
- **Prompt Registry（2026-04-08）**：`config/prompts/*.yaml` + `apps/content_planning/services/prompt_registry.py`（`load_prompt` / 进程内缓存）；`strategy_generator` / `title_generator` / `body_generator` / `image_brief_generator` 与 `apps/template_extraction/agent/template_matcher.py` 的 LLM 分支从 YAML 加载提示词（`image_brief` / `template_match` 中带 JSON 示例的模板对花括号做 `str.format` 转义）。

#### Phase 7: 编排流 + API

- `services/opportunity_to_plan_flow.py` — OpportunityToPlanFlow 一站式编排入口
- `api/routes.py` — FastAPI 路由：`POST /content-planning/xhs-opportunities/{id}/generate-brief` 和 `POST .../generate-note-plan`
- 挂载到 `apps/intel_hub/api/app.py`，共享 review_store

#### Phase 8: 测试

- 28+ 个 content_planning 测试（含 promoted 门禁、生成结果回溯字段等），覆盖：
  - 7 个 Schema 序列化测试
  - 5 个 BriefCompiler 单元测试
  - 3 个 StrategyGenerator 单元测试
  - 3 个 NewNotePlanCompiler 测试
  - 4 个 Generator 降级模式测试
  - E2E Flow（mock adapter）：未找到 / 未 promoted / plan_only / with_generation / 生成回溯 ID
- template_extraction 22 个测试无回归

#### 验收报告落地（对照 template_extraction_result_check 建议项）

- **promoted 门禁**：`OpportunityToPlanFlow.build_brief` 仅当 `opportunity_status == "promoted"` 继续，否则抛出 `OpportunityNotPromotedError`；API 映射为 **403**（[exceptions.py](apps/content_planning/exceptions.py)、[routes.py](apps/content_planning/api/routes.py)）。
- **API 文档 + 无前缀别名**：主路径仍为 `/content-planning/...`；另注册 **兼容路由** `POST /xhs-opportunities/{id}/generate-brief|generate-note-plan`。说明见 [docs/CONTENT_PLANNING_API.md](docs/CONTENT_PLANNING_API.md)。请求体增加 `mode: plan_only | full`（`full` 等价开启生成）。
- **C1 脚本**：[apps/content_planning/scripts/run_acceptance_c1.py](apps/content_planning/scripts/run_acceptance_c1.py)（最多 12 条 promoted，输出 Markdown 表，可选 `--with-generation`）。
- **C2 脚本与索引**：[apps/content_planning/scripts/export_golden_cases.py](apps/content_planning/scripts/export_golden_cases.py) 导出 JSON 至 `data/exports/content_planning/`（已 gitignore），索引 [docs/content_planning_golden_cases.md](docs/content_planning_golden_cases.md)。
- **生成结果回溯**：`TitleGenerationResult` / `BodyGenerationResult` / `ImageBriefGenerationResult` 增加 `opportunity_id` / `brief_id` / `strategy_id` / `template_id`，由 [plan_trace.py](apps/content_planning/utils/plan_trace.py) 统一从 `NewNotePlan` 填充。

---

### 内容策划工作台升级 V2.0（2026-04-07）

基于 `docs/content_pipeline.md` 的 P0-P7 升级方案和 `docs/template_extaction_workstation_prd.md` 的四页工作台 PRD，将后端从"仅 API"升级为完整工作台。

#### Phase 1: 后端升级

- **RewriteStrategy schema 对齐 PRD**：增加 `strategy_status`、`hook_strategy`、`cta_strategy`、`scene_emphasis`、`rationale` 字段
- **OpportunityBrief schema 增强**：增加 `brief_status`、`target_audience`、`evidence_summary`、`constraints`、`suggested_direction`、`updated_at` 字段
- **BriefCompiler review_summary 集成**：从检视摘要提取 `proof_from_source` 补充、`evidence_summary` 构建、`constraints` 提取、`suggested_direction` 生成；高质量评分影响 `content_goal` 表达
- **strategy_generator LLM 增强**：`_llm_enhance` 从空实现升级为调用 `call_text_llm` 润色策略文案（graceful degradation），增加 `hook_strategy`/`cta_strategy`/`scene_emphasis`/`rationale` 生成
- **OpportunityToPlanFlow 会话缓存**：内存 `_SessionState` 管理中间产物（brief/match/strategy/plan/generation），支持阶级失效、局部重生成
- **新增原子方法**：`match_templates()`、`build_strategy()`、`build_plan()`、`regenerate_titles()`/`body()`/`image_briefs()`、`update_brief()`、`compile_note_plan()`、`get_session_data()`

#### Phase 2: 原子 API

新增端点（[routes.py v2](apps/content_planning/api/routes.py)）：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/content-planning/xhs-opportunities/{id}/match-templates` | 模板匹配 |
| POST | `/content-planning/xhs-opportunities/{id}/generate-strategy` | 生成策略（可指定模板） |
| POST | `/content-planning/xhs-opportunities/{id}/generate-titles` | 局部重生成标题 |
| POST | `/content-planning/xhs-opportunities/{id}/generate-body` | 局部重生成正文 |
| POST | `/content-planning/xhs-opportunities/{id}/generate-image-briefs` | 局部重生成图片指令 |
| PUT | `/content-planning/briefs/{id}` | Brief 人工编辑 |
| POST | `/content-planning/xhs-opportunities/{id}/compile-note-plan` | 一键全链路 |
| GET | `/content-planning/session/{id}` | 会话缓存查询 |
| POST | `/content-planning/run-agent/{id}` | 运行指定 Agent（`agent_role` + `extra`），返回解释/置信度/suggestions |
| GET | `/content-planning/agent-log/{id}` | 某机会的 Agent 动作日志（依赖 `plan_store.agent_actions_json`） |
| GET | `/content-planning/agents` | 已注册 Agent 目录（registry 非空时优先返回 registry） |

四页工作台模板内增加 `runAgent(role, extra)`，请求上述 `run-agent` 端点。

#### Phase 3: 四页工作台 UI

- **机会池页升级**：promoted 快捷入口按钮 + 每张 promoted 卡增加"生成 Brief"和"一键策划"按钮
- **Brief 确认页** (`content_brief.html`)：三栏布局（来源上下文 / Brief 结构化展示 / 人工修订区），支持保存编辑、重新生成、下一步跳转
- **模板与策略页** (`content_strategy.html`)：top3 模板候选卡片 + RewriteStrategy 全字段展示，支持模板切换和策略重生成
- **内容策划页** (`content_plan.html`)：三栏布局（上下文 / NewNotePlan 三维策划 / 生成结果 tab），支持标题/正文/图片指令独立重生成，支持 JSON/Markdown 导出
- **导航串联**：`base.html` 增加"内容策划"入口，四页通过面包屑 + 下一步按钮串联

#### Phase 4: 验收

- **端到端验收脚本** (`run_e2e_acceptance.py`)：自动选取 promoted 卡，逐步验证 Brief → 模板匹配 → 策略 → 策划方案 → 标题/正文/图片生成 → 回溯链路，输出结果到 `data/exports/content_planning/`
- **文档更新**：`CONTENT_PLANNING_API.md` v2（完整 API 路由、请求体、工作台流程、curl 示例）

---

### 洞察层升级 V0.8（2026-04-07）

**目标**：为机会卡和 Brief 补充深度洞察字段，消费上游已有的互动数据和跨模态校验结果。

#### 机会卡（发现层洞察）

- **Schema** (`apps/intel_hub/schemas/opportunity.py`)：新增 `engagement_insight`、`cross_modal_verdict`、`insight_statement` 三个字段
- **编译器** (`apps/intel_hub/compiler/opportunity_compiler.py`)：
  - `compile_xhs_opportunities` 签名新增 `note_context` 参数
  - 新增 `_build_engagement_insight`：从互动量计算藏赞比和评论率，输出"X 收藏 / Y 赞 / 藏赞比 Z — 强/中/低收藏属性"
  - 新增 `_build_cross_modal_verdict`：统计 high_confidence / unsupported / challenged 卖点数量，输出验证结论
  - 新增 `_build_insight_statement`：综合互动标签、核心场景/卖点和验证状况，生成一句话运营洞察
- **流水线** (`apps/intel_hub/workflow/xhs_opportunity_pipeline.py`)：传入 `note_context`（like/collect/comment/share）

#### Brief（策划层洞察）

- **Schema** (`apps/content_planning/schemas/opportunity_brief.py`)：新增 `why_worth_doing`、`competitive_angle`、`engagement_proof`、`cross_modal_confidence_label` 四个字段
- **编译器** (`apps/content_planning/services/brief_compiler.py`)：
  - 新增 `_build_why_worth_doing`：结合互动量级、卖点验证比例和人工检视评分生成"为什么值得做"判断句
  - 新增 `_build_competitive_angle`：从 high_confidence_claims 和 challenged_claims 构建差异化切入建议
  - 新增 `_build_engagement_proof`：格式化互动数据佐证句
  - 新增 `_build_cross_modal_confidence_label`：基于 overall_consistency_score 输出高/中/低置信标签
  - 升级 `_infer_content_goal`：根据互动数据特征追加"收藏驱动"/"讨论驱动"标签，根据跨模态一致性追加"已验证"标签

#### UI 适配

- **机会卡列表页** (`xhs_opportunities.html`)：insight_statement 显示为高亮卡片首行，engagement_insight 和 cross_modal_verdict 显示为彩色标签
- **机会卡详情页** (`xhs_opportunity_detail.html`)：标题下方新增洞察区域（insight_statement 高亮框 + 两个信息标签）
- **Brief 确认页** (`content_brief.html`)：中栏新增"策划层洞察"面板（why_worth_doing / competitive_angle / engagement_proof / 置信标签 badge），右栏支持编辑"为什么值得做"和"差异化切入"

#### 测试

- 编译器测试新增 `TestInsightBuilders` 类（5 个用例）和 `test_insight_fields_populated`
- Brief 编译器测试新增 5 个洞察相关用例（含完整数据、空数据、置信标签三档）
- 全量 231 项测试通过

---

### 标签中文化 + LLM 调试信息升级 V0.9

#### 问题

Brief 和机会卡中大量字段使用英文本体 ID（`scene_dining_table`、`style_creamy`、`need_waterproof` 等），对运营用户不友好。`strategy_generator._llm_enhance` 的 `call_text_llm` 调用只传一个参数导致 TypeError 被静默吞掉，LLM 润色从未生效。LLM 调用无 debug 日志，无法排查 prompt/response。

#### 变更

##### 中文映射模块
- **新增** `apps/intel_hub/projector/label_zh.py`：从 `config/ontology_mapping.yaml` 的 `keywords[0]` 自动提取中英映射，硬编码补充 template_hints / vp_* / type / status 等无法从 YAML 推导的映射
  - `to_zh(ref_id)`: 单个翻译，支持 `+` 组合串拆分翻译
  - `to_zh_list(ref_ids)`: 批量翻译

##### 机会卡中文化
- `apps/intel_hub/compiler/opportunity_compiler.py`：
  - 视觉卡 title 中 `mapping.scene_refs` 引用改为 `to_zh(r)` 输出
  - `_build_insight_statement` 中 `core_subject` 从 scene/need/style refs 取值时使用 `to_zh`

##### Brief 中文化
- `apps/content_planning/services/brief_compiler.py`：
  - `compile()` 中 `opportunity_type`、`core_motive`、`primary_value`、`price_positioning` 调用 `to_zh`
  - `target_user`、`target_scene`、`visual_style_direction`、`secondary_values`、`avoid_directions`、`template_hints` 调用 `to_zh_list`
  - `_extract_constraints` 中 `risk_refs` 调用 `to_zh`
  - `_build_target_audience` 中 `audience_refs` 调用 `to_zh`
  - `opportunity_title`、`opportunity_summary` 通过正则 `_zh_replace_refs` 替换嵌入的英文 ref ID

##### LLM Bug 修复
- `apps/content_planning/services/strategy_generator.py`：修复 `_llm_enhance` 中 `call_text_llm(prompt)` 为 `call_text_llm("你是小红书内容策略专家。", prompt)`，解决参数缺失导致的 TypeError

##### LLM 调试日志
- `apps/intel_hub/extraction/llm_client.py`：
  - `call_text_llm`: 增加 `[LLM-REQ]` / `[LLM-OK]` / `[LLM-ERR]` / `[LLM-EXC]` debug 日志，记录 model、elapsed、prompt (前 800 字)、response (前 500 字)、tokens
  - `call_vlm`: 增加 `[VLM-REQ]` / `[VLM-OK]` / `[VLM-ERR]` / `[VLM-EXC]` debug 日志
  - `parse_json_response`: 成功时记录 `[JSON-OK]` keys，失败时记录 `[JSON-ERR]`
  - 设置 `LOG_LEVEL=DEBUG` 即可查看完整 LLM 交互

##### 测试适配
- `apps/content_planning/tests/test_brief_compiler.py`：`opportunity_type` 断言改为 `"视觉"`，template_hints 断言改为中文标签（`"风格定锚"` / `"质感佐证"` / `"场景种草"`）
- 全量 32 项测试通过

---

### LLM 驱动模板匹配 + 策略生成升级 V1.0

#### 问题

- 模板匹配基于纯子串 `in` 关键词碰撞，权重硬编码，无语义理解，区分度低（多个模板经常同分）
- 策略生成全靠 `f"..."` 模板字符串拼接，输出千篇一律，LLM 只润色 5 个字段措辞

#### 变更

##### A. LLM 驱动模板匹配
- `apps/template_extraction/agent/template_matcher.py`：
  - 新增 `_try_llm_match` 方法：一次 LLM 调用评估全部模板，输入 Brief 摘要 + 6 套模板关键属性，输出 `[{template_id, score(0-100), reason}]` JSON
  - 新增 `_build_brief_summary` / `_build_templates_summary` / `_parse_llm_scores` 辅助方法
  - `match_templates` 增加 LLM 优先路径：有 brief 时先尝试 LLM，失败/不可用时 fallback 到现有规则打分
  - 打分标准嵌入 prompt：场景契合度 30%、内容目标匹配 25%、风格一致性 20%、钩子机制适配 15%、规避冲突扣分 10%

##### B. LLM 主导策略生成
- `apps/content_planning/services/strategy_generator.py`：
  - `generate()` 从"规则生成 + LLM 润色"重构为"LLM 生成全部字段 + 规则校验兜底"
  - 新增 `_try_llm_generate`：构建约束清单（Brief 信息 + 模板属性 + 匹配信息）+ JSON schema hint，一次 LLM 调用生成 RewriteStrategy 全部字段
  - 新增 `_merge_llm_with_fallback`：LLM 输出的有效字段优先，缺失字段用规则兜底填充
  - 规则层 `_rule_based_generate` 完整保留作为 fallback，LLM 不可用时整体降级

##### 向后兼容
- `MatchResult` / `RewriteStrategy` schema 不变，下游无感知
- flow 层和 API 路由零改动
- `DASHSCOPE_API_KEY` 缺失或 LLM 异常时两个模块均 graceful fallback 到规则逻辑

##### 测试
- 全量 35 项测试通过（LLM 不可用时自动走规则路径验证）

---

### Batch 1：决策编译层生产化基础（2026-04-08）

目标：把已有编译链做成可持久化、可回溯、可版本化的生产级骨架。

#### 1.1 会话持久化与对象落库

- **新增** `apps/content_planning/storage/plan_store.py` — `ContentPlanStore` 类
  - SQLite 表 `planning_sessions`：`opportunity_id` PK + `session_status` + 7 个 `*_json` 列 + `pipeline_run_id` + `stale_flags_json` + `created_at` / `updated_at`
  - UPSERT 语义：非 None 字段才更新
  - `save_session` / `load_session` / `update_field` / `update_stale_flags` / `list_sessions` / `delete_session` / `session_count`
- **改造** `apps/content_planning/services/opportunity_to_plan_flow.py`：
  - `OpportunityToPlanFlow.__init__` 接受可选 `plan_store` 参数
  - `_get_session` 先查内存缓存 → SQLite → 新建
  - 每步操作完成后调用 `_persist()` 写回 SQLite
  - 新增 `stale_flags` 状态追踪 + `_mark_fresh` 方法
- **改造** `apps/intel_hub/api/app.py`：初始化 `ContentPlanStore` 并注入 Flow

#### 1.2 pipeline_run_id / lineage / version chain

- **新增** `apps/content_planning/schemas/lineage.py` — `PlanLineage` 模型
  - 字段：`pipeline_run_id` / `source_note_ids` / `opportunity_id` / `review_id` / `brief_id` / `template_id` / `strategy_id` / `plan_id` / `parent_version_id` / `derived_from_id` / `created_at`
- **修改** 6 个 schema 增加 `lineage: PlanLineage | None = None`：
  - `OpportunityBrief` / `RewriteStrategy` / `NewNotePlan` / `TitleGenerationResult` / `BodyGenerationResult` / `ImageBriefGenerationResult`
- **修改** `XHSOpportunityCard`：增加 `pipeline_run_id: str | None = None`
- **Flow 传递**：`build_brief` / `build_strategy` / `build_plan` / `regenerate_*` 均构建 lineage 并挂载

#### 1.3 Prompt Registry / Prompt 配置化

- **新增** `apps/content_planning/services/prompt_registry.py` — `load_prompt(scene, variant)` + YAML 缓存
- **新增** 5 个 YAML 配置：
  - `config/prompts/strategy.yaml` / `title.yaml` / `body.yaml` / `image_brief.yaml` / `template_match.yaml`
- **改造** 5 个 service 从 registry 加载 prompt：
  - `strategy_generator.py` / `title_generator.py` / `body_generator.py` / `image_brief_generator.py` / `template_matcher.py`
- 行为完全不变，只做结构性抽离

#### 验证

- 全量 209 项测试通过
- 所有 import 正常
- 向后兼容：所有新字段默认 None，旧数据不受影响

---

### Batch 2：决策编译层增强（2026-04-08）

目标：让机会卡、Brief、Strategy、TemplateMatcher 更强、更可审阅。

#### 2.1 机会卡增强

- **Schema**：`XHSOpportunityCard` 新增 `action_recommendation: str | None` + `opportunity_strength_score: float | None`
- **编译器**：`_build_action_recommendation`（基于 opportunity_type + confidence + engagement 生成运营建议句）、`_build_strength_score`（加权公式 confidence 40% + engagement 30% + cross_modal 30%）
- 使用真实互动数据（like/collect/comment/share）

#### 2.2 BriefCompiler 升级

- **Schema**：`OpportunityBrief` 新增 `why_now` / `differentiation_view` / `proof_blocks: list[dict]` / `planning_direction`
- **编译器**：4 个新 builder（`_build_why_now` / `_build_differentiation_view` / `_build_proof_blocks` / `_build_planning_direction`）
- `proof_blocks` 结构化为 `{"type": "engagement"|"visual"|"validation"|"review", "content": ..., "source": ...}`
- `planning_direction` 为模板匹配和策略生成提供直接输入

#### 2.3 TemplateMatcher 多候选与解释增强

- **Schema**：`TemplateMatchEntry` 新增 `matched_dimensions: dict[str, float] | None`（scene/goal/style/hook/avoid 各维度分）
- `MatchResult` 增加 `matched_dimensions` 属性
- `_score_with_brief` 追踪各维度得分并返回
- Flow 层构建 `TemplateMatchEntry` 时传递维度分

#### 2.4 RewriteStrategy 增强为可对比对象

- **Schema**：`RewriteStrategy` 新增 `strategy_version: int = 1` / `comparison_note: str | None` / `editable_blocks: list[str] | None`
- `_merge_llm_with_fallback` 自动生成 comparison_note（标注 LLM 优化了哪些字段）
- `editable_blocks` 列出所有可编辑字段名

#### 验证

- 全量 209 项测试通过
- 所有新字段向后兼容（默认 None / 空值）

---

### Batch 3：对象交互层工作台化（2026-04-08）

目标：把当前流程页升级成对象化工作台。

#### 3.1 重构工作台信息架构

- 三工作台重命名与定位：
  - `content_brief.html` → **机会工作台**：机会上下文 + Brief 编辑 + 操作面板
  - `content_strategy.html` → **策划工作台**：Brief 摘要 + 模板匹配 + 策略详情
  - `content_plan.html` → **资产工作台**：策略摘要 + 内容生成结果 + 导出操作
- 已有三栏布局保持不变（左30%/中45%/右25%）

#### 3.2 局部失效与局部重算显式化

- `_SessionState` 增加 `stale_flags: dict[str, bool]`（7 个 key）
- `invalidate_downstream` 自动更新 stale_flags
- `_mark_fresh` 在每步完成后标记为新鲜
- `_persist` 每步写回 stale_flags 到 SQLite
- 三个工作台页面 API 返回 stale_flags
- 前端显示状态标记：绿色 ✓ / 红色 ⟳

#### 3.3 多策略对比视图支撑

- `ContentPlanStore` 新增 `save_strategy` / `load_strategies` 方法
- `strategy_json` 支持 list 存储，向后兼容 dict
- API 新增 `GET /content-planning/strategies/{opportunity_id}`

#### 3.4 图位级对象化

- `ImageSlotPlan` 增加 `slot_id: str`（uuid 前 8 位）+ `slot_version: int = 1`
- API 新增 `POST /content-planning/xhs-opportunities/{opportunity_id}/regenerate-image-slot/{slot_index}`
- 单图位查询返回指定槽位的 brief

#### 验证

- 全量 209 项测试通过
- stale_flags 在三个工作台页面正确渲染

---

### Batch 4：资产生产层资产包化（2026-04-08）

目标：标题/正文/图片统一为可导出资产包。

#### 4.1 AssetBundle 统一对象

- **新增** `apps/content_planning/schemas/asset_bundle.py` — `AssetBundle` schema
  - 字段：`asset_bundle_id` / `plan_id` / `opportunity_id` / `template_id` / `template_name` / `title_candidates` / `body_outline` / `body_draft` / `image_execution_briefs` / `export_status` / `lineage` / `created_at`
- **新增** `apps/content_planning/services/asset_assembler.py` — `AssetAssembler.assemble()`
  - 从 `TitleGenerationResult` / `BodyGenerationResult` / `ImageBriefGenerationResult` 组装 AssetBundle
  - 自动判断 export_status（有标题+正文 → ready，否则 draft）
- **Flow 集成**：`OpportunityToPlanFlow.assemble_asset_bundle()` 方法
- **API**：`GET /content-planning/asset-bundle/{opportunity_id}`

#### 4.2 导出层

- **新增** `apps/content_planning/services/asset_exporter.py` — `AssetExporter`
  - `export_json(bundle)` → JSON 字典
  - `export_markdown(bundle)` → 运营文档 Markdown
  - `export_image_package(bundle)` → 设计团队结构化指令
- **API**：`GET /content-planning/asset-bundle/{id}/export?format=json|markdown|image_package`

#### 4.3 批量内容资产生产

- **Flow**：`OpportunityToPlanFlow.batch_compile(opportunity_ids)` 方法
  - 支持部分成功/部分失败
  - 返回 `{succeeded: list[AssetBundle], failed: list[{id, error}], total}`
- **API**：`POST /content-planning/batch-compile`

#### 验证

- 全量 209 项测试通过
- AssetBundle / Assembler / Exporter 类型检查通过

---

### Batch 5：批量化、异步化、反馈闭环（2026-04-08）

目标：让系统进入生产环境可持续运行。

#### 5.1 异步并行生成

- `_run_generation` 从串行改为 `ThreadPoolExecutor(max_workers=3)` 并行
  - 三路 LLM 调用（标题/正文/图片）同时执行
  - 某一路失败不影响其他，错误信息写入 `_generation_errors`
  - 超时 60 秒
- 使用 ThreadPoolExecutor 而非 asyncio（因为 LLM 客户端是同步的）

#### 5.2 运营看板基础指标

- **新增** `apps/content_planning/services/dashboard_metrics.py` — `DashboardMetrics`
  - `opportunity_pool`：总量 / 已检视 / 已 promote / promote 率 / 平均质量分
  - `planning_pipeline`：总会话数 / 已生成数 / 已导出数 / 生成率
  - `template_distribution`：按类型分布
- **API**：`GET /content-planning/dashboard`

#### 5.3 效果回流闭环

- **新增** `apps/content_planning/schemas/feedback.py`
  - `PublishedAssetResult`：发布效果数据
  - `EngagementResult`：互动效果快照
  - `TemplateEffectivenessRecord`：模板有效性记录
- **API**：`POST /content-planning/asset-bundle/{id}/feedback`
  - 接收效果数据，构建 `PublishedAssetResult`
  - 数据结构先做好，暂不做自动学习

#### 验证

- 全量 209 项测试通过
- 所有新模块 import 验证通过
- ContentPlanStore CRUD 验证通过
- PromptRegistry YAML 加载验证通过
- Schema lineage 字段验证通过

---

### 五批升级总结

| Batch | 目标 | 状态 |
|-------|------|------|
| 1 | 决策编译层生产化基础（持久化/血缘/Prompt配置化） | ✅ 完成 |
| 2 | 决策编译层增强（机会卡/Brief/Strategy/Matcher 升级） | ✅ 完成 |
| 3 | 对象交互层工作台化（三工作台/stale_flags/多策略/图位） | ✅ 完成 |
| 4 | 资产生产层资产包化（AssetBundle/导出/批量编译） | ✅ 完成 |
| 5 | 批量化、异步化、反馈闭环（并行生成/看板/回流） | ✅ 完成 |

新增文件：
- `apps/content_planning/schemas/lineage.py`
- `apps/content_planning/schemas/asset_bundle.py`
- `apps/content_planning/schemas/feedback.py`
- `apps/content_planning/storage/plan_store.py`
- `apps/content_planning/services/prompt_registry.py`
- `apps/content_planning/services/asset_assembler.py`
- `apps/content_planning/services/asset_exporter.py`
- `apps/content_planning/services/dashboard_metrics.py`
- `config/prompts/strategy.yaml`
- `config/prompts/title.yaml`
- `config/prompts/body.yaml`
- `config/prompts/image_brief.yaml`
- `config/prompts/template_match.yaml`

---

## AI-native 产品层升级 — Phase 1：对象模型增强 + Agent 基础设施

### 日期：2026-04-07

### 目标
补齐 G1（锁定）/G2（变体）/G3（Agent 抽象）/G6（多版本），为后续工作台页面提供数据与 Agent 基础。

### 1.4 Agent 抽象层 ✅

新增 `apps/content_planning/agents/` 目录：

| 文件 | 角色 | 包装的 Service |
|------|------|----------------|
| `base.py` | 基类 + AgentChip / AgentContext / AgentResult | — |
| `registry.py` | AgentRegistry（注册/发现/按角色查找） | — |
| `trend_analyst.py` | 趋势分析师 (trend_analyst) | opportunity_compiler + promoter |
| `brief_synthesizer.py` | Brief 编译师 (brief_synthesizer) | BriefCompiler |
| `template_planner.py` | 模板策划师 (template_planner) | TemplateMatcher + TemplateRetriever |
| `strategy_director.py` | 策略总监 (strategy_director) | RewriteStrategyGenerator |
| `visual_director.py` | 视觉总监 (visual_director) | ImageBriefGenerator + NewNotePlanCompiler |
| `asset_producer.py` | 资产制作人 (asset_producer) | TitleGenerator + BodyGenerator + AssetAssembler |

Agent 层是 service 的包装层，不改变现有 service 逻辑。

### 1.1 对象锁定机制 ✅

- 新增 `apps/content_planning/schemas/lock.py` — `ObjectLock` 模型
- `OpportunityBrief` / `RewriteStrategy` / `NewNotePlan` / `AssetBundle` 增加 `locks: ObjectLock | None`
- API: `POST /content-planning/lock/{opp_id}` / `POST /content-planning/unlock/{opp_id}`

### 1.2 并行多版本存储 ✅

- `planning_sessions` 表增加 `brief_versions_json` / `strategy_versions_json` / `plan_versions_json`
- `append_version` / `load_versions` 方法（保留最新 10 个快照）
- API: `GET /content-planning/versions/{opp_id}/{type}` / `POST /content-planning/restore-version/{opp_id}`

### 1.3 变体系统骨架 ✅

- 新增 `apps/content_planning/schemas/variant.py` — `Variant` / `VariantSet`
- 新增 `apps/content_planning/services/variant_generator.py`
- `AssetBundle` 增加 `variant_set_id`
- API: `POST /content-planning/asset-bundle/{opp_id}/generate-variant`

### Phase 1 验证

- 全量导入验证：6 个 Agent + Lock + Variant + VariantGenerator 全部 OK
- 测试：235 passed, 0 failed

---

## AI-native 产品层升级 — Phase 2：4 个工作台页面重构

### 日期：2026-04-07

### 目标
把现有 3 个"步骤页"重构为 4 个"对象工作台"，补齐 G5（Board 视图）/ G7（AI chips）/ G8（交互增强）。

### 2.1 Opportunity Workspace ✅

重构 `content_brief.html` → 三栏 Opportunity Workspace：
- 对象锚点栏（Card ID/类型/状态/强度分/Pipeline）
- AI 建议 chips（值得深入/建议观望/适合种草/适合转化）
- 左栏：机会卡摘要 + 检视汇总 + 来源笔记
- 中栏：Brief 全量内容（含策划层洞察）
- 右栏：AI 分析建议 + 人工修订表单 + 锁定按钮 + 版本历史 + CTA

### 2.2 Planning Workspace ✅

重构 `content_strategy.html` → 三栏 Planning Workspace：
- 对象锚点链路（Card → Brief → Template → Strategy）
- 左栏：Brief 摘要 + 场景受众 + 策划深度（why_now/differentiation/planning_direction）
- 中栏：Top 3 模板卡片（含 matched_dimensions）+ 双列策略展示
- 右栏：AI 策划建议 + Strategy AI Chips（更偏种草/转化/礼赠/平价改造）+ 操作区 + 版本历史

### 2.3 Creation Workspace ✅

重构 `content_plan.html` → 三栏 Creation Workspace：
- 对象锚点（完整链路 Card → Brief → Strategy → Plan）
- 左栏：机会/模板/策略摘要上下文
- 中栏：Plan Board（A. 标题策划 + 生成标题、B. 正文策划 + 生成正文、C. 图片策划 + 生成图片指令）
- 右栏：AI 创作分析 + 标题/图片 AI Chips + 操作按钮 + 资产包链接

### 2.4 Asset Workspace ✅ (新增)

新增 `content_assets.html` + 路由 `GET /content-planning/assets/{opportunity_id}`：
- 对象锚点（Brief → Strategy → Plan → Asset Bundle）
- 左栏：资产包信息 + 血缘链路可视化 + Brief/策略摘要
- 中栏：Tab 视图（标题候选 / 正文 / 图片执行 Brief / 变体）
- 右栏：Agent 说明 + 导出 JSON/Markdown + 生成变体 + 标记已发布

### Phase 2 验证

- 测试：235 passed, 0 failed
- App 路由数：66（含新增 Asset Workspace 路由）
- 全量导入验证通过

---

## AI-native 产品层升级 — Phase 3：AI 角色协同层

### 日期：2026-04-07

### 目标
让 Agent 不只是包装层，而是真正的协同参与者（G3 运行时），前端可调用 Agent、查看解释、记录动作轨迹。

### 3.1 Agent 运行与解释 ✅

- 新增 `POST /content-planning/run-agent/{opportunity_id}` — 按 agent_role 实例化 Agent 并运行
- 返回 `AgentResult`（output_object + explanation + confidence + suggestions/chips + comparison）
- 运行后自动记录动作日志

### 3.2 Agent 动作日志 ✅

- `planning_sessions` 表增加 `agent_actions_json` 列
- `_log_agent_action` 自动追加每次 Agent 运行记录（保留最近 50 条）
- `GET /content-planning/agent-log/{opportunity_id}` — 查看 Agent 动作轨迹
- `GET /content-planning/agents` — 列出所有 Agent（6 个角色）

### 3.3 人类 + AI 动作分区 ✅

- 4 个工作台页面右栏已明确分为 AI 可做区（agent-box、chips）和人可做区（表单、按钮）
- 前端 `runAgent(role, extra)` 函数已注入所有 4 个工作台模板
- Agent 运行结果可直接在 AI 分析区域展示

### Phase 3 验证

- 测试：235 passed, 0 failed
- Agent API 导入验证通过
- agent_actions 存储列迁移兼容

---

## AI-native 产品层升级 — Phase 4：品类解耦 + Campaign 级生产

### 日期：2026-04-07

### 目标
解耦品类硬编码（G4），支持 Campaign 级批量生产扩展结构。

### 4.1 品类配置抽象 ✅

- 新增 `config/categories/tablecloth.yaml` — 桌布品类完整配置
  - `extractor_hints`（visual/selling_theme/scene）
  - `ontology_overrides`
  - `template_family`
  - `prompt_fragments`（category_context / visual_style_guide）
  - `brand_defaults`
- PromptRegistry 升级为三级加载：`load_prompt(scene, variant, category)`
  - scene YAML → variant 选择 → category prompt_fragments 注入
  - 新增 `load_category(category)` / `load_prompt_with_category(...)` 辅助函数
  - 品类片段通过 `{category_context}` 等占位符注入 prompt template
  - 向后兼容：无 category 参数时行为不变

### 4.2 Campaign 级批量生产 ✅

- 新增 `apps/content_planning/schemas/campaign.py`
  - `PlatformVersion`（xiaohongshu/ecommerce_main/sku/video_script）
  - `CampaignPlan`（campaign_id + opportunity_ids + target_bundle_count + platform_versions）
  - `CampaignResult`（total/completed/failed bundles + platform_versions_generated）
- API: `POST /content-planning/campaigns` — 创建 Campaign 计划
- API: `POST /content-planning/campaigns/{campaign_id}/execute` — 执行 Campaign（概念验证）
- `AssetBundle.campaign_id` 已存在，可关联 Campaign

### Phase 4 验证

- 测试：235 passed, 0 failed
- 品类配置加载验证：tablecloth YAML 正确读取
- Campaign schema 验证：CampaignPlan / CampaignResult 构建成功

---

## 四阶段升级总结

| Phase | 目标 | 状态 |
|-------|------|------|
| 1 | 对象模型增强 + Agent 基础设施（锁定/多版本/变体/Agent 抽象） | ✅ 完成 |
| 2 | 4 个工作台页面重构（Opportunity/Planning/Creation/Asset） | ✅ 完成 |
| 3 | AI 角色协同层（Agent 运行/动作日志/人机分区） | ✅ 完成 |
| 4 | 品类解耦 + Campaign 级生产（categories YAML/三级加载/Campaign API） | ✅ 完成 |

新增文件：
- `apps/content_planning/agents/__init__.py`
- `apps/content_planning/agents/base.py`
- `apps/content_planning/agents/registry.py`
- `apps/content_planning/agents/trend_analyst.py`
- `apps/content_planning/agents/brief_synthesizer.py`
- `apps/content_planning/agents/template_planner.py`
- `apps/content_planning/agents/strategy_director.py`
- `apps/content_planning/agents/visual_director.py`
- `apps/content_planning/agents/asset_producer.py`
- `apps/content_planning/schemas/lock.py`
- `apps/content_planning/schemas/variant.py`
- `apps/content_planning/schemas/campaign.py`
- `apps/content_planning/services/variant_generator.py`
- `apps/intel_hub/api/templates/content_assets.html`
- `config/categories/tablecloth.yaml`

新增路由：
- `POST /content-planning/lock/{opportunity_id}`
- `POST /content-planning/unlock/{opportunity_id}`
- `GET /content-planning/versions/{opportunity_id}/{object_type}`
- `POST /content-planning/restore-version/{opportunity_id}`
- `POST /content-planning/asset-bundle/{opportunity_id}/generate-variant`
- `POST /content-planning/run-agent/{opportunity_id}`
- `GET /content-planning/agent-log/{opportunity_id}`
- `GET /content-planning/agents`
- `GET /content-planning/assets/{opportunity_id}` (HTML)
- `POST /content-planning/campaigns`
- `POST /content-planning/campaigns/{campaign_id}/execute`

---

## DeerFlow + Hermes Agent 融合升级（2026-04-09）

### 概述
将 DeerFlow 和 Hermes Agent 核心能力融合到内容策划 Agent 体系：
- Multi-LLM Provider 统一路由（DashScope/OpenAI/Anthropic）
- 端到端评价体系（5 环节 LLM-as-Judge + 管线聚合指标）
- LLM-driven LeadAgent 路由（替代纯关键词匹配，带 graceful degradation）
- PlanGraph 执行引擎（按依赖拓扑异步编排多 Agent）
- 6 个 Sub-Agent LLM + Memory 增强
- 多 Agent 阶段讨论（DiscussionOrchestrator）
- 学习闭环（高分讨论自动提取 Skill，低分写入教训）
- Before/After 评价对比报告

### 新增文件（15 个）

**适配器层（`apps/content_planning/adapters/`）：**
- `__init__.py` — 适配器入口
- `llm_router.py` — Multi-LLM 路由（DashScope + OpenAI + Anthropic）
- `deerflow_adapter.py` — DeerFlow 能力适配（LLM 路由/结果合成/技能加载/记忆召回）
- `hermes_adapter.py` — Hermes 能力适配（轨迹压缩/经验提取/Memory Nudge/教训写入）

**评价体系（`apps/content_planning/evaluation/`）：**
- `__init__.py` — 评价模块入口
- `stage_evaluator.py` — 5 环节 LLM-as-Judge 评估器
- `pipeline_metrics.py` — 管线聚合指标
- `comparison.py` — Before/After 对比 + 学习闭环

**Agent 层：**
- `agents/graph_executor.py` — PlanGraph 异步执行引擎
- `agents/discussion.py` — 多 Agent 阶段讨论协调器

**Schema / 配置：**
- `schemas/evaluation.py` — 评价 Schema（StageEvaluation / PipelineEvaluation）
- `config/prompts/evaluation.yaml` — 5 阶段评分 Prompt + 维度/权重定义

**第三方（`third_party/`）：**
- `.gitmodules` — 声明 deer-flow + hermes-agent submodule
- `third_party/deer-flow/README.md` — Submodule 占位
- `third_party/hermes-agent/README.md` — Submodule 占位

### 修改文件（12 个）

- `pyproject.toml` — 新增 `llm-openai` / `llm-anthropic` / `llm-all` 可选依赖
- `agents/lead_agent.py` — LLM-driven 路由（_route_llm）+ 关键词降级 + 多 Agent 建议
- `agents/trend_analyst.py` — LLM 增强 + Memory 注入
- `agents/brief_synthesizer.py` — LLM 增强 + Memory 注入
- `agents/template_planner.py` — LLM 增强 + Memory 注入
- `agents/strategy_director.py` — LLM 增强 + Memory 注入
- `agents/visual_director.py` — LLM 增强 + Memory 注入
- `agents/asset_producer.py` — LLM 增强 + Memory 注入
- `agents/memory.py` — 新增 `inject_context()` 方法
- `api/routes.py` — 新增 5 个端点
- `storage/plan_store.py` — 新增 evaluations 表 + save/load 方法
- `schemas/__init__.py` — 导出 evaluation schemas

### 新增 API 端点

- `POST /content-planning/discuss/{opportunity_id}` — 多 Agent 讨论
- `POST /content-planning/evaluate/{opportunity_id}` — 端到端评价
- `GET /content-planning/evaluation/{opportunity_id}` — 获取评价结果
- `POST /content-planning/baseline/{opportunity_id}` — 采集 baseline
- `POST /content-planning/compare/{opportunity_id}` — Before/After 对比

### 架构要点

- **Graceful Degradation**：所有 LLM 增强均带降级——LLM 不可用时回退到规则模式，行为与升级前一致
- **无新外部依赖**：核心功能不依赖 LangGraph/LangChain；OpenAI/Anthropic SDK 为可选安装
- **Adapter Pattern**：DeerFlow/Hermes 理念通过 Adapter 层桥接，不直接导入第三方框架代码
- **循环导入防护**：LeadAgent 对 DeerFlowAdapter 采用延迟导入避免循环依赖

---

## Sprint 0 + Phase 2 / 3：Stage Workflow（2026-04-09）

### 本轮完成

- 将 `third_party/hermes-agent` 上游源修正为 `NousResearch/hermes-agent`
- 新增 `third_party/UPSTREAM.md`，明确 DeerFlow / Hermes 的本地职责边界
- 新增统一 stage workflow schema：
  - `AgentTask`
  - `AgentRun`
  - `AgentSessionRef`
  - `AgentDiscussionRecord`
  - `StageProposal`
  - `ProposalDiff`
  - `ProposalDecision`
  - `StageScorecard`
- `ContentPlanStore` 新增独立表：
  - `agent_tasks`
  - `agent_runs`
  - `stage_discussions`
  - `stage_proposals`
  - `proposal_decisions`
- 评价结果不再只临时返回；`stage_run / baseline / comparison / pipeline` 均可落入 `evaluations`
- 新增通用 stage API：
  - `POST /content-planning/stages/{stage}/{opportunity_id}/discussions`
  - `GET /content-planning/discussions/{discussion_id}`
  - `GET /content-planning/proposals/{proposal_id}`
  - `POST /content-planning/proposals/{proposal_id}/apply`
  - `POST /content-planning/proposals/{proposal_id}/reject`
  - `POST /content-planning/evaluations/{stage}/{opportunity_id}/run`
  - `GET /content-planning/evaluations/{opportunity_id}`
  - `GET /content-planning/agent-runs/{run_id}`
  - `GET /content-planning/agent-tasks/{task_id}`
- `Brief` 阶段开放第一条可写闭环：
  - discussion -> proposal -> partial apply
  - locked field 保护
  - version bump
  - stale propagation (`strategy / plan / titles / body / image_briefs / asset_bundle`)
- Brief 工作台新增：
  - `Ask the Council`
  - `Discussion Summary`
  - `Proposal Diff`
  - `Apply selected changes`
  - `Baseline vs Current Scorecard`
- `Strategy` 阶段本轮开放 proposal/apply：
  - discussion -> proposal -> partial apply
  - apply 前强制检查 `brief stale / base_version mismatch`
  - apply 后只把 `plan / titles / body / image_briefs / asset_bundle` 标 stale
  - `strategy` 自身保持 fresh，不清空 `match`
- Strategy 工作台新增：
  - `Ask the Council`
  - `Discussion Summary`
  - `Proposal Diff`
  - `Apply selected changes`
  - `Baseline vs Current Scorecard`
- `strategy` 评分口径切到 `strategy_v2`：
  - `strategic_coherence`
  - `differentiation`
  - `platform_nativeness`
  - `conversion_relevance`
  - `brand_guardrail_fit`
- `Plan` 阶段本轮开放 proposal/apply：
  - discussion -> proposal -> partial apply
  - apply 前强制检查 `strategy stale / base_version mismatch`
  - 允许按 nested field 局部应用（例如 `title_plan.candidate_titles` / `body_plan.body_outline` / `image_plan.global_notes`）
  - apply 后保持 `plan` fresh，只把 `titles / body / image_briefs / asset_bundle` 标 stale
- Plan 工作台新增：
  - `Ask the Council`
  - `Discussion Summary`
  - `Proposal Diff`
  - `Apply selected changes`
  - `Baseline vs Current Scorecard`
- `plan` 评分口径新增 `plan_v1`：
  - `structural_completeness`
  - `title_body_alignment`
  - `image_slot_alignment`
  - `execution_readiness`
  - `human_handoff_readiness`
- comparison 现在会同时检查 `strategy_v2` 与 `plan_v1` 的口径兼容性；不兼容 baseline 会被跳过
- comparison 不再比较不兼容的 `strategy_v1` 历史评分；旧记录保留可读，但不会进入当前 uplift 计算

### 当前策略

- `Brief / Strategy / Plan / Asset` 已开放 apply
- `Asset` 已进入 proposal + partial apply 阶段：
  - discussion -> proposal -> partial apply
  - apply 前强制检查 `plan / titles / body / image_briefs` 是否 stale
  - 允许按资产块局部应用：
    - `title_candidates`
    - `body_outline`
    - `body_draft`
    - `image_execution_briefs`
  - apply 后保持 `asset_bundle` fresh，不反向污染 `brief / strategy / plan`
  - apply 会递增 `asset_bundle.version`，并回写 `asset_bundle_versions`
- `Asset` 评分口径升级为 `asset_v1`：
  - `headline_quality`
  - `body_persuasiveness`
  - `visual_instruction_specificity`
  - `brand_compliance`
  - `production_readiness`
- comparison 现在会跳过旧 `content` 口径历史评分；旧记录保留可读，但不会进入当前 `asset_v1` uplift 计算
- `/content-planning/discuss/{opportunity_id}` 与 `/content-planning/evaluate/{opportunity_id}` 继续保留，兼容旧入口

### 运行与验证

- 新增测试：
  - `apps/content_planning/tests/test_stage_workflow_api.py`
- 本轮关键验证命令：
  - `pytest apps/content_planning/tests/test_stage_workflow_api.py -q`
  - `pytest apps/content_planning/tests -q`
  - `pytest apps/intel_hub/tests apps/content_planning/tests -q`
  - `python -m compileall apps/content_planning apps/intel_hub`
  - `GET /content-planning/assets/{opportunity_id}` HTML smoke check

### 已知限制

- `brief council graph` 目前仍由 `DiscussionOrchestrator` 驱动，`graph_executor.py` 仍处于下一步接入阶段
- `Asset` 已开放 apply，但 `asset council` 仍复用 `DiscussionOrchestrator`，还没有切到 `graph_executor.py`
- Asset 页面 smoke check 在无外网时会触发 LLM provider 连接报错日志，但当前实现会 graceful degrade，不影响页面返回与测试
- `evaluations` 已持久化，但更细的 A/B experiment UI 还未建设

## 2026-04-09 补充：Agent 性能优化 Chunk 1（Baseline and Instrumentation）

### 本轮完成

- `run-agent`、`chat`、通用 stage discussion 已补请求级时序埋点：
  - `timing_ms`
  - `timing_breakdown.context_ms`
  - `timing_breakdown.agent_ms` / `discussion_ms`
  - `timing_breakdown.persist_ms`
- 4 个内容策划页面已补服务端渲染耗时响应头：
  - `X-Render-Timing-Ms`
  - 覆盖 `brief / strategy / plan / assets`
- 新增测试：
  - `apps/content_planning/tests/test_agent_performance_paths.py`
  - `apps/intel_hub/tests/test_content_page_fast_paths.py`

### 当前基线（本地离线 / graceful degrade 条件）

以下数据用于后续 Chunk 2+ 的前后对比，不代表外网可用、模型 provider 正常时的真实线上耗时。

- 页面 GET（3 次中位数，单位 ms）：
  - `GET /content-planning/brief/{id}`: `2`
  - `GET /content-planning/strategy/{id}`: `9`
  - `GET /content-planning/plan/{id}`: `18`
  - `GET /content-planning/assets/{id}`: `0`
- 交互端点（3 次中位数，单位 ms）：
  - `POST /content-planning/run-agent/{id}`: `3`
  - `POST /content-planning/chat/{id}`: `5`
  - `POST /content-planning/stages/brief/{id}/discussions`: `7`

### 测量说明

- 测量环境：
  - 本地 `TestClient`
  - warm session
  - 临时 SQLite store
  - 单个已 promoted 的 demo opportunity
- 当前网络环境下 `dashscope.aliyuncs.com` 不可达，LLM provider 会快速报错并走 graceful degradation。
- 因此本轮基线主要用于回答：
  - 哪些路径已经能稳定暴露 timing metadata
  - 后续 `session-first / fast mode / parallel council / timeout` 改造后，耗时是否下降
- 本轮基线暂不用于回答：
  - 外部模型可用时的真实端到端等待时间
  - 多 provider 下的真实 council latency

### 下一步性能优化顺序

1. 将 `Brief / Strategy / Plan` 页面改成 session-first，去掉 GET 上的隐式重编。
2. 为 `run-agent` / `chat` 增加 `fast` 与 `deep` 两种执行模式。
3. 把 council specialist 从串行改成并行，并补 request-scoped context bundle。

## 2026-04-09 补充：Agent 性能优化 Chunk 2（Session-First Pages）

### 本轮完成

- `GET /content-planning/brief/{id}` 不再在 plain GET 上调用 `build_brief()`。
- `GET /content-planning/strategy/{id}` 不再在 plain GET 上调用 `build_note_plan(...with_generation=False)`。
- `GET /content-planning/plan/{id}` 不再在 plain GET 上调用 `build_note_plan(...with_generation=True)`。
- 三个页面统一改成：
  - 先读取 `planning_sessions` / 内存热层中的 session snapshot
  - 只有显式 `?refresh=1` 时才触发重编
  - 若当前 session 没有对象快照，页面显示显式生成 CTA，而不是隐式重跑编译链

### 当前行为

- `brief / strategy / plan` 三页的 plain GET 已是只读热路径。
- `assets` 页暂时保持现状，继续走当前的 asset-safe 组装路径。
- HTML 页新增显式提示文案：
  - “页面不会在加载时自动重编译”
  - “点击这里显式生成 …”

### 影响与预期收益

- 打开对象页时不再默认触发：
  - brief 编译
  - template match
  - strategy 生成
  - note plan + generation
- 这一步先消掉最重的“打开页面即重编”开销，为后续：
  - `fast / deep mode`
  - 并行 council
  - request-scoped context bundle
  提供干净基线。

### Chunk 2 之后的本地 warm-session 观测

仍在本地离线 / graceful degrade 条件下，4 个页面的 `X-Render-Timing-Ms` 3 次中位数已经下降到：

- `GET /content-planning/brief/{id}`: `0`
- `GET /content-planning/strategy/{id}`: `0`
- `GET /content-planning/plan/{id}`: `0`
- `GET /content-planning/assets/{id}`: `0`

这里的 `0` 是整数毫秒取整结果，意味着页面 GET 已基本退化为 session 读取 + 模板渲染成本；真实线上耗时仍需在 provider 可用环境下继续观察。

## 2026-04-10 补充：Agent 性能优化 Chunk 3（Fast / Deep Execution Modes）

### 本轮完成

- `run-agent` 新增 `mode` 协议，默认 `fast`。
- `chat` 新增 `mode` 协议，默认 `fast`。
- stage discussion 的 `run_mode` 新增：
  - `agent_assisted_council`
  - `agent_assisted_single`
- 当前语义收敛为：
  - `fast`
    - 单 Agent 默认跳过 `_enhance_with_llm()`
    - `LeadAgent` 默认跳过 LLM routing，优先走 stage map / keyword fallback
    - 保持现有对象工作流与返回结构不变
  - `deep`
    - 保留当前 richer path
    - `Ask the Council` 继续走 deep/council
- `agent_assisted_single` 会把 stage discussion 收缩为单参与者快速建议，用于后续轻量讨论场景。

### 前端接线

- 4 个对象页里现有的单 Agent 快捷动作与聊天入口，已显式携带 `mode: fast`：
  - `content_brief.html`
  - `content_strategy.html`
  - `content_plan.html`
  - `content_assets.html`
- `Ask the Council` 没有改成 fast，仍然保持多 Agent deep path。

### 当前收益边界

- 这一轮先切掉的是：
  - `LeadAgent` 的默认 LLM routing
  - 各子 Agent 默认的第二次 `_enhance_with_llm()` 调用
- 还没有切掉的是：
  - council specialist 的串行执行
  - provider timeout / circuit breaker

## 2026-04-10 补充：Agent 性能优化 Chunk 4（Request-Scoped Context Bundle）

### 本轮完成

- `run-agent / chat / stage discussion` 统一改为在 routes 层一次性装配 `RequestContextBundle`。
- bundle 当前包含：
  - `card`
  - `source_notes`
  - `review_summary`
  - `template`
  - `memory_context`
  - `object_summary`
- `LeadAgent` 的 deep routing 现在会优先复用 bundle 内的：
  - `memory_context`
  - `object_summary`
  不再重复向 DeerFlow adapter 要一次。
- specialist agents 的深度增强现在会优先复用 bundle 内的 `memory_context`，避免每个 agent 单独再开一次 `AgentMemory.recall()`。
- `DiscussionOrchestrator` 现在也会优先复用 bundle 里的：
  - `memory_context`
  - `object_summary`
  不再在 council 内重复构建。

### 当前收益边界

- 这一轮先切掉的是：
  - `chat deep` 中 DeerFlow routing 的重复 memory/object summary 装配
  - deep specialist path 的重复 memory recall
  - council path 的重复 memory/object summary 装配
- 还没有切掉的是：
  - provider timeout / circuit breaker

## 2026-04-10 补充：Agent 性能优化 Chunk 5（Parallel Council Specialists）

### 本轮完成

- `DiscussionOrchestrator` 已将 specialist 意见收集切换为有界并行执行。
- 当前并行阶段只覆盖 specialist opinions：
  - `trend_analyst`
  - `brief_synthesizer`
  - `template_planner`
  - `strategy_director`
  - `visual_director`
  - `asset_producer`
- synthesis 仍保持单次串行，以避免共识生成逻辑变复杂。
- discussion 输出继续按原参与者顺序写回，因此页面和持久化结构保持稳定。
- 当单个 specialist 失败时：
  - 不再整轮报错
  - discussion 会保留成功观点继续综合
  - 失败角色写入 `failed_participants`
  - 对应消息会带 `metadata.status = failed`

### 当前收益边界

- 这一轮先切掉的是：
  - council specialist 串行等待造成的线性累计耗时
  - 单个 specialist 报错导致整轮 discussion 失败
- 还没有切掉的是：
  - provider timeout / circuit breaker
  - 更细粒度的 node-level 并行观测与 retry

## 2026-04-10 补充：Agent 性能优化 Chunk 6（LLM Fail-Fast / Degraded Mode）

### 本轮完成

- `LLMRouter.chat`：统一 `ThreadPoolExecutor` 超时；`LLM_TIMEOUT_SECONDS`（默认 **90s**，可覆盖）/ `LLM_FAST_MODE_TIMEOUT_SECONDS`（默认 2s）；`call_text_llm` 与之一致；超时或空响应返回 `degraded` + `degraded_reason`。
- `call_text_llm` / VLM：DashScope 调用包在 `_run_with_timeout` 内，与路由层超时策略一致。
- `stage_evaluator`：`_llm_evaluate` 单次 `chat` 解析 JSON；`degraded` 或异常时回退规则评分（`evaluator: rule`）。
- 测试：`test_llm_timeout_returns_degraded_response_quickly`、`test_evaluation_falls_back_to_rule_when_llm_degraded`。

## 2026-04-10 补充：Agent 性能优化 Chunk 7（Frontend Secondary Request Deferral）

### 本轮完成

- 四页 `content_brief / content_strategy / content_plan / content_assets` 内联脚本增加 `scheduleDeferred`（`requestIdleCallback` + 短 `setTimeout` 回退）。
- **评分卡**：`loadLatestScorecard()` 改为空闲时执行，不再与首屏解析同步争抢。
- **SSE**：`EventSource` 连接延后约 40ms + idle，减轻首屏主线程压力。
- **Plan 页协同**：去掉首屏自动 `loadCollab();`，仅用户点击「刷新协同状态」时拉 `timeline` + `graph`。
- **Assets 页技能**：`/content-planning/skills` 封装为 `loadSkillsPanel`，延后加载。
- 测试：`test_content_planning_templates_use_deferred_secondary_fetches`（`apps/intel_hub/tests/test_content_page_fast_paths.py`）。

### 收益边界

- 首屏仍包含完整 HTML 与主对象；延后的是非关键侧栏数据与长连接建立时机。
- 用户若需立即看协同流水线，需手动点一次「刷新协同状态」（Plan）。

## 2026-04-10 补充：Agent 性能优化 Chunk 8（Validation and Rollout）

### 验证命令（本轮已执行）

```bash
cd .worktrees/codex-four-stage-upgrade  # 或仓库根，视 worktree 而定
export PYTHONPATH=$PWD
.venv311/bin/pytest apps/content_planning/tests apps/intel_hub/tests -q
.venv311/bin/python -m compileall apps/content_planning apps/intel_hub -q
```

- **结果（本机）**：`248 passed`（`content_planning` + `intel_hub` 全量）；`compileall` 无报错。

### 页面烟测（TestClient + 已生成 note-plan 的 opportunity）

对 `GET /content-planning/brief|strategy|plan|assets/{id}`（`Accept: text/html`）抽样检查：

- **HTTP**：`200`
- **响应头**：`X-Render-Timing-Ms` 存在且为非负整数

**本轮一次抽样（generate-note-plan 后、本机沙箱/代理可能导致 LLM 日志报错，页面仍应成功）**：

| 路径 | X-Render-Timing-Ms（单次，ms） |
|------|-------------------------------|
| `/content-planning/brief/{id}` | 15 |
| `/content-planning/strategy/{id}` | 12 |
| `/content-planning/plan/{id}` | 17 |
| `/content-planning/assets/{id}` | 22 |

> 说明：上述数字为 **单次** 本地测量，用于 Chunk 8 收口；与 Chunk 1 基线表（多轮中位数）口径不同。外网 DashScope 可用时，应以同一脚本重测并更新本表。

### 交互端点「前后」对照（设计目标 vs 离线环境）

| 指标（计划文档 Success Metrics） | 设计目标 | 离线 / 无可用 provider 时行为 |
|-----------------------------------|----------|-------------------------------|
| 四页 GET 中位数 | brief ≤250ms / strategy ≤300ms / plan ≤350ms / assets ≤300ms（warm session） | 以 session 快照为主时通常 **远低于** 目标；具体取决于磁盘与模板复杂度 |
| `run-agent` fast 中位数 | ≤2.5s | monkeypatch 单测可测路径；真实耗时取决于模型 |
| Council 中位数 | ≤5.0s | 并行 specialist 降低线性累计；仍受 synthesis 与 LLM 限制 |
| 无 provider | — | `llm_router` / `call_text_llm` 快速失败或超时 → **规则/空响应降级**，接口不挂死 |

### 文档收口

- 新增：`docs/ARCHITECTURE_V2.md`（性能控制层与上述策略总览）。
- 新增决策：`docs/DECISIONS.md` **D-026**。
- `docs/README_PRODUCT.md`：增加「相关架构文档」指向 `ARCHITECTURE_V2.md`。
- 本文（`IMPLEMENT.md`）Chunk 1～8 串联可追溯。

### 建议提交

```bash
git add docs/IMPLEMENT.md docs/ARCHITECTURE_V2.md docs/DECISIONS.md docs/README_PRODUCT.md
git commit -m "docs: capture agent performance optimization architecture and metrics"
```

---

## 三阶段商业闭环升级（Phase 1-3）

按 `upgrade_biz_product.md` 中三阶段路径渐进实施。

### Phase 1：发布结果闭环

**数据模型**
- `PublishResult` 增强：新增 `opportunity_id`、`brief_version`、`strategy_version`、`plan_version`、`asset_bundle_version`
- 新建 `FeedbackRecord` / `WinningPattern` / `FailedPattern`（`apps/content_planning/schemas/feedback.py`）

**存储层**
- `ContentPlanStore`：新增 `feedback_records`、`winning_patterns`、`failed_patterns` 三表 + CRUD
- `B2BPlatformStore`：`publish_results` DDL 增加 `opportunity_id` 列；新增 `list_publish_results`

**对比体系**
- `ComparisonReport` 新增 `OutcomeDelta`：`approval_rounds_delta`、`edit_count_delta`、`time_delta`、`engagement_delta`

**API 路由**
- `POST /content-planning/asset-bundle/{id}/publish-result` — 录入发布结果
- `GET /content-planning/opportunities/{id}/outcome-summary` — 聚合摘要
- `GET /content-planning/comparison/{id}/outcome-delta` — 双层对比
- 修复 `POST .../feedback` 路由：增加 SQLite 持久化
- `GET /b2b/workspaces/{id}/feedback` + `GET /b2b/workspaces/{id}/pipeline`

**前端**
- `content_assets.html`：「标记已发布」→「发布结果录入」表单 + outcome summary 卡片
- 新建 `content_feedback.html`：漏斗 / 返工轮次 / 表现对比三视图

### Phase 2：品牌知识库与 Guardrails

**数据模型**
- 新增 `BrandGuardrail`、`BrandVoice`、`BrandProductLine`、`AudienceProfile`、`BrandObjective`（`apps/b2b_platform/schemas.py`）

**主链接入**
- `guardrail_checker.py`：`check_guardrails()` 检测 forbidden/must_mention/risk_words
- `StageProposal` 增加 `guardrail_warnings` / `blocked_by_guardrail` / `brand_fit_score`
- `evaluate_stage` 追加 `brand_fit` / `brand_guardrail_fit` / `campaign_fit` 三维度

**前端**
- 新建 `brand_config.html`：品牌信息 + 调性 + 护栏 + 目标人群 + Campaign 目标只读页

### Phase 3：团队工作区 + 审批交付流

**数据模型**
- 新增 `ObjectAssignment`、`ObjectComment`、`WorkspaceTimelineEvent`、`ApprovalRequest`、`ReadinessChecklist`

**统一状态机**
- `OpportunityBrief`、`RewriteStrategy`、`NewNotePlan`、`AssetBundle` 各增加 `lifecycle_status` 字段
- 全链路：`new → reviewed → promoted → in_planning → ready → approved → exported → published`

**存储层**
- `B2BPlatformStore`：新增 `object_assignments`、`object_comments`、`workspace_timeline`、`approval_requests`、`readiness_checklists` 五表 + CRUD

**API 路由**
- `POST /objects/{type}/{id}/assign` + `POST /objects/{type}/{id}/comments` + `GET .../comments`
- `POST /approvals/{id}/decision`
- `GET /b2b/workspaces/{id}/timeline`
- `GET /objects/{type}/{id}/readiness` + `PUT /objects/{type}/{id}/readiness`

**前端**
- 新建 `workspace_home.html`：工作区首页统计 + 快捷入口
- 新建 `opportunity_pipeline.html`：按 lifecycle_status 分列看板
- 新建 `review_approval.html`：审批队列列表

### 验证结果

- 所有 Python 文件 `py_compile` 通过
- 全部新模型实例化 + 字段断言通过
- `ContentPlanStore` feedback/winning/failed 三表 CRUD 通过
- `B2BPlatformStore` publish_results (增强) + assignments + comments + timeline + approvals + readiness 全量 CRUD 通过
- `guardrail_checker.check_guardrails` 正反用例通过
- 既有测试 `test_b2b_flow.py` 通过

---

## 全链路体验极简化升级（2026-04-10）

### 升级目标
围绕「原始笔记 → 机会卡 → Brief → 策略 → 计划 → 资产 → 发布 → 闭环」全链路，从导航贯通、角色协同、操作效率、信息反馈四维度做极简化/高效化升级。

### 1. 导航与页面贯通
- **顶栏导航重构**（`base.html`）：拆分为「情报中心 | 内容策划 | 协同管理 | 情报对象」四组，全部中文标签，英文 Signals/Opportunities/Risks/Watchlists → 信号/商机/风险/关注列表
- **5 个孤立模板挂载路由**（`app.py`）：`/workspace`、`/brand-config/{brand_id}`、`/feedback`、`/opportunity-pipeline`、`/review-approval` 五条 GET HTML 路由
- **机会卡详情页策划入口**（`xhs_opportunity_detail.html`）：promoted → 「进入 Brief 工作台」；非 promoted → 「升级为策划候选」

### 2. 全链路状态机驱动
- **flow 层 lifecycle_status**（`opportunity_to_plan_flow.py`）：`build_brief` → in_planning、`build_strategy` → in_planning、`build_plan` → in_planning、`assemble_asset_bundle` → ready、`mark_asset_bundle_exported` → exported、`approve_object(approved)` → approved
- **统一进度条**（`_progress_bar.html`）：机会卡 → Brief → 策略 → 计划 → 资产包，高亮当前阶段，显示 lifecycle_status 徽章，点击可跳转
- 四工作台（content_brief / content_strategy / content_plan / content_assets）全部替换原 anchor 面包屑为统一进度条

### 3. 角色协同集成
- **协同侧栏**（`_collab_sidebar.html`）：指派 + 评论 + 审批三折叠面板，调用 `/objects/{type}/{id}/assign`、`.../comments`、审批 API
- 四工作台右栏底部统一 include
- **品牌上下文摘要条**（`_brand_context_bar.html`）：品牌名 + 禁用/必提条数 + guardrail 警告 + 品牌配置入口
- 四工作台进度条下方统一 include

### 4. 操作效率提升
- **CTA 校准**：Assets 页发布后增加「查看反馈全局 →」导向 `/feedback`
- **机会卡批量操作**（`xhs_opportunities.html`）：多选 checkbox + 批量操作栏（批量升级为候选 / 批量生成 Brief）

### 5. 反馈闭环可见化
- **Brief 页品牌历史表现**（`content_brief.html`）：左栏增加「高表现模式 Top 3」「踩坑记录 Top 3」，数据来自 `/b2b/workspaces/{id}/feedback`
- **Dashboard 闭环指标**（`dashboard.html`）：已发布数 / 平均互动代理 / 平均审批轮次 / 高表现模式数

### 新增文件
| 文件 | 用途 |
|------|------|
| `_progress_bar.html` | 全链路进度条 include |
| `_collab_sidebar.html` | 协同面板 include |
| `_brand_context_bar.html` | 品牌上下文条 include |

### 修改文件
| 文件 | 改动 |
|------|------|
| `base.html` | 导航重构为中文四组 |
| `app.py` | +5 页面路由 |
| `opportunity_to_plan_flow.py` | 6 处 lifecycle_status 驱动 |
| `xhs_opportunity_detail.html` | +策划入口卡 |
| `xhs_opportunities.html` | +批量操作 |
| `content_brief.html` | +进度条 +品牌条 +协同栏 +品牌历史 |
| `content_strategy.html` | +进度条 +品牌条 +协同栏 |
| `content_plan.html` | +进度条 +品牌条 +协同栏 |
| `content_assets.html` | +进度条 +品牌条 +协同栏 +反馈CTA |
| `dashboard.html` | +闭环指标卡 |

### 验证结果
- Python 文件 ast.parse 通过
- 16 个 Jinja2 模板 `env.get_template()` 全部通过

---

## DeerFlow + Hermes Agent 架构升级（P0-P3）

**日期**: 2026-04-10
**范围**: Agent 基础设施全面升级，借鉴 DeerFlow 2.0 和 Hermes Agent 最佳实践

### 升级概览

基于 DeerFlow（LangGraph 状态图编排 + 中间件链 + Lead Agent 模式）和 Hermes Agent（自改进学习循环 + Tool Registry + 多入口统一核心）的最佳实践，对 Agent 层进行五阶段架构升级。

### P0: LLMRouter v2 — async + streaming + tool_calls

**文件**: `apps/content_planning/adapters/llm_router.py`

- 新增 `ToolCall`、`StreamChunk` 模型
- `LLMMessage` 扩展 `tool_calls`、`tool_call_id`、`name` 字段
- `LLMResponse` 扩展 `tool_calls`、`finish_reason` 字段
- `BaseLLMProvider` 新增 `achat()` / `achat_stream()` 默认 async 实现
- `OpenAIProvider` 原生 `AsyncOpenAI` 实现（achat + achat_stream）
- `AnthropicProvider` 原生 `AsyncAnthropic` 实现 + OpenAI→Anthropic tool schema 转换
- `LLMRouter` 新增：
  - `chat_with_tools()` — 同步 tool-calling 循环
  - `achat()` / `achat_stream()` — 异步聊天 & 流式
  - `achat_with_tools()` — 异步 tool-calling 循环
- 降级链通过 `LLM_FALLBACK_CHAIN` 环境变量配置化
- 全部同步接口保持向后兼容

### P1: 统一 Tool Registry + MCP 适配器

**新建文件**: `apps/content_planning/agents/tool_registry.py`

- `ToolEntry` — 工具定义（name/description/parameters_schema/handler/toolset/check_fn）
- `ToolResult` — 工具执行结果
- `ToolRegistry` — 中心注册表：register / get / list_tools / to_openai_schema / handle_tool_call / ahandle_tool_call
- `register_builtin_tools()` — 注册全部内置服务（compile_brief, generate_strategy, compile_plan, generate_titles, generate_body, generate_image_briefs, assemble_asset_bundle, list_templates, match_templates, check_guardrails, delegate_task, trigger_pipeline）

**新建文件**: `apps/content_planning/agents/mcp_adapter.py`

- `MCPServerConfig` / `MCPToolSpec` / `MCPAdapter`
- 支持动态发现外部 MCP 服务端并注册到 ToolRegistry
- 当前为结构占位，预留真实 MCP SDK 接口

### P2: LangGraph 式 StateGraph + 中间件链 + GraphExecutor v2

**修改文件**: `apps/content_planning/agents/base.py`

- `AgentContext` 新增 ThreadState 字段：`artifacts`, `todos`, `middleware_log`, `config`, `checkpoint_id`, `run_id`

**新建文件**: `apps/content_planning/agents/middleware.py`

- `BaseMiddleware` 抽象基类（before / after）
- 5 个内置中间件：
  - `GuardrailMiddleware` — 品牌 guardrail 检查
  - `SummarizationMiddleware` — 上下文过长自动摘要
  - `MemoryMiddleware` — 自动注入/提取记忆
  - `LifecycleMiddleware` — lifecycle_status 自动推进
  - `PersistMiddleware` — 每步后自动持久化
- `MiddlewareChain` — 有序中间件编排（default_chain 工厂方法）

**修改文件**: `apps/content_planning/agents/graph_executor.py`

- 新增 `GraphCheckpointer` — SQLite checkpoint（save/load/load_latest）
- `execute()` 增加条件分支评估（`_should_skip_by_condition`）
- 支持条件语法：`context.{field} is not None`、`context.{field} is None`、`context.extra.{key} exists`
- 新增 `execute_from_checkpoint()` — 断点续跑
- 中间件链集成（`set_middleware_chain`）
- 每轮完成后自动 checkpoint

**修改文件**: `apps/content_planning/agents/plan_graph.py`

- `ready_nodes()` 增加 SKIPPED 节点作为已完成依赖

### P3: Skills 可执行化 + Memory v2 + LeadAgent v2

**修改文件**: `apps/content_planning/agents/skill_registry.py`

- 新增 `SkillStep` 模型（tool_name + arguments + condition）
- 新增 `SkillExecutionResult` 模型
- `execute_skill()` / `aexecute_skill()` — 通过 ToolRegistry 执行工作流步骤
- `create_skill_from_result()` — Hermes 式自动沉淀技能
- `load_from_markdown()` — DeerFlow 式 Markdown Skill 加载
- `to_openai_schema()` — 导出为 LLM function calling 格式
- 新增 `full_pipeline` 默认 Skill 带完整 `executable_steps`

**修改文件**: `apps/content_planning/agents/memory.py`

- FTS5 全文检索虚拟表 + 自动同步触发器
- `search()` 优先走 FTS5 MATCH，失败回退 LIKE
- 新增 `session_id` 字段 + `search_sessions()` 跨会话检索
- Nudge 机制：`nudge()` 生成提示 + `process_nudge_response()` 解析存储
- `inject_context()` 增加 relevance_score 排序 + role boost

**修改文件**: `apps/content_planning/agents/lead_agent.py`

- Pipeline/Interactive 双模式：`_run_pipeline()` / `_run_interactive()`
- 三级路由降级：tool_calls > LLM (DeerFlow) > keyword
- `_route_with_tools()` — LLM tool_calls 驱动路由
- `delegate_task` / `trigger_pipeline` / `skill_*` tool_call 解析
- 中间件链集成

### 文件变更总结

| 文件 | 操作 |
|------|------|
| `adapters/llm_router.py` | 改 — async + stream + tool_calls |
| `agents/base.py` | 改 — ThreadState 扩展 |
| `agents/middleware.py` | 新建 — 5 个中间件 |
| `agents/tool_registry.py` | 新建 — 统一工具注册 |
| `agents/mcp_adapter.py` | 新建 — MCP 客户端 |
| `agents/graph_executor.py` | 改 — 条件分支 + checkpoint |
| `agents/plan_graph.py` | 改 — SKIPPED 依赖支持 |
| `agents/skill_registry.py` | 改 — 可执行化 |
| `agents/memory.py` | 改 — FTS5 + 跨会话 |
| `agents/lead_agent.py` | 改 — tool_calls 路由 |

### 架构决策

1. **不引入 LangGraph 包** — 借鉴其 StateGraph + reducer + checkpoint 模式自实现轻量版
2. **向后兼容** — 所有同步接口保持不变，新增 async 接口为增量
3. **不替换现有 7 个 Agent 的业务逻辑** — 只改基类和调用方式
4. **MCP 结构占位** — 预留接口，不引入 MCP SDK 依赖

---

## 一键策划执行过程可观测性升级 (2026-04-10)

将一键策划面板从"状态指示器"升级为"逐步产出预览器"。

### 改动要点

1. **数据层 — GraphExecutor._build_output_summary**
   - 新增方法，按 `agent_role` 从 `output_object` 提取关键字段为结构化 dict
   - 7 个 Agent 角色各有独立的摘要提取逻辑
   - `_run_node` 的 `on_node_complete` 回调增加 `output_summary` + `suggestions` 字段

2. **事件层 — AgentPipelineRunner 透传**
   - `_on_node_complete` 已有 `**data` 展开，新字段自动包含在 SSE payload 中，无需额外改动

3. **展示层 — _agent_pipeline_panel.html**
   - 节点卡片从平铺 grid 改为可展开式单列卡片
   - 完成后自动展开预览区，展示该步骤的结构化产出摘要
   - 按 agent_role 分别渲染：强度评分条/Top3 模板卡/策略三行/视觉图位等
   - 置信度小圆点（绿/黄/红三色）
   - 建议操作标签（chip 展示）
   - explanation 从 40 字扩展到 200 字
   - running 状态脉冲动画

### 文件变更

| 文件 | 操作 |
|------|------|
| `agents/graph_executor.py` | 改 — `_build_output_summary` + 丰富回调 |
| `api/templates/_agent_pipeline_panel.html` | 改 — 可展开预览卡片 + 分角色渲染 |

---

## 一键策划管线 Debug — 时序修复 + 结构化日志 (2026-04-10)

### 根因

1. `trigger()` 在 POST 返回前就发了 `pipeline_started` SSE 事件，但浏览器在 POST 返回后才建立 EventSource
2. 所有 Agent 的 LLM 增强因 `is_any_available()=false` 被跳过，pipeline 在 ~300ms 内全部跑完
3. SSE 连接建立时 pipeline 已完成，历史回放批量推送但前端 DOM 未就绪
4. Python logger 默认级别为 WARNING，所有 `logger.info` 不输出，管线执行完全是黑盒

### 修复

1. **时序修复**：`pipeline_started` 移到 `_execute()` 内部，在首个节点执行前 `await asyncio.sleep(0.3)` 给 SSE 连接建立时间
2. **结构化日志**：`agent_pipeline_runner.py` 和 `graph_executor.py` 在所有关键节点添加 `logger.info("[Pipeline/Executor] ...")`，配置 logger 级别为 DEBUG
3. **异常兜底**：新增 `_execute_safe` 包装器确保后台 task 异常永远被 log
4. **前端历史回放兼容**：`ensureNodeDOM()` 防御性重建缺失的节点卡片；`fallbackLoadStatus()` 在 pipeline_completed 时 totalNodes=0 时调 status API 回填
5. **前端调试日志**：所有 SSE handler 添加 `console.log('[AP]')` 输出

### 文件变更

| 文件 | 操作 |
|------|------|
| `services/agent_pipeline_runner.py` | 改 — 结构化日志 + 时序修复 + _execute_safe |
| `agents/graph_executor.py` | 改 — ROUND/NODE_START/NODE_DONE 日志 |
| `api/templates/_agent_pipeline_panel.html` | 改 — ensureNodeDOM + fallback + console.log |

---

## 四工作台极简化升级 (2026-04-10)

### 概述

将 22 页 / 14 导航项系统收口为「机会台 + 策划台 + 资产台 + 结果台」四主工作台架构。统一 Council/Agent/协同组件，同步升级后端 API 聚合层。

### Phase 0: 基建与测试骨架 ✅

- 新增 `GET /planning/{opportunity_id}` — 策划台聚合 API（一次返回 brief+match+strategy+plan+bundle+vm）
- 新增 `GET /opportunity-workspace` — 机会台聚合 API（列表+选中卡详情+source_notes+review）
- 新增 ViewModel 层 `apps/content_planning/viewmodels/planning_workspace_vm.py`（6 个纯函数，空数据安全）
- 新增 4 个模板骨架：planning_workspace.html / opportunity_workspace.html / asset_workspace.html / result_workspace.html
- 新增 E2E 测试骨架 `tests/e2e/test_workspace_pages.py`

### Phase 1: 导航收口 ✅

- `base.html` 导航从 14 项收口为 4 个主入口（机会/策划/资产/结果）+ 「更多」折叠下拉
- 旧 URL 全部保活，仅从主导航降级到「更多」菜单
- 点击外部自动关闭下拉菜单

### Phase 2: 策划台（核心） ✅

- 策划台三栏布局：左栏上下文 300px + 中栏 4 区块（Brief/模板/策略/Plan Board）+ 右栏 AI 操作区 350px
- ViewModel 集成：后端路由注入 vm 变量，模板使用 vm.brief_summary / vm.template_candidates / vm.strategy_summary / vm.plan_board
- 右侧抽屉组件（Brief 编辑表单）
- 统一 Council 组件 `unified_council.js`（替代 3 套分散实现，支持 stage 参数、SSE 监听、Proposal apply/reject）
- 旧 Brief/Strategy/Plan 页面加降级横幅

### Phase 3: 机会台 ✅

- master-detail 双栏布局：左 380px 卡片列表 + 右栏详情（4 宫格：洞察/证据/风险/动作）
- 紧凑工具栏：类型+状态 chip 筛选，选中态高亮
- 原始笔记预览折叠区
- 升级/进入策划台操作入口

### Phase 4: 资产台 + 结果台 + 组件统一 ✅

- 资产台：图位对象化（5 个独立图位卡片，各带锁定/重新生成操作）+ 变体前台化 + 导出 3 格式
- 结果台：发布结果表格 + 模板策略效果指标 + 复盘建议（强化/沉淀两列）
- `_progress_bar.html` 升级为对象状态条（弱化 step 感，改为面包屑+当前状态+快速跳转）
- `_collab_sidebar.html` 改为默认折叠（details 包裹）
- `_agent_pipeline_panel.html` 已集成到策划台右栏 Agent Board 区域

### 文件变更总览

| 文件 | 操作 |
|------|------|
| `apps/intel_hub/api/app.py` | 改 — 新增 /planning/{id} + /opportunity-workspace 聚合路由 |
| `apps/content_planning/viewmodels/__init__.py` | 新增 |
| `apps/content_planning/viewmodels/planning_workspace_vm.py` | 新增 — 6 个 ViewModel 函数 |
| `apps/intel_hub/api/templates/base.html` | 改 — 4 主入口 + 更多折叠导航 |
| `apps/intel_hub/api/templates/planning_workspace.html` | 新增 — 策划台三栏全功能模板 |
| `apps/intel_hub/api/templates/opportunity_workspace.html` | 新增 — 机会台 master-detail 模板 |
| `apps/intel_hub/api/templates/asset_workspace.html` | 新增 — 资产台图位对象化模板 |
| `apps/intel_hub/api/templates/result_workspace.html` | 新增 — 结果台精简 3 块模板 |
| `apps/intel_hub/api/static/js/unified_council.js` | 新增 — 统一 Council 组件 |
| `apps/intel_hub/api/templates/_progress_bar.html` | 改 — 对象状态条 |
| `apps/intel_hub/api/templates/_collab_sidebar.html` | 改 — 默认折叠 |
| `apps/intel_hub/api/templates/content_brief.html` | 改 — 降级横幅 |
| `apps/intel_hub/api/templates/content_strategy.html` | 改 — 降级横幅 |
| `apps/intel_hub/api/templates/content_plan.html` | 改 — 降级横幅 |
| `tests/e2e/test_workspace_pages.py` | 新增 — E2E 验收测试 |

---

## 六项体验修复升级 (2026-04-11)

### 变更摘要

1. **机会工作台默认选中第一张卡** — `/opportunity-workspace` 路由在无 `selected` 参数时自动选中 `page_cards[0]`，右栏不再为空。
2. **小红书原始笔记卡片** — 右栏详情区四宫格上方新增小红书风格笔记卡片：封面大图、作者信息、正文、图片画廊、互动数据、热门评论，图片可点击放大。
3. **导航栏「资产」链接修复** — `base.html` 中「资产」导航改为 `/asset-workspace`；新增 `GET /asset-workspace` 路由和 `asset_workspace_list.html` 模板，展示已 promoted 卡的资产包列表。
4. **策划台 AI 操作改为抽屉交互** — 「快速分析」「发起委员会」「生成变体」三个按钮均统一改为右侧抽屉交互，分析结果和 Council 讨论全部在抽屉内展示。
5. **LLM 切换为用户自定义端点** — `.env` 新增 `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` / `LLM_PROVIDER` / `LLM_FALLBACK_CHAIN`，`OpenAIProvider` 显式传入 `base_url` 和 `api_key`。
6. **Council 多角色讨论完整前端交互** — 抽屉内实现完整 Council UI：阶段选择、讨论主题输入、发起讨论按钮，讨论过程中各角色 Agent 发言卡片实时展示，讨论完成后显示 Proposal diff + 采纳/拒绝操作。

### 文件变更

| 文件 | 操作 |
|------|------|
| `apps/intel_hub/api/app.py` | 改 — 机会台默认选中第一张卡 + 新增 /asset-workspace 路由 |
| `apps/intel_hub/api/templates/base.html` | 改 — 「资产」导航改为 /asset-workspace |
| `apps/intel_hub/api/templates/opportunity_workspace.html` | 改 — 小红书风格原始笔记卡片(封面+正文+图片+评论) + 图片 lightbox |
| `apps/intel_hub/api/templates/planning_workspace.html` | 改 — AI 操作统一抽屉 + Council 完整交互 UI |
| `apps/intel_hub/api/templates/asset_workspace_list.html` | 新增 — 资产工作台列表入口页 |
| `apps/content_planning/adapters/llm_router.py` | 改 — OpenAIProvider 显式传入 base_url/api_key |
| `.env` | 改 — 新增 Gemini 自定义端点配置 |

---

## V2 三层架构升级: Hermes Base + DeerFlow Harness + Workspace OS (2026-04-11)

### 变更摘要

基于 `product_architecture_V4` 和 `architech_deerflow_hermes_V4` 两份文档，完成三层架构升级：

**Phase A: Agent Base Layer (Hermes 风格基座)**
1. **PlanningContextAssembler** — 统一上下文组装，`run-agent`/`chat`/`council` 三条 AI 入口共用
2. **ProjectMemoryProvider** — `AgentMemory` 新增 `brand_id`/`campaign_id` 维度，支持品牌级记忆、跨机会教训注入、项目共识存储
3. **SkillRegistry v2** — 所有 10 个默认 Skill 补上 `executable_steps`；新增 `success_rate`/`last_updated` 追踪
4. **LearningLoopHooks** — `HermesAdapter` 新增 `on_proposal_adopted`/`on_low_score`/`track_skill_execution` 闭环钩子

**Phase B: Workflow Harness Layer (DeerFlow 风格编排)**
5. **Workspace Subgraphs** — 4 个 Workspace 子图 (`opportunity`/`planning`/`creation`/`asset`) + `WORKSPACE_GRAPH_BUILDERS` 映射
6. **execute_subgraph** — `GraphExecutor` 新增从指定节点开始执行的子图能力
7. **Partial Rerun** — `AgentPipelineRunner` 新增 `rerun_from_node`/`cancel_node` 支持局部重跑
8. **IntentRouter** — 替代 LeadAgent 关键词猜测，Stage 约束 → 正则意图分类 → LLM 兜底

**Phase C: Workspace-native AI (产品层)**
9. **HealthChecker** — Brief/Strategy/Plan/Asset 四阶段健康检查
10. **ActionSpec** — 统一 AI 动作规格模型
11. **Council 全阶段 diff** — `strategy_block_diffs`/`plan_field_diffs`/`asset_diffs`
12. **StrategyBlockAnalyzer** — 策略块级分析/重写/锁定
13. **AIInspector** — 对象选中态 AI 面板 + Plan Consistency
14. **OpportunityReadinessChecker** — 证据完整度 + Review 共识 + 历史机会
15. **JudgeAgent** — 资产质量评估 + VariantSet 多变体对比
16. **ReviewLoop** — 发布后效果回填 → 记忆 → 进化信号

**Phase D: Review and Evolution Loop (自进化闭环)**
17. D1-D3 整合在 `ReviewLoop`：Skill 版本追踪、品牌偏好沉淀、策略模式提取

### 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/{opp_id}/health-check` | POST | 阶段健康检查 |
| `/{opp_id}/inspect` | POST | AI Inspector 对象分析 |
| `/{opp_id}/plan-consistency` | POST | 计划一致性检查 |
| `/{opp_id}/readiness` | GET | 机会就绪度评估 |
| `/{opp_id}/judge` | POST | 资产质量评审 + 变体对比 |
| `/{opp_id}/review-feedback` | POST | 发布后效果回填 |
| `/{opp_id}/strategy-block` | POST | 策略块级操作 |
| `/{opp_id}/agent-pipeline/rerun` | POST | 局部重跑 pipeline |

### 文件变更

| 文件 | 操作 |
|------|------|
| `apps/content_planning/agents/context_assembler.py` | 新增 — PlanningContextAssembler |
| `apps/content_planning/agents/intent_router.py` | 新增 — IntentRouter |
| `apps/content_planning/agents/health_checker.py` | 新增 — HealthChecker |
| `apps/content_planning/agents/strategy_block_analyzer.py` | 新增 — StrategyBlockAnalyzer |
| `apps/content_planning/agents/ai_inspector.py` | 新增 — AIInspector + PlanConsistency |
| `apps/content_planning/agents/opportunity_readiness.py` | 新增 — OpportunityReadinessChecker |
| `apps/content_planning/agents/judge_agent.py` | 新增 — JudgeAgent + VariantSetComparison |
| `apps/content_planning/agents/review_loop.py` | 新增 — ReviewLoop + D1/D2/D3 |
| `apps/content_planning/schemas/action_spec.py` | 新增 — ActionSpec + 转换函数 |
| `apps/content_planning/agents/memory.py` | 改 — brand_id/campaign_id + 项目级记忆方法 |
| `apps/content_planning/agents/skill_registry.py` | 改 — 10 个 Skill 补 executable_steps |
| `apps/content_planning/agents/discussion.py` | 改 — CouncilSynthesisBundle 多阶段 diff |
| `apps/content_planning/agents/plan_graph.py` | 改 — 4 个 Workspace 子图 |
| `apps/content_planning/agents/graph_executor.py` | 改 — execute_subgraph |
| `apps/content_planning/agents/lead_agent.py` | 改 — 集成 IntentRouter |
| `apps/content_planning/adapters/hermes_adapter.py` | 改 — LearningLoopHooks V2 |
| `apps/content_planning/services/agent_pipeline_runner.py` | 改 — rerun_from_node + cancel_node |
| `apps/content_planning/api/routes.py` | 改 — PlanningContextAssembler + 8 个新端点 |

---

## V3 验收测试与补全（2026-04-11 完成）

### Schema 补全

| 文件 | 操作 |
|------|------|
| `apps/content_planning/schemas/export_package.py` | 新增 — ExportPackage（导出封装 + lineage） |
| `apps/content_planning/schemas/image_execution_brief.py` | 新增 — ImageExecutionBrief（强类型图位执行指令） |
| `apps/content_planning/schemas/variant.py` | 改 — VariantSet +brief_id/strategy_id/plan_id |
| `apps/content_planning/schemas/asset_bundle.py` | 改 — +brief_id/strategy_id 顶层; image_execution_briefs 类型升级 |

### 验收测试（83 项全部通过）

| 测试文件 | 用例数 | 覆盖层 |
|----------|--------|--------|
| `test_v3_L0_architecture.py` | 18 | Hermes 基座 + DeerFlow 编排 + 分层隔离 |
| `test_v3_L1_object_chain.py` | 7 | 12+ 对象构造 + 全链路追溯 + 版本管理 |
| `test_v3_L2_context_stage.py` | 18 | Context Assembler + HealthChecker + ActionSpec 转换 |
| `test_v3_L3_decision_action.py` | 18 | IntentRouter + Council Diffs + ActionSpec 覆盖 |
| `test_v3_L4_compiler.py` | 7 | Brief 健康 + StrategyBlock 分析 + AssetBundle 组装 |
| `test_v3_L5_workspace_api.py` | 8 | 8 个 V2 API 端点集成测试 |
| `test_v3_L6_L7_stability.py` | 7 | LLM 降级 + Memory miss + 回归确认 |

### 前端 V2 端点对接

| 工作台模板 | 对接端点 | 功能 |
|------------|----------|------|
| `planning_workspace.html` | health-check, strategy-block | 健康度指示器 + Action Chips + 策略块 AI 检视 |
| `opportunity_workspace.html` | readiness | 就绪度面板 + 历史记忆 |
| `asset_workspace.html` | judge, review-feedback | JudgeAgent 评分 + 效果反馈表单 |
| `content_plan.html` | plan-consistency, inspect | 一致性检查 + AI Inspector |

### 验收报告

详见 `docs/V3_VERIFICATION_REPORT.md` — 96 项测试（含 13 项 V1 回归）全部通过，零失败。

---

## Council 讨论 Apply + 资产详情页升级（2026-04-11）

### Phase A: Council Apply 断裂修复

| 变更 | 说明 |
|------|------|
| `planning_workspace.html` apply/reject 路径 | `applyProposal` / `rejectProposal` 改为调用 `/proposals/{proposalId}/apply`（之前错误调用 `/discussions/{id}/apply`） |
| `_renderFinalProposal` 字段展示 | 读取 `proposed_updates` + `diff` 行，渲染 before/after 对比 + 逐字段勾选框 + `selected_fields` 传参 |
| Strategy 块级 diff 映射 | `apply_stage_updates` strategy 分支新增 `strategy_block_diffs` 参数处理：`action=rewrite` 的块映射到 `title_strategy` / `body_strategy` 等字段 |
| `routes.py` apply_proposal | 当 stage=strategy 时，从 proposal 载荷中提取 `strategy_block_diffs` 传入 flow |

### Phase B: 资产制作人分析修复

| 变更 | 说明 |
|------|------|
| `AssetProducerAgent._ensure_prerequisites` | 新增方法：当 context 缺少 plan/strategy 时，自动从 flow session 加载或触发上游构建 |
| `content_assets.html` mode 修正 | `asset_producer` 角色改为 `deep` 模式（其他角色保持 `fast`） |
| 错误提示优化 | 缺少前置对象时返回明确提示 + 引导 chips |

### Phase C: 资产阶段 Council 角色

| 变更 | 说明 |
|------|------|
| `discussion.py` STAGE_DISCUSSION_ROLES | asset 阶段角色更新为 `[creative_director, brand_guardian, growth_strategist, risk_assessor]`，4 角色全参与 |

### Phase D: 委员会历史讨论可见

| 变更 | 说明 |
|------|------|
| `plan_store.py` | 新增 `list_discussions_by_opportunity(opportunity_id, limit, stage)` 方法 |
| `routes.py` | 新增 `GET /discussions/by-opportunity/{opportunity_id}` 端点 |
| `planning_workspace.html` | Council 抽屉顶部增加「历史讨论」折叠区，打开时自动加载 |
| `content_assets.html` | Council 区块上方增加「历史讨论」折叠区，按 asset 阶段过滤 |

### Phase E: 资产详情页右栏重构

右栏从 10+ 卡片垂直堆叠重构为 4 层结构：

```
├── 固定主操作区（sticky）
│   ├── 资产制作人分析
│   ├── 导出 JSON / MD
│   └── 生成变体
├── AI 面板 Tab 组
│   ├── Tab 1: AI 评审（Scorecard）
│   ├── Tab 2: Council（历史 + 提问 + Proposal）
│   └── Tab 3: 协同（时间线 + 对话合并）
├── 发布与复盘（折叠）
│   ├── 发布结果录入
│   ├── 结果摘要
│   └── 反馈全局入口
└── 辅助信息（折叠）
    ├── 对象状态
    └── 可用技能
```

### 测试状态

148 项测试全部通过（含新增 + 原有回归），零失败。

---

## 资产页 Council 交互对齐策划页 (2026-04-11)

### Phase 1: 资产页 Council SSE 全链路对齐

资产详情页的 Council Tab 从「轻量单次 HTTP 请求」升级为与策划页完全一致的「SSE 流式讨论 + 结构化 Proposal Apply」模式：

- **SSE 实时讨论过程**：`EventSource` 监听所有 `council_*` 事件
- **讨论线程 UI**：参与者卡片 + SOUL tagline + 轮次标题 + thinking 动画
- **共识综合卡**：绿色「总调度 · 共识」实时插入
- **Proposal 结构适配**：`proposed_updates` + `diff[]` + `field_changes` 多路兼容
- **Reject 操作**：`/proposals/{id}/reject` 按钮
- **`run_mode` 显式传参**：`agent_assisted_council`
- **stage 固定为 `asset`**，不需要阶段下拉

### Phase 2: Council 公共 JS 提取

新建 `_council_ui.html` Jinja include，两页面共用：

| 函数 | 说明 |
|------|------|
| `councilUI.roleMeta(agentId)` | 角色图标/颜色/标签映射 |
| `councilUI.esc(s)` | HTML 转义 |
| `councilUI.loadDiscussionHistory(elId, oppId, stage)` | 历史讨论加载 |
| `councilUI.renderFinalProposal(data, el, opts)` | Proposal 渲染（含 diff 适配 + 共识徽章 + skip_reason） |
| `councilUI.applyProposal(proposalId, cbClass)` | 采纳 |
| `councilUI.rejectProposal(proposalId)` | 拒绝 |
| `councilUI.initCouncilSession(config)` | 入口函数，初始化 SSE + POST |

### Phase 3: asset_diffs 持久化 + apply 通道

- **3a**: `DiscussionRound` 增加 `strategy_block_diffs` / `plan_field_diffs` / `asset_diffs` 字段，`discuss()` 在合成后赋值
- **3a**: `StageProposal` schema 增加同名三个字段，创建 Proposal 时写入
- **3b**: `apply_proposal` 路由在 `stage == "asset"` 时从 proposal 取 `asset_diffs` 传入 flow
- **3c**: `apply_stage_updates` asset 分支增加 `_ASSET_COMPONENT_MAP` 映射：

```
title -> title_candidates
body -> body_draft
body_outline -> body_outline
image -> image_execution_briefs
```

### Phase 4: skip_reason 提示

- `build_stage_diff` 对不在 editable 白名单的字段标注 `skip_reason: "属于上游对象，请在策划页修改"`
- `apply_stage_updates` asset 分支返回 `skipped_reasons` 字典
- `apply_proposal` API 响应中包含 `skipped_reasons`
- 前端 `renderFinalProposal` 对有 `skip_reason` 的 diff 行显示灰色提示

### 文件变更清单

| 文件 | 变更 |
|------|------|
| `_council_ui.html` | **新建**：Council 公共 JS include |
| `content_assets.html` | Council Tab 替换为完整 SSE 版本，引入 `_council_ui.html` |
| `planning_workspace.html` | 引入 `_council_ui.html`，移除重复函数，delegate 到 `councilUI.*` |
| `discussion.py` | `DiscussionRound` 增加 `strategy_block_diffs`/`plan_field_diffs`/`asset_diffs`，`discuss()` 赋值 |
| `agent_workflow.py` | `StageProposal` 增加 `strategy_block_diffs`/`plan_field_diffs`/`asset_diffs` |
| `routes.py` | `_run_stage_discussion` 创建 Proposal 时写入 diffs；`apply_proposal` 传 `asset_diffs`；响应含 `skipped_reasons` |
| `opportunity_to_plan_flow.py` | `apply_stage_updates` 增加 `asset_diffs` 参数 + `_ASSET_COMPONENT_MAP`；`build_stage_diff` 增加 `skip_reason` 标注 |

### 测试状态

148 项测试全部通过，零失败。

---

## V5 内容策划架构升级 — 实施记录 (2026-04-11)

### Wave 1: Production Pipeline MVP

**目标**: 跑通离线 pipeline + 自动晋级 + 一键编译 + 发布格式化

#### 新增文件

| 文件 | 说明 |
|------|------|
| `schemas/compilation_report.py` | `CompilationReport`, `PublishReadyPackage`, `QualityExplanation`, `ImprovementItem` |
| `services/publish_formatter.py` | `XHSPublishFormatter` — AssetBundle -> 小红书发布格式化 |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `opportunity_promoter.py` | 新增 `auto_promote_for_dev()`, `batch_auto_promote()` |
| `xhs_opportunity_pipeline.py` | `main()` 默认 JSONL 路径先查 `data/fixtures/` |
| `opportunity_to_plan_flow.py` | `compile_note_plan()` 新增 `with_evaluation`/`with_publish_format` 参数；新增 `_evaluate_compilation()`, `format_for_publish()` |
| `routes.py` | 新增 V5 API: `POST /v5/compile/{id}`, `GET /v5/compilation-report/{id}`, `GET /v5/publish-package/{id}`, `POST /v5/auto-promote/{id}`, `POST /v5/batch-auto-promote` |

### Wave 2: 质量与解释

**目标**: QualityExplainer + 质量门控 + 编译报告前端

#### 新增文件

| 文件 | 说明 |
|------|------|
| `services/quality_explainer.py` | `QualityExplainer` — LLM 优先、规则兜底的差异化质量解释 |
| `templates/_compilation_report.html` | `compilationUI.renderReport()`, `compilationUI.renderPublishPackage()` 前端组件 |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `opportunity_to_plan_flow.py` | `_evaluate_compilation()` 集成 QualityExplainer |
| `routes.py` | 新增 `GET /v5/quality-explanation/{id}` |

### Wave 3: 工具与技能

**目标**: 激活 ToolRegistry + MCP 真实接入 + Skill 执行链路

#### 修改文件

| 文件 | 变更 |
|------|------|
| `tool_registry.py` | 新增 3 个 V5 工具注册: `format_for_publish`, `explain_quality`, `evaluate_stage`；共 14 个工具注册成功 |
| `skill_registry.py` | `full_pipeline` 技能更新为 10 步完整链路（含 titles/body/format/evaluate） |
| `mcp_adapter.py` | 新增 `load_config()` 从 YAML 加载 MCP 服务器定义；新增 `list_servers()` |
| `app.py` | 在 `create_app` 中调用 `register_builtin_tools()` 激活工具注册 |
| `routes.py` | 新增 `GET /v5/tools` 列出工具/技能/MCP 服务器 |

### Wave 4: 混合工作台

**目标**: 手机模拟器预览 + 变体对比 + 行内编辑

#### 新增文件

| 文件 | 说明 |
|------|------|
| `templates/_preview_canvas.html` | `previewCanvas.renderPreview()`, `renderVariantCompare()`, `enableInlineEdit()` |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `planning_workspace.html` | 引入 `_compilation_report.html` + `_preview_canvas.html` |
| `content_assets.html` | 引入 `_compilation_report.html` + `_preview_canvas.html` |

### Wave 5: 数据飞轮

**目标**: 统一反馈 + Pattern 提取 + 模板效果权重 + 记忆增强

#### 新增文件

| 文件 | 说明 |
|------|------|
| `schemas/unified_feedback.py` | `UnifiedFeedback` 统一反馈事实表 |
| `services/pattern_extractor.py` | `PatternExtractor` — 从反馈中提取 WinningPattern / FailedPattern |
| `services/feedback_processor.py` | `FeedbackProcessor` — 单一入口触发三路下游 (pattern + template + memory) |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `plan_store.py` | 新增 `template_effectiveness` + `unified_feedback` 表；新增 `save_template_effectiveness()`, `save_unified_feedback()`, `load_unified_feedback()`, `load_template_effectiveness()` |
| `routes.py` | 新增 V5 飞轮 API: `POST /v5/feedback`, `GET /v5/feedback/{id}`, `GET /v5/patterns`, `GET /v5/template-effectiveness/{id}` |

### 测试状态

148 项测试全部通过，零失败（全部 Waves 完成后验证）。

### 新增 V5 API 总览

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/v5/compile/{id}` | 一键编译 + 质量评分 + 发布格式化 |
| GET | `/v5/compilation-report/{id}` | 获取编译质量报告 |
| GET | `/v5/quality-explanation/{id}` | 获取差异化质量解释 |
| GET | `/v5/publish-package/{id}` | 获取可发布格式内容包 |
| POST | `/v5/auto-promote/{id}` | Dev 快速晋级机会卡 |
| POST | `/v5/batch-auto-promote` | Dev 批量快速晋级 |
| GET | `/v5/tools` | 列出已注册工具/技能/MCP |
| POST | `/v5/feedback` | 统一反馈入口 |
| GET | `/v5/feedback/{id}` | 获取反馈记录 |
| GET | `/v5/patterns` | 获取 Winning/Failed Pattern |
| GET | `/v5/template-effectiveness/{id}` | 获取模板效果记录 |

---

## 生图体验升级 V2 (Phase A-G)

### 完成日期
2026-04-11

### 概要
从 7 个维度全面升级生图体验，覆盖 prompt 质量、用户交互、数据闭环和智能化。

### Phase A: 快速修复
- **A1**: `RichImagePrompt.to_image_prompt()` 将 `style_tags` 拼入实际 prompt（`风格：tag1、tag2`）
- **A2**: `prompt_composer` 补采 `text_overlay`（图上文字）、`target_user`/`target_scene`/`content_goal`（场景约束）
- **A3**: 前端负向 prompt textarea 始终渲染，空时有 placeholder 引导
- **A4**: 封面图默认尺寸改为 `1024*1365`（3:4 竖图），内容图保持 `1024*1024`

### Phase B: 原图展示 + 对比
- **B1**: 来源笔记卡片展示原始封面图（`cover_image`）
- **B2**: 生成完成后支持"原图 vs 生成图"并排对比（调用 `renderVariantCompare`）

### Phase C: 结构化 Prompt Builder
- **C1**: 替换遮罩弹窗为内联折叠面板 `#prompt-builder-panel`
- **C2**: 每个 slot 拆为 5 个模块：主体描述、风格/色调（chips）、必含元素（chips）、规避项（chips）、参考图
- **C3**: Prompt 质量分实时计算（主体 30 + 风格 20 + 必含 15 + 规避 15 + 参考图 10 = 90 满分）

### Phase D: Prompt 保存与复用
- **D1**: `plan_store.py` 新增 `saved_prompts_json` 列
- **D2**: 保存按钮 + `POST /v6/image-gen/{id}/save-prompts` + `preview-prompts` 优先加载已保存版本
- **D3**: 生成历史面板"复用此提示词"按钮，一键加载到 Builder

### Phase E: 质量信号 + 反馈闭环
- **E1**: 每张生成图增加评价按钮（👍 👎），`POST /v6/image-gen/{id}/feedback`
- **E2**: 确认生成前显示 diff 提示（修改了哪些字段/数量变化）

### Phase F: 基于用户编辑的自进化
- **F1**: `apply_user_preferences()` 从历史中提取 `user_edited=True && rating=good` 的偏好，合并到新 prompt
- **F2**: Builder 顶部显示偏好应用提示

### Phase G: Skill 驱动的 Prompt 优化
- **G1**: 新建 `apps/content_planning/skills/prompt_optimizer.py`，调用 LLM 优化结构化 prompt
- **G2**: `POST /v6/image-gen/{id}/optimize-prompt` + 前端"AI 优化提示词"按钮

### 新增文件

| 文件 | 说明 |
|------|------|
| `apps/content_planning/skills/__init__.py` | Skills 包初始化 |
| `apps/content_planning/skills/prompt_optimizer.py` | LLM prompt 优化 Skill |

### 修改文件

| 文件 | 变更 |
|------|------|
| `services/image_generator.py` | `RichImagePrompt` 增加 `subject`/`must_include`/`avoid_items` 字段，`compose_prompt_text()` 方法，`to_image_prompt()` 组装逻辑 |
| `services/prompt_composer.py` | `_SlotAccumulator` 增加结构化字段收集，补采 `text_overlay`/`target_user`/`target_scene`/`content_goal`，封面尺寸默认 `1024*1365`，新增 `apply_user_preferences()` |
| `storage/plan_store.py` | 新增 `saved_prompts_json` 列映射和迁移 |
| `api/routes.py` | 新增 `save-prompts`/`feedback`/`optimize-prompt` 端点，`preview-prompts` 支持 saved 优先加载和偏好应用计数，`edited_prompts` 处理增加结构化字段，`prompt_log` 增加 `subject`/`must_include`/`avoid_items` |
| `planning_workspace.html` | 内联 Prompt Builder 替代弹窗，结构化模块编辑（chips），质量分实时计算，保存/复用/AI优化按钮，评价按钮，diff 提示，原图对比视图，偏好提示，来源笔记封面图 |

### 新增 V6 API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/v6/image-gen/{id}/save-prompts` | 保存结构化 prompt |
| POST | `/v6/image-gen/{id}/feedback` | 图片评价（good/ok/bad） |
| POST | `/v6/image-gen/{id}/optimize-prompt` | AI 优化 prompt |

---

## Visual Builder 独立页升级（2026-04-12）

### 核心变更

1. **封面图传递修复**：新增 `source_images_json` 列，首次加载策划台时持久化来源笔记图片到 session，后续图片生成不再每次查 pipeline_details
2. **Visual Builder 独立页**：`GET /planning/{id}/visual-builder` 三栏布局（来源证据 / 预览画布 / Prompt 编辑 + LLM 日志）
3. **LLM 调用可观测**：`quick_draft_generator`/`prompt_optimizer`/`image_generator` 返回 `llm_trace`；前端右栏实时展示调用链
4. **策划台精简**：原笔记预览区从全功能区精简为只读缩略预览 + "进入视觉工作台"跳转按钮

### 新增文件

| 文件 | 说明 |
|------|------|
| `apps/intel_hub/api/templates/visual_builder.html` | 视觉工作台独立页模板 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `storage/plan_store.py` | 新增 `source_images_json` 列映射、JSON 列集合、ALTER TABLE 迁移、load_session 返回 |
| `intel_hub/api/app.py` | 新增 `_persist_source_images` + `visual_builder_page` 路由 |
| `api/routes.py` | `_build_rich_prompts` 优先从 session.source_images 读取参考图 |
| `services/quick_draft_generator.py` | 返回 `llm_trace`（model / input / output / latency） |
| `skills/prompt_optimizer.py` | 返回 `llm_trace` |
| `services/image_generator.py` | `ImageResult` 增加 `prompt_sent` / `ref_image_sent` 字段 |
| `planning_workspace.html` | 笔记预览区精简，移除 Prompt Builder / 生图操作 / 历史面板 |

### 新增路由

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/planning/{id}/visual-builder` | 视觉工作台独立页 |

---

## 卖点编译器体验升级（2026-04-16）

### 概述

针对卖点编译器的 6 个体验问题进行系统性升级：参考上下文缺失、编译过程黑盒、字段覆盖不全、平台表达无参考、专家参与不足、缺少评估与衔接。

### 改造清单

| # | 改造 | 状态 |
|---|------|------|
| 6 | 修复右栏 `[object Object]`、未传 workspace_id、规则兜底缺 first3s_expression | ✅ 完成 |
| 1 | TrendOpportunity 新增 rich_context、adapter 打包语义字段、compiler 扩充上下文、左栏卡片详情展开 | ✅ 完成 |
| 2 | 三阶段 SSE 编译流 + 前端过程面板（thinking dots + reasoning cards） | ✅ 完成 |
| 3 | 右栏结构化展示 + 货架/前3秒参考案例 | ✅ 完成 |
| 4 | ExpertAnnotation schema + 存储 + 批注 UI + 历史经验注入 LLM | ✅ 完成 |
| 5 | SellingPointEvaluator + 质量报告卡片 + 下一步引导 | ✅ 完成 |

### 新增文件

| 文件 | 说明 |
|------|------|
| `apps/growth_lab/services/selling_point_evaluator.py` | 规则驱动的卖点质量评估器（6维度打分 + 下一步建议） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `schemas/trend_opportunity.py` | 新增 `rich_context: dict` 字段 |
| `schemas/selling_point_spec.py` | 新增 `ExpertAnnotation` 模型 |
| `schemas/__init__.py` | 导出 `ExpertAnnotation` |
| `adapters/opportunity_adapter.py` | 打包 pain_point/desire/hook/selling_points 等语义字段到 rich_context |
| `services/selling_point_compiler.py` | 三阶段 SSE 编译流（洞察提炼→卖点构建→平台表达）、rich_context 注入 LLM prompt、专家批注历史注入、规则兜底补齐 first3s_expression |
| `storage/growth_lab_store.py` | 新增 expert_annotations 表 + CRUD 方法 |
| `api/routes.py` | 新增 SSE compile-stream 端点、annotations CRUD 端点、references 参考案例端点 |
| `templates/compiler.html` | 全面升级：左栏卡片详情展开、SSE 编译过程面板、结构化表达渲染、专家批注 UI、质量评估报告、下一步引导按钮、参考案例区 |

### 新增路由

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/growth-lab/api/compiler/compile-stream` | SSE 三阶段编译流 |
| POST | `/growth-lab/api/compiler/annotations` | 创建专家批注 |
| GET | `/growth-lab/api/compiler/annotations` | 查询批注列表 |
| GET | `/growth-lab/api/compiler/references` | 获取货架/前3秒参考案例 |

---

## 采集自动消费与串行队列优化（2026-04-24）

### 概述

解决“开始采集后只入队、不自动消费，右侧观察窗长期停留 pending”的问题。当前单实例原型环境改为应用内单 worker 自动消费，多个采集任务按 FIFO 串行执行，整批 crawl 跑完后只触发一次 `pipeline_refresh`，`/crawl-observer` 与全局右侧观察窗统一展示“当前执行 + 排队等待 + 结果整理”。

### 核心变更

1. **应用内嵌入单 worker**
   - `create_app(..., enable_embedded_crawl_worker: bool | None = None)` 新增开关
   - `RuntimeSettings.embedded_crawl_worker_enabled` 默认 `true`
   - FastAPI `lifespan` 内创建后台 coordinator
   - coordinator 使用 `asyncio.Event` 唤醒，不再靠忙轮询

2. **队列改成批次 + 串行语义**
   - 新采集任务会复用当前未整理完成批次的 `job_group_id`
   - `keyword_search` 同优先级按 FIFO 串行执行
   - `pipeline_refresh` 不会插队到待跑 crawl 前
   - 全部 crawl 任务结束后只入队一次 `pipeline_refresh`
   - 单个 crawl 失败不会阻塞后续任务

3. **观察窗口径统一到批次视角**
   - `/crawl-observer` 新增：
     - `queue.batch_job_group_id`
     - `queue.pending_jobs`
     - `queue.batch_total`
     - `queue.batch_completed`
   - `preferred job_id` 现在会映射到同批次活动任务，而不是死盯首次提交的 job
   - 右侧观察窗、`/notes` 轻量进度条、`/dashboard` 采集卡统一显示当前任务、排队任务数、后续关键词与整理阶段

4. **worker 参数与路径对齐**
   - `process_one_job(...)` / `worker_loop(...)` 补齐 `status_path`、`alerts_path`、`runtime_config_path`
   - API 与 embedded worker 统一使用 runtime 解析出的 `job_queue_path / crawl_status_path / alerts_path`

### 验证

- `python -m unittest apps.intel_hub.tests.test_api -v` 通过
- 新增验证覆盖：
  - 自定义 `status_path / alerts_path`
  - 同批次 `job_group_id` 复用
  - crawl 任务优先于 `pipeline_refresh`
  - `/crawl-observer` 批次摘要字段
  - embedded worker 自动消费 + 全批次完成后单次 `pipeline_refresh`

### 当前边界

- 本轮仍假设单 API 进程 / 单 uvicorn worker
- 不支持真实多实例并发消费
- 首版仍用轮询，不引入 SSE
- `pipeline_refresh` 在整批 crawl 结束后统一执行一次，不在每个关键词后单独执行
- 2026-04-24 补充：采集执行已切到 `third_party/MediaCrawler/.venv` 子进程，避免主应用 Python 3.14 直接导入 MediaCrawler 时持续遇到 `Pillow/cv2/matplotlib` 等二进制依赖兼容问题；应用内 worker 仍负责串行消费、heartbeat、失败告警与统一观察状态。

---

## 首页与入口文案精修（2026-04-25）

围绕用户提出的 5 点优化，对入口与首页做收敛：

1. **抽离无线画布** — `apps/growth_lab/templates/compiler.html`、`radar.html`、`main_image_lab.html`、`board.html`、`asset_graph.html`、`first3s_lab.html` 顶部 navbar 统一去掉 `视觉工作台 → /growth-lab/workspace` 入口；`compiler.html` specs 列表卡与 `updateActionLinks()` 中的"视觉工作台 →"按钮一并移除。增长实验室主线 2 不再跨跳到主线 3，套图工作台仅作为独立主线 3 入口出现在首页与 `_lane_bar.html`。
2. **去掉(旧) 标签** — `compiler.html` 与 `workspace.html` 共 6 处文案：`主图(旧) → 主图裂变`、`前3秒(旧) → 前3秒裂变`，路由保持不变。
3. **新增图片代理 `/img-proxy`** — `apps/intel_hub/api/app.py`：
   - 新增 `httpx` 依赖驱动的 `GET /img-proxy?url=...` 路由：白名单 host（`xhscdn.com / xhs.cn / xiaohongshu.com / douyinpic.com / douyincdn.com / weibocdn.com / sinaimg.cn`）+ `Referer: https://www.xiaohongshu.com/` + 桌面 UA + 失败回落 1×1 透明 PNG 占位 + `Cache-Control: public, max-age=86400`。
   - 在 `TEMPLATE_ENV` 注册 Jinja 过滤器 `proxy_img`；命中白名单的外链改写为 `/img-proxy?url=<encoded>`，站内静态路径与非白名单外链原样返回。
   - 模板侧统一接入：`notes.html / note_detail.html / xhs_opportunity_detail.html / content_brief.html / planning_workspace.html / opportunity_workspace.html` 中所有指向小红书原图的 `<img src>` 与视频 poster 全部走 `| proxy_img`，并清理冗余的 `referrerpolicy / crossorigin` 属性。
4. **消除"推送系统资产"误导文案** — `apps/growth_lab/templates/_lane_bar.html` 中"推送系统资产 →" 改为"查看系统资产 →"，原 href 不变，避免被误读为提交动作。本次未引入真正的 POST 入库动作（`SystemAssetService.register()` 已有，但每条 lane 的"完成 → 真入库"口径需另立项决定）。
5. **首页瘦身 + 三主线业务化卡片** — `apps/intel_hub/api/templates/dashboard.html` 整体重写：
   - 删除采集器状态卡 / 系统告警卡 / 闭环指标 / Signals/Opportunity/Risks/Watchlists 4 个 section 及其轮询脚本与 `@keyframes` 样式；`dashboard` handler 的 ctx 同步去掉 `signals/opportunities/risks/watchlists/crawl/crawl_dy/rss_counts`。
   - 三主线卡片采用统一 `.lane-card` 样式：顶边色（lane-1 #d97706、lane-2 #7c3aed、lane-3 #ea580c）+ 主线标签 / CTA / 业务化标题 / 描述 / 步骤 chips；主线 1 显示"素材库存 / 机会卡总数 / 已晋升机会"3 列 KPI，主线 2/3 用能力 chips 表达（避免数字空心）。
   - 次级"系统资产 / 结果反馈 / 审批队列" 3 张 `.quick-card` 轻量同样式化，跨主线产物统一沉淀的语义更清晰。

### 验证

- `python -m pytest apps/intel_hub/tests/test_api.py -q` 全绿（27 项），新增 `ImgProxyTests` 覆盖：白名单准入 + mock 上游 200 透传 + 拒绝非白名单与相对路径。
- 旧用例 `test_api_serves_paginated_lists_and_html_dashboard` 同步更新断言为新版三主线文案（`主线 1 · 内容生产` 等），原"Opportunity / evidence" 字面量随首页瘦身一同移除。
- 浏览器人工抽检路径：`/`、`/notes`、`/notes/{id}`、`/xhs-opportunities/{id}`、`/growth-lab/compiler`、`/growth-lab/workspace`、`/growth-lab/radar`，原始笔记图片改走 `/img-proxy?url=...`、首页只剩三主线卡 + 三张次级卡。

### 不在本次范围

- 真正的"完成 → POST 沉淀到 SystemAsset"动作（仅校正按钮文案；后续单独立项决定每条 lane 的提交口径与产物字段）。
- `/growth-lab/lab` 与 `/growth-lab/first3s` 页面本身的功能合并/迁移到视觉工作台（仅入口去重、文案统一为"裂变"，路由保留）。
