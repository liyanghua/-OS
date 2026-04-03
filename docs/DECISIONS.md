# 本体大脑情报中枢设计决策

## D-001 不深度侵入 TrendRadar，而是外包 `intel_hub`

- 决策内容：TrendRadar 保持为采集与原始分析底座，`intel_hub` 在外层读取 output。
- 原因：
  - 降低对上游开源项目的耦合与升级成本
  - 让情报对象模型与 UI/API 可以独立演进
- 替代方案：
  - 直接改 TrendRadar 内部 storage/report
  - fork TrendRadar 并把业务逻辑混入其中
- 当前影响：
  - loader 需要兼容 output 格式变化
  - 不依赖 TrendRadar 内部 import
- 后续重审：
  - 当真实 output schema 稳定并且需要更高吞吐时重审

## D-002 第一版先用 SQLite + JSONL

- 决策内容：主存储使用 SQLite，调试快照使用 JSONL。
- 原因：
  - 本地单机部署简单
  - 易于审查输出是否正确
  - 足够支撑 V0.2 的对象量级
- 替代方案：
  - 直接上 Postgres
  - 只用 JSON 文件不入库
- 当前影响：
  - 查询与迁移都保持轻量实现
- 后续重审：
  - 当需要多人协作、并发写入或复杂查询时重审

## D-003 第一版只做 `competitor` / `category` / `platform_policy`

- 决策内容：watchlist 只开放三类。
- 原因：
  - 能覆盖机会、赛道、平台风险三类最常见情报信号
  - 可先验证对象模型与编译链路
- 替代方案：
  - 一次放开更多对象类别
  - 先只做 competitor 单类
- 当前影响：
  - canonical entity 与 dedupe 规则先围绕三类实体组织
- 后续重审：
  - 当反馈需要更细分 taxonomy 时重审

## D-004 Opportunity / Risk 使用 evidence-linked card 结构

- 决策内容：所有 card 必须带 `trigger_signals` 与 `evidence_refs`。
- 原因：
  - 便于人工复核
  - 让卡片不是黑盒摘要，而是可追溯对象
- 替代方案：
  - 只保留摘要文本，不保留证据链
  - 只保留 source URL，不保留 evidence object
- 当前影响：
  - dedupe 也必须保留并合并 evidence refs
- 后续重审：
  - 当 evidence 量级过大时重审分页/聚合策略

## D-005 先做极简 UI，而不是完整工作台

- 决策内容：首版只提供总览和列表页，不做完整工作台。
- 原因：
  - 当前要验证的是对象编译与 review 闭环，不是完整工作台流程
  - 避免把 TrendRadar 接入层误做成业务操作台
- 替代方案：
  - 直接建设多页工作台
  - 完全不做页面，只保留 API
- 当前影响：
  - 页面聚焦查看、筛选与 review 展示
- 后续重审：
  - 当 workflow 扩展到 Phase 5 时重审

## D-006 API 与 HTML 共用同一路径

- 决策内容：`/signals`、`/opportunities`、`/risks`、`/watchlists` 同时承担 JSON API 与 HTML 页面，通过 `Accept` 区分。
- 原因：
  - 满足固定路径要求
  - 避免再造一套 `/api/*` 路由命名
- 替代方案：
  - API 与页面拆成两套路由
- 当前影响：
  - review 展示与 JSON 返回共用同一套查询逻辑
- 后续重审：
  - 当前端独立部署时重审是否拆分 API namespace

## D-007 本地验证使用 Python 3.11

- 决策内容：当前工作站验证采用 `python3.11`。
- 原因：
  - 本机没有 `python3.12`
  - 需要先把依赖安装、测试和 API 启动链路跑通
- 替代方案：
  - 停止实现，等待 3.12 环境
  - 手写无依赖替代层，放弃 FastAPI/Pydantic
- 当前影响：
  - 本地验证说明以 3.11 为准
- 后续重审：
  - 当本机或 CI 提供 3.12 时重审并回对齐

## D-008 review 先做轻量字段回写，而不是完整审批流

