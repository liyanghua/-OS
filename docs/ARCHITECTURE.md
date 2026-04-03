# 本体大脑情报中枢 V0.2 架构

## 总体架构

系统保持“外部采集底座 + 外层情报编译模块”的结构：

1. 外部采集器（TrendRadar / MediaCrawler）：抓取各平台内容，输出本地文件或 SQLite。
2. `apps/intel_hub/ingest`：通过 `source_router` 统一收集各采集器产出，按来源解析为 raw signal dict。
3. `apps/intel_hub/normalize`：归一化为 `Signal` / `EvidenceRef`。
4. `apps/intel_hub/projector`：做 canonical entity projection 与 topic tagging。
5. `apps/intel_hub/compiler`：打分、规则 dedupe、编译机会/风险卡。
6. `apps/intel_hub/storage`：SQLite 持久化与 review writeback。
7. `apps/intel_hub/api`：提供 JSON API 与极简 HTML 页面。

## 采集器与 intel_hub 的职责边界

- TrendRadar：
  - 多平台热点/新闻/RSS 采集
  - 原始 output 落盘（`output/news/*`、`output/rss/*`）
- MediaCrawler：
  - 小红书等社媒平台的笔记/评论采集（基于 Playwright 登录态）
  - 原始 output 落盘（`data/xhs/jsonl/*`、`data/xhs/json/*`、`database/sqlite_tables.db`）
- intel_hub：
  - 通过 `source_router.py` 统一消费各采集器 output
  - 不 import 任何采集器内部模块
  - 输出统一对象与 evidence-linked cards
  - 提供人工 review 回写

MediaCrawler 不经过 TrendRadar，作为独立 source adapter 直接接入 ingest 层。

## source_router 双源架构

`ingest/source_router.py` 是统一的 raw signal 收集入口：

1. TrendRadar 路径：`trendradar_loader.load_latest_raw_signals()`
2. MediaCrawler 路径：`mediacrawler_loader.load_mediacrawler_records()`（读取原生笔记级输出）
3. XHS capture 路径（兼容旧逻辑）：`xhs_loader + xhs_aggregator`

`refresh_pipeline.py` 只需调用 `collect_raw_signals(settings)`，不再硬编码各 loader 分支。

## 数据流

`raw signal -> normalized signal -> projected signal -> deduped cards -> reviewed cards`

### TrendRadar 默认平台桌布链路

本轮桌布 demo 的真实接入口径为：

`TrendRadar 默认平台 -> keyword filter -> output -> intel_hub refresh_pipeline -> UI`

- TrendRadar 侧：
  - 使用默认支持平台
  - 使用 `current + keyword`
  - 外部手动运行，不在本仓库内改源码
- intel_hub 侧：
  - 读取 output
  - 将桌布相关内容映射为 `category_tablecloth`
  - 在 `/signals`、`/opportunities`、`/risks` 中按 entity / platform 查看

### 1. Raw signal adapter

- 输入来源：
  - TrendRadar: `output/news/*`、`output/rss/*`
  - MediaCrawler: `data/xhs/jsonl/*`、`data/xhs/json/*`、`database/sqlite_tables.db`
- 当前兼容：
  - `.json`
  - `.jsonl`
  - `.db`
- 最新批次选择：
  - 先按 `news` / `rss` 分目录找最新日期/时间戳
  - 同批多文件时按文件名中的日期优先，再按 mtime 兜底

### 2. `.db` 解析策略

- 若存在 `news_items`：
  - 读取 `news_items`
  - 关联 `platforms`
  - 若存在 `rank_history`，取每条 news item 最新 rank 记录补齐 `rank` / `score`
- 若存在 `rss_items`：
  - 读取 `rss_items`
  - 关联 `rss_feeds`
- 若都不命中：
  - 回退通用 SQLite 表扫描

### 3. Best effort 字段保留

loader 尽量保留这些字段，缺失不报错：

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

已知不确定性：

