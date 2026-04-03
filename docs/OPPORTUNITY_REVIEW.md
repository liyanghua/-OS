# XHS 机会卡检视反馈闭环（V0.7）

## 概述

基于 XHS 三维结构化流水线生成的 `XHSOpportunityCard`，实现最小可用的"检视 + 人工反馈 + 聚合统计 + 升级判定"闭环。

## 数据流

```
Pipeline 输出 (opportunity_cards.json)
    ↓ sync_cards_from_json
XHSReviewStore (SQLite)
    ↓ 列表页 / 详情页
人工检视反馈 (OpportunityReview)
    ↓ review_aggregator
聚合指标回写 (review_count, composite_review_score, ...)
    ↓ opportunity_promoter
升级判定 (pending_review → reviewed → promoted)
```

## OpportunityReview 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `review_id` | `str` | 自动生成 16 位 hex |
| `opportunity_id` | `str` | 关联机会卡 ID |
| `reviewer` | `str` | 检视人 |
| `reviewed_at` | `datetime` | 检视时间 (UTC) |
| `manual_quality_score` | `int` | 质量评分 1-10 |
| `is_actionable` | `bool` | 是否可执行 |
| `evidence_sufficient` | `bool` | 证据是否充分 |
| `review_notes` | `str?` | 备注 |

## XHSOpportunityCard 聚合字段（V0.7 新增）

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `review_count` | `int` | `0` | 检视次数 |
| `manual_quality_score_avg` | `float?` | `None` | 平均质量评分 |
| `actionable_ratio` | `float?` | `None` | 可执行率 |
| `evidence_sufficient_ratio` | `float?` | `None` | 证据充分率 |
| `composite_review_score` | `float?` | `None` | 综合评分 |
| `qualified_opportunity` | `bool` | `False` | 是否已升级 |
| `opportunity_status` | `str` | `"pending_review"` | 状态 |

## 聚合公式

单卡综合评分：

```
normalized_quality = manual_quality_score_avg / 10
composite_review_score = 0.5 × normalized_quality + 0.3 × actionable_ratio + 0.2 × evidence_sufficient_ratio
```

## 升级判定（promoted 条件）

全部满足：

- `review_count >= 1`
- `manual_quality_score_avg >= 7.5`
- `actionable_ratio >= 0.6`
- `evidence_sufficient_ratio >= 0.7`
- `composite_review_score >= 0.72`

## 全局 needs_optimization 判定

任一满足即为 `true`：

- `average_manual_quality_score < 6.5`
- `average_actionable_ratio < 0.5`
- `average_evidence_sufficient_ratio < 0.6`
- `average_composite_review_score < 0.65`

## opportunity_status 状态机

```
pending_review  →  reviewed  →  promoted
                              →  rejected（暂未实现自动驳回）
```

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/xhs-opportunities` | 机会卡列表（支持 type/status/qualified 筛选） |
| `GET` | `/xhs-opportunities/{id}` | 机会卡详情页（HTML + JSON） |
| `POST` | `/xhs-opportunities/{id}/reviews` | 提交检视反馈 |
| `GET` | `/xhs-opportunities/{id}/reviews` | 查询某卡全部 review |
| `GET` | `/xhs-opportunities/review-summary` | 全局检视统计 |

## 存储

- SQLite 数据库：`data/xhs_review.sqlite`
- 两张表：`xhs_opportunity_cards`（机会卡 + 聚合字段）、`xhs_reviews`（检视记录）
- 启动时自动从 `opportunity_cards.json` 同步卡片，保留已有聚合数据

## 不做的事项

- 不改现有 `Repository` / 旧 pipeline 存储
- 不做多篇聚合
- 不做复杂鉴权
- 不做 Agent 编排 / Onyx
- 不做前端 SPA 改造
