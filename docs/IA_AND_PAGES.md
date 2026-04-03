# 本体大脑情报中枢 V0.2 信息架构

## 首版信息架构

- `/`
  - 今日新增 Signals
  - Opportunities
  - Risks
  - Watchlists
- `/signals`
- `/opportunities`
- `/risks`
- `/watchlists`

仍是极简查看层，不扩成完整工作台。

## 导航结构

- 总览
- Signals
- Opportunities
- Risks
- Watchlists

## 页面清单

### `/`

- 目标：快速看到当日情报对象总量和各类卡片摘要。
- 输入：SQLite 中四类对象的第一页结果。
- 输出：总数卡片、摘要卡片、evidence refs 和已回写的 review 信息。

### `/signals`

- 目标：查看归一化后的原子信号。
- 输入：`signals` 表。
- 输出：标题、摘要、实体、主题、平台、来源、review 状态、evidence refs。
- 桌布查看方式：
  - `/signals?entity=category_tablecloth`
  - `/signals?entity=category_tablecloth&platform=weibo`

### `/opportunities`

- 目标：查看编译后的机会卡并支持按 review 状态过滤。
- 输入：`opportunity_cards` 表。
- 输出：
  - 机会卡摘要
  - 实体/主题
  - `trigger_signals`
  - `evidence_refs`
  - `dedupe_key`
  - `review_status`
  - `review_notes`
  - `reviewer`
  - `reviewed_at`
- 桌布查看方式：
  - `/opportunities?entity=category_tablecloth`
  - `/opportunities?entity=category_tablecloth&platform=weibo`

### `/risks`

- 目标：查看编译后的风险卡并支持按 review 状态过滤。
- 输入：`risk_cards` 表。
- 输出：
  - 风险卡摘要
  - 实体/主题
  - `trigger_signals`
  - `evidence_refs`
  - `dedupe_key`
  - `review_status`
  - `review_notes`
  - `reviewer`
  - `reviewed_at`
- 桌布查看方式：
  - `/risks?entity=category_tablecloth`
  - 若当前为空，保留真实结果，不强造 risk

### `/watchlists`

- 目标：查看当前 watchlist 配置与投影范围。
- 输入：`watchlists` 表。
- 输出：watchlist 类型、关键词、实体引用、主题标签。

## 页面之间跳转关系

- `/` -> `/signals`
- `/` -> `/opportunities`
- `/` -> `/risks`
- `/` -> `/watchlists`

## Signal / Card 详情展开方式

- 使用卡片内 `details/summary` 展开。
- 展开后至少显示：
  - `evidence_refs`
  - `trigger_signals`
  - `merged_signal_ids`
  - `merged_evidence_refs`
  - `review_notes`
  - `reviewer`
  - `reviewed_at`

## Review 交互

- 当前 HTML 页面只展示 review 字段，不提供表单提交。
- review 更新通过 API 完成：
  - `POST /opportunities/{id}/review`
  - `POST /risks/{id}/review`

## 列表筛选

- `GET /signals?entity=&topic=&platform=`
- `GET /opportunities?review_status=&reviewer=&entity=&topic=&platform=`
- `GET /risks?review_status=&reviewer=&entity=&topic=&platform=`

HTML 页面提供最小桌布快捷链接与 review status 快速筛选链接。

## API 与页面路由策略

- 同路径双视图：
  - 程序调用默认返回 JSON
  - 浏览器 `Accept: text/html` 时返回 HTML

保留固定 API 路径，不新增第二套路由命名。
