# 本体大脑情报中枢 V0.9 — AI-native 多角色协同交互架构

> V0.9 AI-native 协同架构升级：协同网关 + Lead Agent + SSE 实时流 + 多轮对话 + Plan Graph + Agent Memory + Skill Registry + 前端富交互。
> V0.3 核心升级：把小红书笔记从"内容样本"编译成"经营决策资产"。

## V0.9 进展 — AI-native 协同架构升级 (2026-04-09)

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

- `LLMRouter.chat`：统一 `ThreadPoolExecutor` 超时；`LLM_TIMEOUT_SECONDS` / `LLM_FAST_MODE_TIMEOUT_SECONDS`；超时或空响应返回 `degraded` + `degraded_reason`。
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
