# 本体大脑情报中枢 · 信息架构（主视角主线版）

本文是系统的 **页面 IA 源头**，所有导航、面包屑、跳转都以此为准。旧的 V0.8 只读架构（Signals / Opportunities / Risks / Watchlists 四平铺）作为数据对象后台保留，但不再是主导航。

## 用户主视角：三条主线 + 一个资产中枢

```
   主线 1 · 内容生产（图文笔记）                                       主线 3 · 套图生产
   /notes  →  /category-lenses  →  /xhs-opportunities                   /growth-lab/workspace
       →  /xhs-opportunities/{id}  →  /planning/{id}  →  /planning/{id}/visual-builder
                                                                          ↘
   主线 2 · 增长实验室（极速上线）                                         → /asset-workspace（系统资产统一视图）
   /growth-lab/radar  →  /growth-lab/compiler  →  /growth-lab/lab    ↗
       →  /growth-lab/first3s  →  /growth-lab/board  →  /growth-lab/assets
```

- **所有主线的产物都沉淀到 `/asset-workspace`**，以 SystemAsset 模型统一编排，通过 `source_lane` 区分 `content_note` / `growth_lab` / `workspace_bundle`。
- **/** (首页) 只做三主线入口 + 系统资产/反馈/审批 快捷入口 + 采集和运维状态。

## 顶级导航

在 `apps/intel_hub/api/templates/base.html` 中定义：

| 顶栏条目 | 激活规则（`pathname` 前缀判断） | 子菜单 / 跳转 |
|---|---|---|
| **内容生产 ▾** | `/`、`/notes*`、`/category-lenses*`、`/xhs-opportunities*`、`/planning/*`、`/content-planning/*`、`/asset-workspace?lane=content_note` | 素材中心 / 类目透视 / 机会卡看板 / 策划台队列 / 图文资产 |
| **增长实验室 ▾** | `/growth-lab/radar`、`/compiler`、`/lab`、`/first3s`、`/board`、`/assets` | 热点雷达 / 卖点编译 / 主图裂变 / 前3秒裂变 / 测试放大 / 实验资产图谱 |
| **套图工作台** | `/growth-lab/workspace` | （直链无下拉） |
| 系统资产 | `/asset-workspace` | 右侧快捷入口 |
| 结果反馈 | `/feedback` | 右侧快捷入口 |
| 更多 ▾ | — | 策划工具 / 协同管理 / 数据对象（Signals、Opportunities、Risks、Watchlists、RSS）|

激活态由 base.html 末尾的 JS 根据 `window.location.pathname` 自动加 `aria-current="page"`。

## 主线 1：内容生产（图文笔记）

| 阶段 | 路由 | 模板 | 关键能力 |
|---|---|---|---|
| 1 · 素材 | `/notes`（可选 `?platform=xhs|dy` / `?lens=<lens_id>` / `?q=` / `?category=<keyword>`） | `notes.html` | 平台 Tab + 类目 Tab（`CategoryLens`）+ 采集关键词二级过滤 |
| 1b · 详情 | `/notes/{note_id}` | `note_detail.html` | 右栏直达该 note 的类目透视、相关机会卡 |
| 2 · 类目透视 | `/category-lenses`、`/category-lenses/{lens_id}` | `category_lenses.html`, `category_lens_detail.html` | lens 配置 + 五层模型静态展示 |
| 3 · 机会卡看板 | `/xhs-opportunities?lens=<id>&status=&type=` | `xhs_opportunities.html` | 类目摘要卡片、lens 过滤后 `type` 动态导航、分页保留 lens |
| 3b · 机会卡详情 | `/xhs-opportunities/{opportunity_id}` | `xhs_opportunity_detail.html` | 五层模型渲染、检视反馈表单、晋升后 CTA → `/planning/{id}` |
| 4 · 策划台 | `/planning/{opportunity_id}` | `planning_workspace.html` | brief / strategy / plan / assets 作为策划台内 tab，AI 检视、委员会 |
| 5 · 视觉 | `/planning/{opportunity_id}/visual-builder` | `visual_builder.html` | 三栏 prompt 工作区，quick-draft / image-gen 走 `/content-planning/v6/*` |
| 6 · 资产 | `/asset-workspace?lane=content_note&opportunity_id=` | `asset_workspace_list.html` | SystemAsset 中 `source_lane=content_note` 的聚合视图 |

**晋升流程**（不变）：机会卡详情 POST `/xhs-opportunities/{id}/reviews` → `OpportunityPromoter` 按阈值（`min_quality_avg=7.5`、`min_actionable_ratio=0.6`、`min_evidence_ratio=0.7`、`min_composite_score=0.72`）升级为 `promoted`；达成后主 CTA 改指向 `/planning/{id}`。

## 主线 2：增长实验室（极速上线）

所有 growth-lab 页面共用顶部 `_lane_bar.html` 步骤条，当前步骤高亮。

| 阶段 | 路由 | 模板 | 下一步 |
|---|---|---|---|
| 1 · 热点雷达 | `/growth-lab/radar` | `radar.html` | → 卖点编译（带 spec_id）|
| 2 · 卖点编译 | `/growth-lab/compiler` | `compiler.html` | → 主图裂变 / 前3秒裂变 |
| 3 · 主图裂变 | `/growth-lab/lab` | `main_image_lab.html` | → 测试放大 |
| 4 · 前3秒裂变 | `/growth-lab/first3s` | `first3s_lab.html` | → 测试放大 |
| 5 · 测试放大 | `/growth-lab/board` | `board.html` | → 实验资产图谱 / 系统资产 |
| 6 · 实验资产图谱 | `/growth-lab/assets` | `asset_graph.html` | 产物写入 SystemAsset（`source_lane=growth_lab`）|

## 主线 3：套图工作台

| 路由 | 模板 | 核心能力 |
|---|---|---|
| `/growth-lab/workspace` | `workspace.html` | SVG 无限画布 + Agent 对话；输出模式：`main_image`(主图5张) / `detail`(详情9模块) / `video_shots`(视频分镜) / `buyer_show`(买家秀8张) / `competitor`(竞品对标)；发布后写入 SystemAsset（`source_lane=workspace_bundle`）|

## 系统资产（统一视图）

- `/asset-workspace` 读取 `SystemAssetService.list_assets(lane=?, lens=?, status=?)`，聚合三处：
  1. `content-planning` 的 `asset_bundle`（主线 1 产物）
  2. `growth-lab` 的 `asset_graph` 数据（主线 2 产物）
  3. `growth-lab/workspace` 的 publish 产物（主线 3 产物）
- 模板 `asset_workspace_list.html` 顶部 Tab：**全部 / 图文笔记 / 增长实验 / 套图**，同时支持 `lens` / `asset_type` / `status` 过滤。
- 每个 SystemAsset 卡显示血缘链接：跳转回 brief / visual_pattern / test_id。
- `GET /api/system-assets` 提供 JSON API 供其他页面调用。

### SystemAsset 字段（权威定义）

| 字段 | 类型 | 说明 |
|---|---|---|
| `asset_id` | str | 全局唯一 |
| `source_lane` | Literal | `content_note` / `growth_lab` / `workspace_bundle` |
| `source_ref` | str | opportunity_id / spec_id / workspace_project_id |
| `lens_id` | str \| None | 归属类目透视（若有）|
| `asset_type` | Literal | `xhs_note` / `main_image_set` / `detail_gallery` / `video` / `buyer_show` / `competitor_benchmark` |
| `title` | str | 展示标题 |
| `thumbnails` | list[str] | 缩略图 URL |
| `status` | Literal | `draft` / `ready` / `published` / `archived` |
| `lineage` | dict | 上下游链接（brief、strategy、visual_pattern、test_id）|
| `created_at` | datetime | 创建时间 |

## 数据对象后台（旧 V0.8 只读架构，保留）

- `/signals` / `/opportunities` / `/risks` / `/watchlists`：沿用原只读表视图，作为"更多 → 数据对象"二级入口。
- `/signals?entity=category_tablecloth` 等桌布快捷链接保留。
- Review 更新仍走 API（`POST /opportunities/{id}/review`、`POST /risks/{id}/review`）。

## API 与页面路由策略

- 同路径双视图：
  - 程序调用（`Accept: application/json`）默认返回 JSON
  - 浏览器（`Accept: text/html`）返回 HTML
- 保留固定 API 路径，不新增第二套路由命名。

## 跨主线共享片段

| 片段 | 用途 |
|---|---|
| `apps/growth_lab/templates/_lane_bar.html` | 主线 2 步骤条（radar → compiler → lab → first3s → board → assets）|
| `apps/intel_hub/api/templates/_lane_bar.html` | 主线 1 步骤条（notes → category-lenses → xhs-opportunities → planning → visual-builder → asset-workspace）|

激活步骤通过 include 时传入 `lane_step=<阶段 id>` 决定高亮。
