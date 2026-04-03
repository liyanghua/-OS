# 本体大脑情报中枢 V0.3+ — 四层编译链 + 评论关联 + 视觉分析 + RSS 趋势情报 + XHS 机会卡

> V0.3 核心升级：把小红书笔记从"内容样本"编译成"经营决策资产"。
> V0.3+ 增量：评论-笔记自动关联 / 千问 VL 视觉分析 / 端到端验证通过。
> V0.4  RSS 趋势情报：接入 awesome-tech-rss + awesome-rss-feeds，新增「科技趋势」「新闻媒体」原生浏览页。
> V0.5  XHS 三维结构化机会卡流水线：视觉/卖点/场景三维提取 → 本体映射 → 机会卡生成。
> 详见 [PLAN_V2_COMPILATION_CHAIN.md](./PLAN_V2_COMPILATION_CHAIN.md) / [XHS_OPPORTUNITY_PIPELINE.md](./XHS_OPPORTUNITY_PIPELINE.md)

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
      visual_extractor.py        # 视觉维度提取
      selling_theme_extractor.py # 卖点主题提取
      scene_extractor.py         # 场景维度提取
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
      xhs_signals.py             # V0.5 VisualSignals / SellingThemeSignals / SceneSignals
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
