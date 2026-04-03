# 本体大脑情报中枢实施计划

## Phase 0: 文档与目录初始化

- 状态：已完成

## Phase 1: TrendRadar output 接入

- 状态：已完成首版，并在 V0.2 补上公开 SQLite schema 的专用适配。

## Phase 2: normalizer / projector

- 状态：已完成首版，并在 V0.2 补上 canonical entity projection。

## Phase 3: card compiler

- 状态：已完成首版，并在 V0.2 补上显式规则 dedupe。

## Phase 4: API / UI

- 状态：已完成首版，并在 V0.2 增加 review 字段展示与过滤。

## Phase 4.5: V0.2 可用性增强

### A. 真实 output 兼容增强

- 目标：让 loader 对 `.json` / `.jsonl` / `.db` 都能更稳健。
- 产出：
  - 最新批次选择
  - `news_items` / `platforms` / `rank_history` 专用映射
  - `rss_items` / `rss_feeds` 专用映射
- 验收标准：json/jsonl/db 均有自动化测试。
- 当前状态：已完成。

### B. Review / feedback 初版

- 目标：让卡片支持轻量人工 review writeback。
- 产出：
  - review schema
  - SQLite 回写
  - POST review API
  - HTML review 字段展示
- 验收标准：状态更新、过滤、`reviewed_at` 自动写入均有测试。
- 当前状态：已完成。

### C. Canonicalization / dedupe

- 目标：降低别名噪音和重复卡片。
- 产出：
  - canonicalizer
  - raw/canonical entity 字段
  - 显式 dedupe 规则
  - `dedupe_key` / `merged_signal_ids` / `merged_evidence_refs`
- 验收标准：alias 命中与 card merge 均有测试。
- 当前状态：已完成。

### D. Tablecloth category intelligence demo

- 目标：用 TrendRadar 默认平台和 keyword filter 跑通“桌布相关 output -> intel_hub UI 可看”的最短真实链路。
- 产出：
  - TrendRadar 配置样例
  - 桌布词包 V1
  - `category_tablecloth` watchlist 与 ontology mapping
  - 桌布 fixture 与自动化测试
  - UI 按 `entity` / `platform` 查看
- 验收标准：
  - 至少 1 条桌布 signal 命中 `category_tablecloth`
  - 至少 1 张桌布 opportunity card
  - UI 可按 `entity=category_tablecloth` 查看
- 当前状态：已完成。

## Phase 5: feedback / workflow 扩展

- 目标：从轻量 review writeback 继续扩展到更完整的 workflow。
- 已完成：
  - ✅ TrendRadar 真实抓取集成（克隆 → 配置 → 抓取 → pipeline → UI）
  - ✅ 真实 output 目录 smoke test（170 条 raw → 170 signals → UI 可查看）
  - ✅ MediaCrawler XHS 评论桥接（xhs_loader + xhs_aggregator → pipeline → UI）
  - ✅ MediaCrawler 作为 source adapter 直接接入（mediacrawler_loader + source_router）
- 当前状态：双源（TrendRadar + MediaCrawler）pipeline 已完成。

### Phase 5.E MediaCrawler source adapter 集成

- 目标：将 MediaCrawler 作为小红书专用 source adapter 接入 intel_hub，不经过 TrendRadar。
- 产出：
  - `third_party/MediaCrawler`（clone，.gitignore 排除）
  - `ingest/mediacrawler_loader.py`（读取原生 JSON/JSONL/SQLite 笔记输出）
  - `ingest/source_router.py`（统一 raw signal 收集，替代 pipeline 硬编码分支）
  - `config/runtime.yaml` 增加 `mediacrawler_sources` 配置
  - `topic_tagger.py` 增加桌布 tags：拍照出片、价格敏感、尺寸适配
  - 修复 `is_xhs` 平台检测（支持 platform_refs 为 `"xiaohongshu"` 的情况）
  - fixture 数据：5 条桌布 XHS 笔记 + 评论
  - 测试：12 loader + 6 router + 2 pipeline = 20 新增，38 全量通过
- 验收标准：
  - ✅ MediaCrawler fixture 走完整 pipeline，产出 signals + opportunity cards
  - ✅ signals 命中 `category_tablecloth` 实体
  - ✅ topic_tags 包含新增标签（拍照出片/价格敏感/尺寸适配）+ XHS 标签
  - ✅ evidence_refs 不为空
  - ✅ 所有 38 个测试通过，无回归

## Phase 6: 下一步

- review 历史记录
- signal/evidence 级反馈
- 在 MediaCrawler 真实 output 上验证字段映射
- 定时自动执行 TrendRadar + MediaCrawler 抓取 + pipeline 刷新
- 扩展 MediaCrawler 到更多平台（抖音/快手/B站）
- 增量加载优化（基于文件日期/mtime 过滤）
