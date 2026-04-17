# 增长实验室（Growth Lab）技术报告与产品功能实现报告

> 截止日期：2026-04-16  
> 版本：V1.0  
> 报告范围：`apps/growth_lab/` 全部模块，含热点雷达、卖点编译器、主图裂变工作台、前3秒裂变工作台、测试放大板、资产图谱六大功能板块，以及小红书一键发布、数据回采等端到端闭环链路。

---

## 目录

1. [系统概述](#1-系统概述)
2. [技术架构](#2-技术架构)
3. [数据模型](#3-数据模型)
4. [功能模块详述](#4-功能模块详述)
   - 4.1 [热点雷达（Radar）](#41-热点雷达radar)
   - 4.2 [卖点编译器（Compiler）](#42-卖点编译器compiler)
   - 4.3 [主图裂变工作台（Main Image Lab）](#43-主图裂变工作台main-image-lab)
   - 4.4 [前3秒裂变工作台（First 3s Lab）](#44-前3秒裂变工作台first-3s-lab)
   - 4.5 [测试放大板（Test & Learn Board）](#45-测试放大板test--learn-board)
   - 4.6 [资产图谱（Asset Graph）](#46-资产图谱asset-graph)
5. [端到端业务链路](#5-端到端业务链路)
6. [外部集成与第三方服务](#6-外部集成与第三方服务)
7. [API 接口清单](#7-api-接口清单)
8. [存储与数据统计](#8-存储与数据统计)
9. [代码统计与工程质量](#9-代码统计与工程质量)
10. [已知问题与后续规划](#10-已知问题与后续规划)

---

## 1. 系统概述

### 1.1 定位

增长实验室（Growth Lab）是本体大脑 AI-native 经营操作系统中的**热点驱动裂变子系统**，负责从市场信号捕捉到内容生成、发布、测款、数据回采、资产沉淀的完整闭环。

### 1.2 核心业务链

```
热点信号 / 竞品变化 / 跨域灵感
        ↓
    TrendOpportunity（机会卡）
        ↓
    SellingPointSpec（卖点规格）
      ↙           ↘
MainImageVariant   First3sVariant
  （主图裂变）       （前3秒视频裂变）
      ↘           ↙
    TestTask（测款任务）
        ↓
    ResultSnapshot（效果快照）
        ↓
    AmplificationPlan（放大计划）
        ↓
    AssetPerformanceCard → PatternTemplate
       （高表现资产沉淀 → 模式模板提取）
```

### 1.3 用户角色

| 角色 | 主要使用场景 |
|------|-------------|
| 产品研发总监 | 卖点编译、主图裂变、资产复用 |
| 运营与营销总监 | 热点雷达、测款放大、一键发布 |
| 视觉总监 | 主图裂变、前3秒视频、视觉资产管理 |
| CEO | 测试放大板、资产图谱全局纵览 |

---

## 2. 技术架构

### 2.1 整体技术栈

| 层级 | 技术选型 |
|------|----------|
| Web 框架 | FastAPI + Uvicorn (--reload) |
| 前端渲染 | Jinja2 模板 + 原生 JavaScript（无框架依赖） |
| 数据存储 | SQLite (`data/growth_lab.db`)，JSON payload + 索引列模式 |
| LLM 调用 | OpenAI-compatible（通过 OpenRouter 转发）、DashScope |
| 图片生成 | OpenRouter (image models) / DashScope 通义万象 |
| 视频生成 | OpenRouter `bytedance/seedance-2.0-fast` 异步模型 |
| 浏览器自动化 | Playwright (Chromium)，用于小红书发布与数据回采 |
| 静态资源 | FastAPI StaticFiles 挂载 (`/generated-images`, `/generated-videos`, `/source-images`) |

### 2.2 模块架构

```
apps/growth_lab/
├── api/routes.py           ← FastAPI 路由（47 个端点）
├── schemas/                ← Pydantic 数据模型（6 个文件，14+ 个模型）
│   ├── trend_opportunity.py
│   ├── selling_point_spec.py
│   ├── main_image_variant.py
│   ├── first3s_variant.py
│   ├── test_task.py
│   └── asset_performance.py
├── services/               ← 业务逻辑（11 个服务）
│   ├── selling_point_compiler.py      ← 卖点编译（LLM + 规则兜底）
│   ├── selling_point_evaluator.py     ← 卖点评估打分
│   ├── main_image_variant_compiler.py ← 主图变体矩阵编译
│   ├── variant_batch_queue.py         ← 批量生图队列
│   ├── first3s_variant_compiler.py    ← 前3秒钩子脚本生成
│   ├── video_generator.py             ← 视频生成（OpenRouter Seedance）
│   ├── video_processor.py             ← 视频分析（转录+钩子分析）
│   ├── xhs_publisher.py               ← 小红书一键发布（Playwright）
│   ├── note_metrics_syncer.py         ← 小红书数据回采（创作者后台）
│   ├── amplification_planner.py       ← 放大建议生成
│   └── asset_graph_service.py         ← 资产沉淀与模式提取
├── storage/
│   └── growth_lab_store.py            ← SQLite 统一存储层
├── adapters/
│   ├── opportunity_adapter.py         ← 情报中枢机会同步适配
│   └── invokeai_provider.py           ← InvokeAI 生图适配（预留）
└── templates/                         ← 6 个 HTML 页面
    ├── radar.html          (274 行)
    ├── compiler.html       (1183 行)
    ├── main_image_lab.html (985 行)
    ├── first3s_lab.html    (1312 行)
    ├── board.html          (496 行)
    └── asset_graph.html    (283 行)
```

### 2.3 服务间通信

- **前端 → 后端**：标准 REST API（JSON），SSE 流式（编译过程）
- **后端 → LLM**：OpenAI-compatible HTTP API（httpx async）
- **后端 → 小红书**：Playwright 浏览器自动化（storage_state 持久登录）
- **后端 → 视频生成**：OpenRouter Generations API（异步提交→轮询→下载）

---

## 3. 数据模型

### 3.1 核心对象链

| 对象 | Schema | 主键 | 关键字段 |
|------|--------|------|----------|
| **TrendOpportunity** | `trend_opportunity.py` | `opportunity_id` | source_type, freshness_score, relevance_score, actionability_score, status |
| **SellingPointSpec** | `selling_point_spec.py` | `spec_id` | core_claim, supporting_claims, target_people, target_scenarios, shelf_expression, first3s_expression, confidence_score |
| **ExpertAnnotation** | `selling_point_spec.py` | `annotation_id` | spec_id, field_name, annotation_type(insight/correction/risk/template) |
| **PlatformExpressionSpec** | `selling_point_spec.py` | - (嵌入) | platform, expression_type(shelf/first3s/spoken/standard_play), headline, sub_copy, visual_direction |
| **MainImageVariant** | `main_image_variant.py` | `variant_id` | source_selling_point_id, image_variant_spec, generated_image_url, quality_score |
| **VariantVariable** | `main_image_variant.py` | - (嵌入) | dimension(模特/构图/场景等), label, value, locked |
| **ImageVariantSpec** | `main_image_variant.py` | `spec_id` | variables, base_prompt, negative_prompt, style_tags, reference_image_urls, size |
| **First3sVariant** | `first3s_variant.py` | `variant_id` | source_selling_point_id, hook_script, video_prompt, generated_video_url, video_generation_status, publish_count, publish_history |
| **HookScript** | `first3s_variant.py` | `script_id` | opening_line, supporting_line, cta_line, tone, duration_hint_seconds |
| **HookPattern** | `first3s_variant.py` | `pattern_id` | hook_type, conflict_type, visual_contrast, effectiveness_score |
| **TestTask** | `test_task.py` | `task_id` | source_variant_id, variant_type(main_image/first3s), platform, xhs_note_id, xhs_note_url, xhs_review_status, test_window_days |
| **ResultSnapshot** | `test_task.py` | `snapshot_id` | task_id, date, liked_count, collected_count, comment_count, share_count, view_count, rise_fans_count |
| **AmplificationPlan** | `test_task.py` | `plan_id` | based_on_task_id, amplification_type, recommended_actions, priority |
| **AssetPerformanceCard** | `asset_performance.py` | `asset_id` | asset_type, source_variant_id, best_metrics, usage_count, reusable |
| **PatternTemplate** | `asset_performance.py` | `template_id` | template_type, pattern_spec, source_asset_ids, avg_performance |

### 3.2 对象关系图

```
TrendOpportunity (1) ──→ (N) SellingPointSpec
                                    │
                    ┌───────────────┼───────────────┐
                    ↓                               ↓
          MainImageVariant (N)           First3sVariant (N)
                    │                               │
                    └───────────┬───────────────────┘
                                ↓
                       TestTask (1:1 per variant publish)
                                │
                                ↓
                    ResultSnapshot (N per task, time series)
                                │
                                ↓
                     AmplificationPlan (0..1)
                                │
                                ↓
              AssetPerformanceCard ←→ PatternTemplate
```

---

## 4. 功能模块详述

### 4.1 热点雷达（Radar）

**页面**：`/growth-lab/radar` → `radar.html` (274 行)

**功能描述**：
- 展示来自情报中枢（Intel Hub）的小红书机会卡、趋势信号、竞品变化等
- 支持按来源类型筛选（trend / rising_product / competitor_shift / cross_domain_idea / xhs_opportunity）
- 卡片操作：收藏（bookmark）、推进到编译（promote）
- 一键同步情报中枢最新机会数据

**API 端点**（6 个）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/radar/opportunities` | 列出机会（支持 status/source_type 筛选） |
| GET | `/api/radar/opportunities/{opp_id}` | 获取单个机会详情 |
| POST | `/api/radar/opportunities` | 创建机会 |
| POST | `/api/radar/opportunities/{opp_id}/bookmark` | 收藏 |
| POST | `/api/radar/opportunities/{opp_id}/promote` | 推进到编译阶段 |
| POST | `/api/radar/sync-from-intel-hub` | 从情报中枢同步机会 |

**技术实现**：
- `OpportunityAdapter` 负责从 Intel Hub 的 `opportunity_cards.json` 和 `pipeline_details.json` 转换为 `TrendOpportunity` 模型
- 同步时自动关联小红书笔记源图和上下文

**数据统计**：当前库中有 **498 条** 机会记录

---

### 4.2 卖点编译器（Compiler）

**页面**：`/growth-lab/compiler` → `compiler.html` (1183 行)

**功能描述**：
- 从机会卡出发，通过 AI 编译生成结构化卖点规格
- 支持 SSE 流式编译，实时显示编译进度和中间结果
- 编译产出包含：核心卖点声明、支撑声明、目标人群、目标场景、差异化说明、风险提示
- 自动生成四种平台表达规格：货架表达、前3秒表达、口播表达、标准打法表达
- 专家批注系统：支持 insight / correction / risk / template 四种批注类型
- AI 评估打分：多维度评估卖点质量，给出改进建议
- 直接导航到主图工作台 / 前3秒工作台（无需重新编译）

**API 端点**（7 个）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/compiler/specs` | 卖点规格列表 |
| GET | `/api/compiler/specs/{spec_id}` | 单个规格详情 |
| POST | `/api/compiler/specs` | 创建规格 |
| POST | `/api/compiler/compile` | 一次性编译 |
| POST | `/api/compiler/compile-stream` | SSE 流式编译 |
| POST | `/api/compiler/annotations` | 创建专家批注 |
| GET | `/api/compiler/annotations` | 批注列表 |

**核心服务**：

1. **SellingPointCompilerService** (`selling_point_compiler.py`, 508 行)
   - `compile()` / `compile_stream()` — 主编译入口
   - LLM 编译 + 规则兜底策略
   - 支持机会上下文注入（关联的小红书笔记内容、图片等）
   - JSON 结构化输出解析（带容错）

2. **SellingPointEvaluator** (`selling_point_evaluator.py`)
   - 多维度评分：完整性、差异化、可执行性等
   - 生成改进建议和下一步行动

**数据统计**：当前 **12 条**卖点规格，**2 条**专家批注

---

### 4.3 主图裂变工作台（Main Image Lab）

**页面**：`/growth-lab/lab` → `main_image_lab.html` (985 行)

**功能描述**：
- 基于卖点规格，通过变量矩阵（模特、构图、场景、色调等）生成主图变体
- 支持批量生图（可选 2/4/8 张）
- 参考图选择系统：
  - 关联笔记图库：自动加载该卖点关联的小红书素材
  - 全部素材库：浏览所有已采集的小红书图片
  - 弹窗式图片选择器，支持勾选多张参考图
- 生成图片实时预览与画廊展示
- 图片质量评分

**API 端点**（4 个）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/lab/variants` | 主图变体列表 |
| GET | `/api/lab/variants/{variant_id}` | 单个变体详情 |
| POST | `/api/lab/variants` | 创建变体 |
| POST | `/api/lab/generate-batch` | 批量生图 |
| GET | `/api/lab/batch/{batch_id}/status` | 批量任务状态 |

**核心服务**：

1. **MainImageVariantCompiler** (`main_image_variant_compiler.py`)
   - `compile_matrix()` — 将卖点规格编译为变量矩阵，生成多个 `ImageVariantSpec`

2. **VariantBatchQueue** (`variant_batch_queue.py`)
   - `enqueue_batch()` — 并发管理多张图片的生成任务
   - `get_batch_status()` — 查询批量任务进度
   - 使用 ThreadPoolExecutor 并行执行

**图片生成提供商**：
- OpenRouter（主力）
- DashScope 通义万象（备选）

**数据统计**：当前 **4 条**主图变体，**59 张**已生成图片

---

### 4.4 前3秒裂变工作台（First 3s Lab）

**页面**：`/growth-lab/first3s` → `first3s_lab.html` (1312 行)

**功能描述**：
- 基于卖点规格，AI 生成前3秒钩子脚本（开场白 + 支撑句 + CTA）
- 支持多种钩子类型：痛点钩子、场景代入、悬疑反转、数据冲击、社会认同、利益诱惑等
- 视频生成：使用 OpenRouter Seedance 2.0 Fast 模型
  - 支持文生视频（text-to-video）和图生视频（image-to-video）
  - 横屏 (16:9) / 竖屏 (9:16) 切换
  - 参考图选择（首帧画面）
- 生成视频历史管理与预览
- **一键发布到小红书**：
  - 发布内容自动组装（标题、正文、话题标签）
  - 发布前预览与编辑
  - 小红书登录态管理（扫码登录 + storage_state 持久化）
  - 异步发布进度跟踪
  - 发布成功后自动创建测试任务

**API 端点**（10 个）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/first3s/variants` | 前3秒变体列表 |
| GET | `/api/first3s/variants/{variant_id}` | 单个变体详情 |
| POST | `/api/first3s/generate-hooks` | 生成钩子脚本 |
| POST | `/api/first3s/generate-video` | 提交视频生成 |
| GET | `/api/first3s/video-status/{job_id}` | 视频生成状态 |
| POST | `/api/first3s/publish` | 发布到小红书 |
| GET | `/api/first3s/publish-status/{job_id}` | 发布进度 |
| GET | `/api/first3s/publish-preview` | 发布内容预览 |
| GET | `/api/first3s/xhs-login-status` | 登录态检查 |
| POST | `/api/first3s/xhs-login` | 触发扫码登录 |

**核心服务**：

1. **First3sVariantCompiler** (`first3s_variant_compiler.py`)
   - `generate_hook_variants()` — LLM 生成钩子脚本
   - 输出含 HookScript（台词）+ HookPattern（钩子模式分析）

2. **VideoGeneratorService** (`video_generator.py`)
   - `submit_job()` → `poll_status()` → `download_video()` 异步三阶段
   - 调用 OpenRouter `bytedance/seedance-2.0-fast` 模型
   - 视频保存到 `data/generated_videos/{variant_id}/video.mp4`

3. **XHSPublishService** (`xhs_publisher.py`, 547 行)
   - Playwright 自动化发布流程：
     1. 检查登录态 / 触发扫码登录
     2. 导航到创作者发布页
     3. 上传视频文件（多策略：set_input_files / file_chooser / JS 兜底）
     4. 等待视频处理完成
     5. 填写标题、正文
     6. 添加话题标签
     7. 点击发布按钮
     8. 等待发布确认
   - `build_publish_content()` — 自动从卖点规格组装发布内容

**数据统计**：当前 **4 条**前3秒变体，**3 个**已生成视频

---

### 4.5 测试放大板（Test & Learn Board）

**页面**：`/growth-lab/board` → `board.html` (496 行)

**功能描述**：
- 统一管理所有测试任务（主图测款 + 视频测款）
- 小红书笔记关联：
  - 视频发布成功后自动创建测试任务
  - 支持手动绑定笔记 ID（自动从 URL 提取）
  - 显示审核状态：待审核 / 平台审核中 / 审核通过 / 审核拒绝
- **数据回采**（核心功能）：
  - 通过创作者后台 API 回采笔记互动数据
  - 数据源：`/api/galaxy/creator/datacenter/note/base`
  - 指标：观看数、点赞数、收藏数、评论数、分享数、涨粉数
  - 审核状态自动同步（audit_status 0/1/2/3）
- 结果快照时间线展示
- 放大计划生成
- 任务状态流转：draft → active → concluded / amplified / re_variant

**API 端点**（6 个）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/board/tasks` | 测试任务列表 |
| POST | `/api/board/tasks` | 创建测试任务 |
| POST | `/api/board/tasks/{task_id}/result` | 添加结果快照 |
| GET | `/api/board/tasks/{task_id}/results` | 任务结果列表 |
| PATCH | `/api/board/tasks/{task_id}/bind-note` | 绑定小红书笔记 |
| POST | `/api/board/tasks/{task_id}/sync-metrics` | 回采笔记数据 |
| POST | `/api/board/tasks/{task_id}/amplify` | 生成放大计划 |

**核心服务**：

1. **NoteMetricsSyncer** (`note_metrics_syncer.py`, 185 行)
   - 通过 Playwright 打开创作者后台数据中心
   - **主方案**：拦截浏览器发出的 `datacenter/note/base` API 响应
   - **降级方案**：在创作者后台上下文中直接 fetch API
   - 输出：liked_count, collected_count, comment_count, share_count, view_count, rise_fans_count, audit_status, cover_url 等

2. **AmplificationPlanner** (`amplification_planner.py`)
   - `suggest()` — 根据测试结果推荐放大策略

**数据统计**：当前 **1 条**测试任务，**3 条**结果快照

---

### 4.6 资产图谱（Asset Graph）

**页面**：`/growth-lab/assets` → `asset_graph.html` (283 行)

**功能描述**：
- 高表现内容资产自动沉淀
- 模式模板提取（从成功案例中提炼可复用的模式）
- 资产推荐：为新卖点推荐相似的历史高表现资产
- 反馈回流到雷达：将资产洞察反哺到热点捕捉

**API 端点**（5 个）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/assets/cards` | 资产卡片列表 |
| GET | `/api/assets/templates` | 模式模板列表 |
| POST | `/api/assets/promote-high-performers` | 晋升高表现资产 |
| POST | `/api/assets/extract-patterns` | 提取模式 |
| GET | `/api/assets/recommend/{selling_point_id}` | 资产推荐 |
| POST | `/api/loop/feedback-to-radar` | 反馈回雷达 |

**核心服务**：

- **AssetGraphService** (`asset_graph_service.py`)
  - `promote_high_performers()` — 扫描测试结果，自动晋升高表现资产
  - `extract_patterns()` — 从资产中提取可复用模式
  - `recommend_for_selling_point()` — 资产推荐
  - `feedback_to_radar()` — 闭环反馈

**数据统计**：当前 **0 条**资产卡片，**0 条**模式模板（待积累足够测试数据后触发）

---

## 5. 端到端业务链路

### 5.1 完整业务流程

```
┌─────────────────────────────────────────────────────────────────┐
│  情报中枢（Intel Hub）                                           │
│  · 小红书爬虫 → 笔记采集 → 机会挖掘 → opportunity_cards.json     │
└─────────────┬───────────────────────────────────────────────────┘
              ↓  同步 (sync-from-intel-hub)
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 热点雷达                                                │
│  · 浏览机会 → 收藏 / 推进                                        │
└─────────────┬───────────────────────────────────────────────────┘
              ↓  选择机会，触发编译
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: 卖点编译器                                              │
│  · AI 编译 → 结构化卖点规格 → 专家批注 → 质量评估                  │
│  · 输出：货架表达 + 前3秒表达 + 口播表达 + 标准打法                 │
└────────┬────────────────────────────┬───────────────────────────┘
         ↓                            ↓
┌─────────────────────┐   ┌──────────────────────┐
│  Step 3a: 主图工作台  │   │  Step 3b: 前3秒工作台  │
│  · 变量矩阵生图       │   │  · 钩子脚本生成        │
│  · 批量生成 2/4/8    │   │  · Seedance 视频生成   │
│  · 参考图选择         │   │  · 一键发布小红书       │
└────────┬────────────┘   └───────────┬──────────┘
         ↓                            ↓
         │     发布成功自动创建         │
         └──────────→ ←───────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: 测试放大板                                              │
│  · 关联笔记 ID → 数据回采（创作者后台 API）                        │
│  · 观看/点赞/收藏/评论/分享/涨粉 时间线                            │
│  · 审核状态跟踪                                                   │
└─────────────┬───────────────────────────────────────────────────┘
              ↓  高表现 → 晋升
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: 资产图谱                                                │
│  · 高表现资产沉淀 → 模式提取 → 复用推荐 → 反馈回雷达               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 小红书发布闭环（端到端）

```
卖点编译完成
    ↓
前3秒工作台 → 钩子脚本生成 → 视频生成
    ↓
一键发布按钮 → 自动组装内容（标题+正文+话题）→ 发布前预览/编辑
    ↓
检查登录态 → [需要登录] → 扫码登录 → storage_state 保存
    ↓
Playwright 自动化发布：上传视频 → 填写内容 → 添加话题 → 发布
    ↓
发布成功 → 自动创建 TestTask → 关联 variant_id + note_url
    ↓
测试放大板 → 绑定笔记 ID（手动/自动提取）
    ↓
刷新数据 → Playwright 打开创作者后台 → 拦截 datacenter/note/base API
    ↓
写入 ResultSnapshot → 展示互动指标时间线
```

---

## 6. 外部集成与第三方服务

| 服务 | 用途 | 集成方式 |
|------|------|----------|
| **OpenRouter** | LLM 调用（文本生成、卖点编译）| OpenAI-compatible HTTP API |
| **OpenRouter** | 图片生成 | HTTP API，model 可配 |
| **OpenRouter Seedance 2.0** | 视频生成 | 异步 Generations API（submit → poll → download）|
| **DashScope** | 备选 LLM / 图片生成 | HTTP API |
| **小红书创作者平台** | 内容发布 + 数据回采 | Playwright 浏览器自动化 |
| **情报中枢 Intel Hub** | 机会数据源 | 内部 JSON 文件同步 |

### 6.1 LLM 配置

| 环境变量 | 说明 |
|----------|------|
| `OPENAI_BASE_URL` | OpenAI-compatible API 地址（通常指向 OpenRouter） |
| `OPENAI_API_KEY` | API 密钥 |
| `OPENAI_MODEL` | 默认文本模型 |
| `OPENROUTER_API_KEY` | OpenRouter 专用密钥（视频生成等） |
| `OPENROUTER_IMAGE_MODEL` | 图片生成模型 |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope 密钥 |

### 6.2 小红书集成细节

**登录态管理**：
- 持久化文件：`data/sessions/xhs_state.json`
- 登录方式：Playwright 控制 Chromium 浏览器，展示二维码供用户手机扫码
- 自动保存 `storage_state` 供后续发布和数据回采复用

**发布自动化**（`xhs_publisher.py`）：
- 三种上传策略：直接 `set_input_files`、`file_chooser` 事件、JS 兜底
- 视频处理等待（含重新上传检测）
- 话题标签：输入 `#` 触发下拉选择

**数据回采**（`note_metrics_syncer.py`）：
- 数据源切换：从公开页 `/explore/` → 创作者后台 `creator.xiaohongshu.com`
- API：`/api/galaxy/creator/datacenter/note/base?note_id=...`
- 优势：无需签名、支持审核中笔记、数据更全面

---

## 7. API 接口清单

路由前缀：`/growth-lab`，共 **47 个端点**。

### 7.1 页面路由（6 个 GET）

| 路径 | 页面 |
|------|------|
| `/radar` | 热点雷达 |
| `/compiler` | 卖点编译器 |
| `/lab` | 主图裂变工作台 |
| `/first3s` | 前3秒裂变工作台 |
| `/board` | 测试放大板 |
| `/assets` | 资产图谱 |

### 7.2 数据 API（41 个）

| 模块 | 端点数 | 覆盖操作 |
|------|--------|----------|
| Radar（机会） | 6 | CRUD + 收藏/推进/同步 |
| Compiler（编译） | 7 | 规格 CRUD + 编译 + 流式编译 + 批注 |
| Lab（主图） | 5 | 变体 CRUD + 批量生图 + 状态查询 |
| First3s（前3秒） | 10 | 变体列表 + 钩子生成 + 视频生成/状态 + 发布/状态/预览 + 登录 |
| Board（测试） | 7 | 任务 CRUD + 结果 + 绑定笔记 + 数据回采 + 放大 |
| Assets（资产） | 5 | 卡片/模板列表 + 晋升 + 提取 + 推荐 |
| Loop（闭环） | 1 | 反馈回雷达 |

---

## 8. 存储与数据统计

### 8.1 存储架构

| 存储 | 路径 | 说明 |
|------|------|------|
| 主数据库 | `data/growth_lab.db` | SQLite，10 张表 |
| 生成图片 | `data/generated_images/` | 按批次/机会 ID 分目录 |
| 生成视频 | `data/generated_videos/` | 按 variant_id 分目录 |
| 源图素材 | `data/source_images/` | 按机会 ID 分目录 |
| 会话状态 | `data/sessions/xhs_state.json` | 小红书 Playwright 登录态 |

### 8.2 数据库表清单

| 表名 | 主键字段 | 当前记录数 |
|------|----------|-----------|
| `trend_opportunities` | `opportunity_id` | 498 |
| `selling_point_specs` | `spec_id` | 12 |
| `main_image_variants` | `variant_id` | 4 |
| `first3s_variants` | `variant_id` | 4 |
| `test_tasks` | `task_id` | 1 |
| `result_snapshots` | `snapshot_id` | 3 |
| `amplification_plans` | `plan_id` | 0 |
| `asset_performance_cards` | `asset_id` | 0 |
| `pattern_templates` | `template_id` | 0 |
| `expert_annotations` | `annotation_id` | 2 |

### 8.3 文件资产统计

| 类型 | 数量 | 存储位置 |
|------|------|----------|
| 已生成图片 | 59 张 | `data/generated_images/` |
| 已生成视频 | 3 个 | `data/generated_videos/` |
| 采集源图 | 17 张 | `data/source_images/` |
| 登录会话 | 2 文件 | `data/sessions/` |

---

## 9. 代码统计与工程质量

### 9.1 代码行数

| 类型 | 文件数 | 总行数 |
|------|--------|--------|
| Python (`.py`) | 27 | 5,332 |
| HTML (`.html`) | 6 | 4,533 |
| **合计** | **33** | **9,865** |

### 9.2 关键文件规模

| 文件 | 行数 | 职责 |
|------|------|------|
| `api/routes.py` | 1,195 | 全部 47 个 API 端点 |
| `templates/first3s_lab.html` | 1,312 | 前3秒工作台前端（含视频生成 + 发布流程） |
| `templates/compiler.html` | 1,183 | 卖点编译器前端（含 SSE 流式 + 专家批注） |
| `templates/main_image_lab.html` | 985 | 主图工作台前端（含参考图选择器） |
| `services/xhs_publisher.py` | 547 | 小红书发布自动化 |
| `services/selling_point_compiler.py` | 508 | 卖点 AI 编译核心逻辑 |
| `templates/board.html` | 496 | 测试放大板前端 |
| `storage/growth_lab_store.py` | ~350 | SQLite 存储层 |

### 9.3 架构质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 模块分离 | ★★★★☆ | schemas / services / storage / api / templates 职责清晰 |
| 类型安全 | ★★★★☆ | 全部使用 Pydantic v2 严格类型定义 |
| API 设计 | ★★★★☆ | RESTful 风格，命名一致，请求/响应模型完整 |
| 错误处理 | ★★★☆☆ | 核心路径有 try/except + HTTPException，部分边缘场景可增强 |
| 可测试性 | ★★★☆☆ | 服务层可独立测试，但缺少单元测试文件 |
| 前端代码 | ★★★☆☆ | 原生 JS 无框架，功能完整但大文件可拆分 |
| 文档 | ★★★★★ | 完整的 PRD + 架构文档 + 21 个计划文件 |

---

## 10. 已知问题与后续规划

### 10.1 已修复的重要问题

| # | 问题 | 根因 | 修复方案 |
|---|------|------|----------|
| 1 | 视频发布后报"文件不存在" | Web URL 路径未转换为文件系统绝对路径 | 在 routes.py 中增加路径转换逻辑 |
| 2 | Playwright `storage_state` 参数错误 | 误用 `launch_persistent_context` | 改用 `launch()` + `new_context(storage_state=...)` |
| 3 | 视频上传超时 | 单一上传策略不够健壮 | 三策略上传（set_input_files / file_chooser / JS 兜底） |
| 4 | 数据回采 HTTP 500 | 公开页 API `/api/sns/web/v1/feed` 需要签名 | 改用创作者后台 API `datacenter/note/base`，无需签名 |
| 5 | 审核中笔记无法回采 | 公开页显示"暂时无法浏览" | 创作者后台 API 不受审核状态影响 |

### 10.2 当前限制

1. **无自动定时回采**：数据回采需手动点击"刷新数据"，暂无定时任务调度
2. **放大计划未实际使用**：`AmplificationPlan` 模型和服务已就绪，但缺少足够测试数据触发
3. **资产沉淀待积累**：`AssetPerformanceCard` 和 `PatternTemplate` 表为空，需足够的高表现测试结果
4. **单用户模式**：当前无多用户/多工作区隔离
5. **前端无框架**：原生 JS 在大页面（1000+ 行）中维护成本增加

### 10.3 建议后续方向

| 优先级 | 方向 | 说明 |
|--------|------|------|
| P0 | 定时数据回采 | 对活跃测试任务定时回采互动指标，构建时间线 |
| P0 | 放大决策自动化 | 基于回采数据自动触发放大/止损建议 |
| P1 | 资产沉淀闭环 | 测试结果 → 高表现自动晋升 → 模式提取 → 推荐复用 |
| P1 | 批量发布 | 支持多个视频变体一键批量发布 |
| P2 | 主图发布链路 | 主图变体 → 电商平台上架（如淘宝/拼多多主图替换） |
| P2 | A/B 测试对比 | 同一卖点不同变体间的对照测试支持 |
| P3 | 前端组件化 | 迁移到 React/Vue 组件体系，提升可维护性 |

---

## 附录 A：依赖清单

**核心依赖**（`pyproject.toml`）：

| 包 | 版本要求 |
|-----|---------|
| fastapi | ≥0.115, <1.0 |
| uvicorn | ≥0.35, <1.0 |
| pydantic | ≥2.11, <3.0 |
| httpx | ≥0.28, <1.0 |
| jinja2 | ≥3.1, <4.0 |
| numpy | ≥1.26, <3 |
| pyyaml | ≥6.0, <7.0 |
| scikit-learn | ≥1.3, <2 |

**可选依赖**：

| 分组 | 包 |
|------|----|
| `llm-openai` | openai ≥1.0, <2.0 |
| `llm-anthropic` | anthropic ≥0.40, <1.0 |
| `browser` | playwright ≥1.45, <2.0 |

---

## 附录 B：环境变量清单

| 变量名 | 用途 |
|--------|------|
| `OPENAI_BASE_URL` | OpenAI-compatible API 地址 |
| `OPENAI_API_KEY` | API 密钥 |
| `OPENAI_MODEL` | 默认文本模型名 |
| `OPENROUTER_API_KEY` | OpenRouter 专用密钥 |
| `OPENROUTER_IMAGE_MODEL` | 图片生成模型名 |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope 密钥 |

---

> **报告生成时间**：2026-04-16  
> **代码库版本**：基于当前工作目录最新代码