- 决策内容：V0.2 只回写 `review_status`、`review_notes`、`reviewer`、`reviewed_at` 等轻量字段。
- 原因：
  - 先验证“卡片可进入人审闭环”是否有价值
  - 避免在没有真实协作流程前引入重审批流设计
- 替代方案：
  - 直接建设审批节点、任务流转和多角色状态机
- 当前影响：
  - Repository 与 API 保持简单
  - HTML 页面只展示 review，不做复杂交互
- 后续重审：
  - 当 review 频次和角色协作稳定后重审

## D-009 canonicalization 先用规则，不上 embedding / entity linking

- 决策内容：V0.2 采用规则化 alias -> canonical entity。
- 原因：
  - 当前实体范围有限，规则实现更可解释、更可测
  - 便于和 watchlist 配置保持一致
- 替代方案：
  - 直接上 embedding/entity linking
- 当前影响：
  - 仍会有跨语言和弱别名漏识别
- 后续重审：
  - 当规则维护成本显著上升时重审

## D-010 dedupe 先做显式规则合并，而不是复杂模型

- 决策内容：按实体/主题/时间窗/title token overlap 做显式 dedupe。
- 原因：
  - 规则可解释，可直接写测试
  - 有利于保护 `evidence_refs` 追溯能力
- 替代方案：
  - 直接用复杂相似度模型或聚类模型
- 当前影响：
  - 某些弱相似标题仍可能漏合并
  - 但误合并风险更低
- 后续重审：
  - 当真实数据量和标题多样性上来后重审

## D-011 桌布 demo 第一轮不用小红书，先用 TrendRadar 默认平台

- 决策内容：桌布情报 demo 第一轮只用 TrendRadar 默认支持的平台。
- 原因：
  - 当前目标是验证接入链路，不是扩平台能力
  - 可避免把精力花在新增抓取适配上
- 替代方案：
  - 先接小红书
  - 先新增自定义平台
- 当前影响：
  - 桌布 demo 的覆盖面受限于默认平台内容密度
- 后续重审：
  - 当默认平台链路稳定后重审是否扩平台

## D-012 桌布 demo 第一轮用 keyword filter，不切 ai

- 决策内容：首轮桌布场景固定使用 keyword filter。
- 原因：
  - 词包更直接、更容易解释和调试
  - 便于对照 output 验证到底是哪里漏命中或噪音过高
- 替代方案：
  - 直接上 ai filter
  - keyword + ai 同时启用
- 当前影响：
  - 词包质量直接决定召回质量
  - 高噪音词需要靠主词共现和后续人工 review 控制
- 后续重审：
  - 当桌布词包跑过真实 output 后重审是否加 ai filter

## D-013 先验证 category intelligence demo，再扩到更深采集

- 决策内容：先把 `category_tablecloth` 作为 category intelligence demo 跑通。
- 原因：
  - 先验证“默认平台 output -> watchlist/mapping -> card -> UI”是否成立
  - 降低一开始就扩到完整行业研究的复杂度
- 替代方案：
  - 一开始就扩到多品类、多品牌、多平台深采集
- 当前影响：
  - 当前 UI 和测试更聚焦 category 维度
- 后续重审：
  - 当桌布 demo 稳定后，再扩 competitor / policy / 多类目组合

## D-014 TrendRadar 放在 third_party/ 子目录，而非 fork 或 submodule

- 决策内容：`git clone` 到 `third_party/TrendRadar`，`.gitignore` 排除。
- 原因：
  - 保持 D-001"不深度侵入"原则
  - 避免 submodule 增加协作复杂度
  - 本地独立 venv 不污染主项目
  - 升级时直接 `git pull`
- 替代方案：
  - git submodule
  - fork 并定制
  - pip install 为库
- 当前影响：
  - 需要手动 clone 和配置
  - output 路径通过 `config/runtime.yaml` 配置
  - litellm 等重型依赖通过 stub 解决，避免安装耗时
- 后续重审：
  - 当需要 CI/CD 自动化或多人协作时重审是否改用 submodule

## D-015 小红书 MediaCrawler 通过桥接层接入 intel_hub，而非直接依赖

