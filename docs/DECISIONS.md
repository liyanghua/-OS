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

## D-016 商业化首版先补平台骨架，而不重写现有编译链

- 决策内容：保留 `intel_hub + content_planning` 主链，在外层新增 `b2b_platform`。
- 原因：
  - 现有 XHS 内容情报与内容策划链已经足够强，不应该为商业化而推翻重做。
  - 当前最大缺口在组织化、审批、权限和计量。
- 替代方案：
  - 直接平台化重构
  - 继续把 B2B 逻辑散落进原有模块
- 当前影响：
  - 改动收敛，原有 API 和对象链可继续工作。
- 后续重审：
  - 当并发和部署复杂度上来后，再评估是否拆服务。

## D-017 试点版先用 header token auth / RBAC

- 决策内容：B2B 试点版采用 `WorkspaceMembership + api_token + headers`。
- 原因：
  - 先验证 workspace 隔离和多角色边界。
  - 不阻塞现有工作台继续迭代。
- 替代方案：
  - 直接上完整登录、密码、SSO
- 当前影响：
  - 当前是试点级 auth，不是企业级安全方案。
- 后续重审：
  - 进入外部真实客户环境前重审。

## D-018 商业化首版先保留 SQLite，但把对象边界和接口先定下来

- 决策内容：B2B 平台对象仍使用 SQLite，本轮不一起切 Postgres / 对象存储 / 分布式 queue。
- 原因：
  - 当前先验证对象模型和 API 面是否成立。
  - 同时切基础设施会显著放大改动面。
- 替代方案：
  - 本轮直接上生产级基础设施
- 当前影响：
  - 试点阶段可运行，但还不具备真正生产级并发与恢复能力。
- 后续重审：
  - 客户试点前优先重审存储和任务编排。
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

## D-018 cross_modal 贯穿全链路 + Projector 拆子函数 (V0.6)

- 决策内容：将 `CrossModalValidation` 作为参数传入 `project_xhs_signals()` 和 `compile_xhs_opportunities()`，而非仅在提取后丢弃。`project_xhs_signals()` 拆分为 8 个独立子函数。
- 原因：
  - cross_modal 校验结果（unsupported_claims、scene_alignment）对本体映射和机会卡置信度有直接影响
  - projector 拆子函数：便于独立测试、独立复用、后续替换为 LLM 映射
  - merge_opportunities 去重：同一篇笔记可能因信号组合相近生成重复卡片
  - suggested_next_step 改为 list：更符合实际操作场景（多条可执行建议）
  - value_proposition_refs 引入 canonical VP 映射（vp_photogenic 等）+ need×style 组合
- 替代方案：
  - cross_modal 只用于 UI 展示，不参与编译逻辑（丢失信息）
  - projector 保持单一函数（难以测试和扩展）
  - 不做 merge_opportunities（可能产生重复卡片）
- 当前影响：
  - `project_xhs_signals()` 新增 `cross_modal` 可选参数，向后兼容
  - `compile_xhs_opportunities()` 新增 `cross_modal` 可选参数，向后兼容
  - `XHSOntologyMapping` 新增 `source_signal_summary` 字段
  - `XHSOpportunityCard` 新增 `content_pattern_refs`/`value_proposition_refs`/`audience_refs`
  - `suggested_next_step` 类型从 `str` 改为 `list[str]`
  - `ontology_mapping.yaml` 新增 `risk_claim_unverified`/`need_size_fit`
  - `opportunity_rules.yaml` 新增 cross_modal 相关阈值和 merge_rules
- 后续重审：
  - 当需要 LLM 语义映射时，可替换单个子函数而非重写整体
  - 当多篇聚合需求出现时，merge_opportunities 可扩展为跨笔记合并

## D-019 先做人工反馈闭环，再做自动质量判定 (V0.7)

- 决策内容：V0.7 先实现最小"检视 + 人工反馈 + 聚合 + 升级"闭环，不做自动质量模型或多人审批流。
- 原因：
  - 机会卡是三维结构化流水线的最终产出，需要人工验证其质量和可执行性
  - 聚合公式简单透明（composite = 0.5×quality + 0.3×actionable + 0.2×evidence），便于后续校准
  - promoted 阈值先取保守值（quality≥7.5, actionable≥60%, evidence≥70%, composite≥0.72），防止低质量卡片流入下游
  - XHSReviewStore 独立于旧 Repository，避免 schema 冲突
  - SQLite 轻量存储足够 MVP 阶段使用
- 替代方案：
  - 自动质量模型（LLM 评分 / 规则打分）—— 缺少训练数据和人工标注基线
  - 多人审批流（角色分配 / 多级审核）—— 当前阶段无需复杂协作
  - 直接在旧 Repository 上扩展 —— schema 不兼容，改动量大
- 当前影响：
  - 新增 `schemas/opportunity_review.py` + `storage/xhs_review_store.py` + 2 个服务
  - `/xhs-opportunities` 路由从 JSON 文件切换到 SQLite store
  - 详情页支持在线提交反馈，提交后自动触发聚合 + 升级判定
