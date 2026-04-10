# 本体大脑情报中枢 V0.8 Pilot Foundation

> 当前主线已经从早期 TrendRadar 情报编译层，升级为「XHS 内容情报编译引擎 + 内容策划链 + B2B 试点平台骨架」。

## 产品名称与定位

- 产品名：本体大脑情报中枢 V0.2
- 定位：构建在 TrendRadar 之外的轻量情报编译层，把热点、新闻、RSS output 转成统一的 `Signal`、`EvidenceRef`、`OpportunityCard`、`RiskCard`，并补上初步人工 review 闭环。
- 边界：TrendRadar 继续负责采集与原始分析；`intel_hub` 负责 output 接入、归一化、投影、卡片编译、SQLite/API/UI 与 review writeback。

## 解决什么问题

- 原始 output 直接进入产品/架构讨论时，存在对象不统一、别名噪音、重复卡片和无法回写人工判断的问题。
- 情报团队需要一个可以“看结果 + 做轻量 review + 保留证据链”的中间层，而不是完整工作台。

## 目标用户

- 产品负责人：看机会卡、风险卡与证据出处。
- 架构负责人：看赛道、竞品、平台政策变化。
- 情报运营：维护 watchlist、处理重复卡、回写人工 review。

## MVP / V0.2 范围

- 读取 TrendRadar `output/news`、`output/rss` 最新批次。
- 兼容 `.json`、`.jsonl`、`.db`，并对公开 SQLite schema 做专用映射。
- 归一化为统一 `Signal` / `EvidenceRef`。
- 基于 watchlist 与 ontology mapping 做 canonical entity projection。
- 编译 `OpportunityCard` / `RiskCard`，保留 `trigger_signals` 与 `evidence_refs`。
- 增加 card review writeback：`pending` / `accepted` / `rejected` / `needs_followup`。
- 增加显式规则 dedupe，减少别名与近似标题导致的重复卡片。
- 提供本地 SQLite、JSON API 与极简 HTML 页面。
- 新增桌布情报 demo：通过 TrendRadar 默认平台 + keyword filter 验证 category intelligence 链路。

## 非目标范围

- 不改 TrendRadar 抓取、过滤、AI 分析内部逻辑。
- 不接小红书，不新增自定义抓取平台。
- 不做完整审批流、权限系统、多租户、消息队列或迁移框架。
- 不做 embedding/entity linking/复杂模型去重。

## 核心价值

- 把 TrendRadar output 从“信息流”整理为“对象流”。
- 让每张机会/风险卡都可追溯到 `evidence_refs`。
- 让“查看情报”升级成“初步 review 闭环”。
- 通过 canonical entity 与规则 dedupe 降低重复卡和别名噪音。
- 用一个可运行的桌布 category demo 验证“默认平台 output -> 情报对象 -> UI 查看”链路。

## 首版对象

- `Signal`
- `EvidenceRef`
- `OpportunityCard`
- `RiskCard`
- `Watchlist`

## 首版 watchlist 范围

- `competitor`
- `category`
- `platform_policy`

## 桌布情报接入 Demo

- 目标：不改 TrendRadar 核心逻辑，只利用默认平台、keyword filter 和现有 `intel_hub` 链路，稳定看到桌布相关 `signals / opportunities / risks`。
- category 实体：`category_tablecloth`
- 首轮平台建议：
  - 默认启用：`zhihu`、`douyin`、`bilibili`、`tieba`、`toutiao`、`weibo`
  - 可选启用：`baidu`、`thepaper`、`ifeng`
  - 暂不重点依赖：`wallstreetcn`、`cls`
- 首轮词包见：
  - `docs/examples/trendradar_tablecloth_config_snippet.yaml`
  - `docs/examples/frequency_words_tablecloth_v1.txt`
- 这是一个基于 TrendRadar 默认平台的 category intelligence demo，不是完整行业采集方案。

## 当前状态

- 已完成 ingest -> normalize -> canonicalize/project -> rank -> dedupe/compile -> storage -> API/UI 全链路。
- 已支持 `POST /opportunities/{id}/review` 与 `POST /risks/{id}/review`。
- 已补齐贴近公开 schema 的 `.json/.jsonl` fixture，以及测试内生成的 `.db` fixture。
- 当前默认仍读取 `data/fixtures/trendradar_output/output`；真实接入通过 `config/runtime.yaml` 切换 `trendradar_output_dir`。
- 已新增桌布场景 fixture 与 `category_tablecloth` watchlist / mapping，可通过 `entity=category_tablecloth` 在 UI 查看。

## V0.8 商业化试点骨架

- 新增 `apps/b2b_platform`：
  - `Organization`
  - `Workspace`
  - `BrandProfile`
  - `Campaign`
  - `WorkspaceMembership`
  - `Connector`
  - `OpportunityQueueEntry`
  - `ApprovalRecord`
  - `UsageEvent`
  - `PublishResult`
- 现有 `OpportunityBrief` / `RewriteStrategy` / `NewNotePlan` / `AssetBundle` 已可挂到：
  - `workspace_id`
  - `brand_id`
  - `campaign_id`
- 已支持：
  - workspace bootstrap
  - promoted 机会卡进入品牌队列
  - 内容对象审批
  - 生成与导出的用量记账

## 相关架构文档

- 内容策划四阶段工作台与 Agent 性能控制层（Session-first、Fast/Deep、并行 Council、超时降级、前端延后）：见 [`ARCHITECTURE_V2.md`](ARCHITECTURE_V2.md)。

## 当前边界

- 这是试点可售版地基，不是完整企业版平台。
- 当前仍使用 SQLite，本轮不替换为 Postgres / 对象存储 / 分布式 worker。
- 当前 auth 为 header token + role，主要用于验证 workspace 隔离与协作边界。