- 真实 TrendRadar `.db` 列名可能继续演化
- 同名表在不同版本中可能补/删字段
- 因此 `.db` 解析采用“探测表和列 -> best effort 映射 -> 回退通用扫描”的策略

## Canonical entity projection

- 输入：
  - normalized signal
  - `config/watchlists.yaml`
  - `config/ontology_mapping.yaml`
- 过程：
  - 文本标准化
  - alias 命中
  - canonical entity id 归一
  - 同类型实体去重
- 输出：
  - `raw_entity_hits`
  - `canonical_entity_refs`
  - `entity_refs`（继续保留为 canonical 结果，兼容旧接口）

桌布 demo 相关配置位置：

- `config/watchlists.yaml`
  - `category_tablecloth`
- `config/ontology_mapping.yaml`
  - `entities.category_tablecloth`
  - `platform_refs.zhihu/douyin/bilibili/tieba/toutiao/weibo/...`

桌布 demo 相关 topic tags 由 `projector/topic_tagger.py` 的轻量规则补充：

- `风格偏好`
- `材质偏好`
- `清洁痛点`
- `场景改造`
- `内容钩子`
- `拍照出片`
- `价格敏感`
- `尺寸适配`

小红书平台还会附加 XHS review tags：`用户真实体验`、`购买意向`、`负面反馈`、`推荐种草`。

## Card dedupe / compiler

- 输入：projected signal + `config/scoring.yaml` + `config/dedupe.yaml`
- 规则：
  - 同 canonical 主实体
  - 同主主题
  - 同时间窗（默认 72h）
  - 标题 token overlap 达阈值
- 输出：
  - `OpportunityCard`
  - `RiskCard`
  - 附带 `dedupe_key`
  - 附带 `merged_signal_ids`
  - 附带 `merged_evidence_refs`

所有 card 继续保留：

- `trigger_signals`
- `evidence_refs`

## Review writeback 流程

1. 客户端调用 `GET /opportunities` 或 `GET /risks` 查看卡片。
2. 人工判断后调用 `POST /opportunities/{id}/review` 或 `POST /risks/{id}/review`。
3. API 校验请求体并补 `reviewed_at`。
4. Repository 更新 SQLite 中对应 card 的 payload 与索引列。
5. 后续 GET 与 HTML 页面读取回写结果。

当前只做轻量字段回写，不做审批流。

## 存储方式

- 主存储：`data/intel_hub.sqlite`
- 调试快照：`data/raw/latest_raw_signals.jsonl`
- 配置：
  - `config/watchlists.yaml`
  - `config/ontology_mapping.yaml`
  - `config/scoring.yaml`
  - `config/dedupe.yaml`
  - `config/runtime.yaml`

SQLite 表仍为：

- `signals`
- `evidence_refs`
- `opportunity_cards`
- `risk_cards`
- `watchlists`

迁移策略为轻量自迁移：启动时检测并补列，不引入迁移框架。

## API 与前台关系

- 同一 FastAPI 应用提供 API 与 HTML。
- 页面：
  - `/`
  - `/signals`
  - `/opportunities`
  - `/risks`
  - `/watchlists`
- API：
  - `GET /signals`
  - `GET /opportunities`
  - `GET /risks`
  - `GET /watchlists`
  - `POST /opportunities/{id}/review`
  - `POST /risks/{id}/review`

本轮新增列表过滤能力：

- `entity`
- `topic`
- `platform`
- `review_status`
- `reviewer`

## 已知局限

- canonicalization 与 dedupe 仍是显式规则，不处理跨语言语义相似度。
- review 只更新卡片，不回写 signal/evidence 或更下游 workflow。
- 桌布 demo 当前优先验证 category intelligence，不追求覆盖完整家居内容生态。
- MediaCrawler 需手动运行并维护 Playwright 登录态，无定时调度。
- MediaCrawler 与 intel_hub 之间通过文件系统传递，无实时流。