- 后续重审：
  - 当收集足够人工反馈后，可训练自动质量模型辅助预筛
  - 当需要多角色协作时，扩展审批流和角色权限
  - 当 promoted 卡片需要进入下游系统时，定义导出接口

## D-020 DeerFlow / Hermes 采用 adapter-first + embedded runtime

- 决策内容：业务代码只依赖本地适配层和 workflow substrate，不直接耦合第三方框架内部 API。
- 原因：
  - 当前产品主语仍然是 `Brief / Strategy / Plan / Asset` 这些业务对象，不是第三方框架的原生 UI 或 runtime。
  - 适配层可以让上游框架升级时只改 adapter，不扩散到 routes / services / templates。
- 替代方案：
  - 直接把 DeerFlow / Hermes 作为主运行时暴露到产品层
  - 完全不引入上游代码，只做概念借鉴
- 当前影响：
  - `third_party/` 负责上游 pin 与引用说明
  - `apps/content_planning/adapters/*` 是唯一合法接入边界
- 后续重审：
  - 当 graph executor / memory runtime 成熟后，再评估是否更深接入上游内部模块

## D-021 统一 stage workflow 采用顺序 writable rollout

- 决策内容：四阶段共用一套 `task/run/discussion/proposal/evaluation` 底座，但只有 `Brief` 首先开放 apply。
- 原因：
  - 可以先验证多 Agent 讨论是否真的提升质量和减少人工编辑
  - 避免 `Brief -> Strategy -> Plan -> Asset` 一次性全可写导致 stale/approval/version 失控
- 替代方案：
  - 四阶段同时开放 proposal apply
  - 只做只读 council，不做 apply
- 当前影响：
  - 先后按 `Brief -> Strategy -> Plan -> Asset` 开放 apply
  - 任一阶段开放可写前，先要求前一阶段通过 `持久化 / partial apply / stale propagation / comparison` gate
  - 当前四个阶段都已接入同一套 substrate，但仍只允许一个阶段作为下一轮新增可写能力的主焦点
- 后续重审：
  - 当 `graph_executor` 与更完整的 approval gate 接入后，重审是否允许多个阶段并行可写

## D-022 评价与对比必须持久化，不能只靠内存 baseline

- 决策内容：baseline / stage_run / comparison / pipeline 统一落库到 `evaluations`。
- 原因：
  - “升级前后是否更好”必须可跨重启复现，不能依赖进程内存
  - 只有持久化后，前端与人工验收才能看到稳定的历史对比
- 替代方案：
  - 用 `_baseline_store` 这类进程内缓存
  - 即算即返，不保留历史结果
- 当前影响：
  - `GET /content-planning/evaluations/{opportunity_id}` 成为标准读取入口
  - comparison 优先读取最近 baseline，而不是假设同一进程还活着
- 后续重审：
  - 当实验量更大时，再拆出专门 experiment store 或报表层

## D-023 Strategy 评分口径升级到 strategy_v2，并与旧四维历史隔离

- 决策内容：`Strategy` 评分本轮直接切到 `strategy_v2` 五维，并且 comparison 只比较相同 `stage + rubric_version` 的结果。
- 原因：
  - `Strategy proposal/apply` 开放后，需要更贴近业务决策与平台适配的评价口径
  - 旧四维（`executability / brief_alignment / creativity`）无法准确衡量策略一致性、平台原生度和品牌守护栏适配
  - 混用新旧口径会让 uplift 结论失真
- 替代方案：
  - 继续沿用旧四维
  - 新旧口径同时参与同一 comparison
- 当前影响：
  - `StageEvaluation` / `StageScorecard` 新增 `rubric_version`
  - `strategy_v1` 历史记录保留可读，但不进入当前 comparison
  - Strategy UI 会明确提示“旧口径不参与当前对比”
- 后续重审：
  - 当 `Plan / Asset` 也升级后，再决定是否给其它阶段引入口径版本化

## D-024 Plan 评分从 content 口径拆出，并以 plan_v1 独立版本化

- 决策内容：`Plan` 不再沿用共享的 `content` 评分口径，而是单独引入 `plan_v1`，并且 comparison 只比较相同 `stage + rubric_version` 的结果。
- 原因：
  - `Plan proposal/apply` 打开后，评价对象已经从“生成产物质量”变成“结构化执行方案质量”
  - `content` 口径更适合标题/正文/图片产出后的评估，不适合衡量 `NotePlan` 的结构完整性和交接就绪度
  - 若继续混用，会让 plan uplift 与 asset uplift 混在一起，无法判断哪一层真的改善
- 替代方案：
  - 继续把 `plan` 映射到 `content`
  - 不做 `rubric_version` 隔离，直接与旧 baseline 比较
- 当前影响：
  - `StageEvaluation` 支持 `plan` 阶段与 `plan_v1`
  - `comparison` 会跳过不兼容的旧 `content/plan` baseline
  - Plan UI 会明确提示“旧口径不参与当前对比”