- 决策内容：MediaCrawler-main 保持外部独立项目，通过 `xhs_loader.py` + `xhs_aggregator.py` 桥接层读取其产出数据，在 `runtime.yaml` 中配置路径。
- 原因：
  - MediaCrawler 依赖 Playwright + 浏览器登录，运行时环境远比 intel_hub 复杂
  - 评论级数据粒度与信号级不同，需要聚合层将多条评论合成一条笔记级信号
  - 保持"抓取"与"情报分析"两个关注点分离
  - 不引入 MediaCrawler 的重型依赖（httpx/playwright/sqlalchemy 等）到 intel_hub
- 替代方案：
  - 将 MediaCrawler 也放入 third_party/（过重，含浏览器数据目录和 node_modules）
  - 直接 import review_intel 模块（耦合过深，依赖链不可控）
  - 让 MediaCrawler 产出 TrendRadar 兼容格式（改动 MediaCrawler 侧过多）
- 当前影响：
  - 需要先在 MediaCrawler 侧运行抓取，再在 intel_hub 侧刷新 pipeline
  - 数据通过文件系统（events.jsonl / jsonl / sqlite）传递，无实时流
  - `xhs_sources` 配置中使用绝对路径
- 后续重审：
  - 当需要实时流式接入时，考虑用消息队列或共享数据库
  - 当需要多机部署时，考虑用 S3/OSS 共享存储替代本地路径

## D-017 XHS 三维结构化流水线与现有 pipeline 并行

- 决策内容：XHS 三维结构化流水线（V0.5）作为独立 pipeline 与现有 `refresh_pipeline.py` 并行运行。
- 原因：
  - 现有 pipeline 基于扁平 `BusinessSignalFrame`，无法支持三维分离和细粒度证据追溯
  - 独立 pipeline 避免对现有流程的侵入式改动
  - 新 schema 层（`xhs_raw`/`xhs_parsed`/`xhs_signals` 等）与现有 schema 不冲突
  - 新 `extraction/` 目录与现有 `extractor/` 独立
- 替代方案：
  - 直接修改现有 `refresh_pipeline.py` 添加三维分支（侵入大，影响现有功能）
  - 用 LLM 做语义提取（当前阶段规则引擎更可控、可测试）
- 当前影响：
  - `ontology_mapping.yaml` 共享，新增 canonical refs
  - `opportunity_compiler.py` 新增函数，不改动现有函数
  - 需要独立的运行入口 `xhs_opportunity_pipeline.py`
- 后续重审：
  - 当两条 pipeline 产出需要统一展示时重审合并策略
  - 当需要 LLM 语义提取时重审提取器架构

## D-016 MediaCrawler 克隆到 third_party/ 并通过 source_router 接入

- 决策内容：将 MediaCrawler 开源仓库 clone 到 `third_party/MediaCrawler`，通过新增 `mediacrawler_loader.py` 读取其原生笔记级输出（JSON/JSONL/SQLite），通过 `source_router.py` 在 ingest 层与 TrendRadar 汇合。
- 原因：
  - MediaCrawler 原生输出已是笔记级粒度（title/desc/互动数据/标签），无需二次聚合
  - 与 D-014（TrendRadar 放 third_party/）保持一致的接入模式
  - `source_router` 解耦 pipeline 与具体 loader，扩展新源只需增加 loader + 配置
  - 不改动 MediaCrawler 核心代码，升级时直接 `git pull`
- 替代方案：
  - 继续只走 review_intel capture 格式（评论级数据需聚合，间接且低效）
  - 在 refresh_pipeline 中硬编码分支（不可扩展，违反 SRP）
  - 把 MediaCrawler 输出转为 TrendRadar 兼容格式再走 trendradar_loader（不必要的间接层）
- 当前影响：
  - `mediacrawler_sources` 配置了 `output_path` 和 `fixture_fallback`
  - MediaCrawler 需手动运行并维护 Playwright 登录态
  - `.gitignore` 排除 `third_party/MediaCrawler/`
- 后续重审：
  - 当 MediaCrawler 有真实 output 后，验证字段映射准确性
  - 当需要增量加载时，补充 mtime/日期过滤逻辑
  - 当新增平台（抖音/快手等）时，扩展 `mediacrawler_loader` 或新增 loader