- 后续重审：
  - 当 `Asset` 也进入 proposal/apply 后，再决定是否把 `content` 完整迁移为 `asset_v1`

## D-025 Asset 评分从 content 口径拆出，并以 asset_v1 独立版本化

- 决策内容：`Asset` 不再沿用共享的 `content` 评分口径，而是单独引入 `asset_v1`，并且 comparison 只比较相同 `stage + rubric_version` 的结果。
- 原因：
  - `Asset proposal/apply` 打开后，评价对象已经是最终可交付资产包，而不是泛化的“内容生成结果”
  - 资产层需要显式衡量标题质量、正文说服力、图位执行指令、品牌守护栏和 production readiness
  - 若继续沿用 `content`，会让 `plan` 与 `asset` 的 uplift 混在一起，无法区分“执行方案变好了”还是“交付资产变好了”
- 替代方案：
  - 继续让 `asset` 映射到 `content`
  - 不做 `rubric_version` 隔离，直接沿用旧 baseline
- 当前影响：
  - `StageEvaluation` 支持 `asset` 阶段与 `asset_v1`
  - comparison 会跳过旧 `content/asset` baseline
  - Asset UI 会明确提示“旧 content 口径不参与当前对比”
- 后续重审：
  - 当 publish feedback 更稳定接回 comparison 后，再评估是否需要把 `asset_v1` 再拆成 `creative_quality` 与 `delivery_readiness` 两层口径

## D-026 内容策划 Agent 性能控制层（Session-first / Fast-Deep / 并行 Council / 超时降级 / 前端延后）

- **决策内容**：在 `content_planning` + `intel_hub` 四阶段工作台引入一层明确的**性能控制策略**，而不是把优化散落在各处 one-off：
  - **Session-first GET**：plain GET 不隐式重编；`?refresh=1` 或显式按钮触发 `build_brief` / `build_note_plan`。
  - **Fast / Deep**：`run-agent` 与 `chat` 默认 `fast`；深分析显式 `deep`；Council 保持多 Agent 能力，并可选用轻量 `run_mode`。
  - **RequestContextBundle**：同一次 API 请求内预装配上下文，经 `AgentContext.extra` 复用，减少重复 memory / object 摘要。
  - **Council 并行**：specialist 意见有界并行，按参与者顺序写回；失败项进入 `failed_participants` 不拖死整轮。
  - **LLM fail-fast**：`LLMRouter` 与 `call_text_llm` 带超时；degraded 时上层可走规则或短响应。
  - **前端延后**：`scheduleDeferred` 延后评分、SSE、skills；Plan 页协同面板不首屏自动拉 `timeline`/`graph`。
- **原因**：
  - 对象工作流与阶段语义已稳定，瓶颈主要在 **重复编译、串行 LLM、阻塞式页面副作用请求**。
  - 需要可文档化、可测试的策略，便于后续调参与监控。
- **替代方案**：
  - 仅加缓存不加语义分层（易不一致）
  - 全面异步化 FastAPI 路由而不先收敛同步 LLM 形态（改动面过大）
- **当前影响**：
  - JSON 响应可带 `timing_ms` / `timing_breakdown`；页面带 `X-Render-Timing-Ms`。
  - 无 provider 或网络失败时，用户仍能得到规则降级与页面渲染（可能伴随日志中的 LLM 异常栈，属预期）。
- **后续重审**：
  - 当接入真实生产可观测性（tracing、SLO）后，收紧超时默认值并区分环境（dev/staging/prod）。

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

## D-017 Council v2：HTTP 四段结构 + 标准化 SSE + 向后兼容

- **决策内容**：
  - **HTTP**：`POST .../discussions` 顶层同时返回 `session`（`CouncilSession`）、`discussion`、`proposal`、`observability`（`CouncilObservability`），与 `docs/council_upgrade_v2.md` 对齐。
  - **SSE**：标准 10 类事件名 `council_session_started` … `council_session_failed`，payload 中带 `event_version: 2`；短期内保留 `council_phase`、`discussion_message` 等旧事件名，避免一次性打断已有订阅端。
  - **编排**：`DiscussionOrchestrator.discuss` 支持 `on_council_event` + `council_session_id`；专家并行前后发 participant / synthesis 粒度事件；路由层在持久化后发 `council_proposal_ready`、`council_session_completed`，异常发 `council_session_failed`。
- **原因**：管理端需要「可观察、可判断、可继续流转」的 Council 对象，而不是仅依赖整轮 HTTP 结束后的单次渲染。
- **替代方案**：只扩 JSON 不扩 SSE（主区仍无法增量感知）；或只发 SSE 不固化 HTTP 形状（契约不清晰）。
- **当前影响**：Brief 页 `content_brief.html` 使用显式 FSM + SSE 增量行 + HTTP 落盘渲染；Strategy/Plan/Asset 等页可复用同一 `session`/`observability` 契约接线。
- **后续重审**：当接入分布式 tracing 时，将 `trace_id` 与外部 APM 对齐；旧 SSE 事件废弃时间表单独公告。
