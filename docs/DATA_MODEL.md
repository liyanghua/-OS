# 本体大脑情报中枢 V0.2 数据模型

## 核心对象

### Signal

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `str` | signal id |
| `title` | `str` | 标题 |
| `summary` | `str` | 摘要 |
| `source_refs` | `list[str]` | 来源 URL 列表 |
| `entity_refs` | `list[str]` | canonical entity 输出，兼容旧接口 |
| `raw_entity_hits` | `list[str]` | 原始 alias 命中 |
| `canonical_entity_refs` | `list[str]` | 归一化后的 canonical entity ids |
| `topic_tags` | `list[str]` | 主题标签 |
| `platform_refs` | `list[str]` | 平台标签 |
| `timestamps` | `dict[str, str]` | 至少包含 `published_at`、`captured_at` |
| `confidence` | `float` | 0~1 |
| `evidence_refs` | `list[str]` | 关联 evidence ids |
| `review_status` | `ReviewStatus` | 当前默认 `pending` |
| `author` | `str?` | 作者 |
| `account` | `str?` | 账号 |
| `watchlist_hits` | `list[str]` | watchlist 命中上下文 |
| `raw_source_type` | `str?` | `json` / `jsonl` / `db_news_items` / `db_rss_items` / `db_generic` / `mediacrawler_jsonl` / `mediacrawler_json` / `mediacrawler_sqlite` / `xhs_capture_event` / `xhs_aggregated` |
| `metrics` | `dict[str, Any]` | 热度指标 |
| `business_priority_score` | `float` | 优先级 |

桌布 demo 示例（TrendRadar 源）：

- `entity_refs: ["category_tablecloth"]`
- `platform_refs: ["weibo"]`
- `topic_tags` 可能包含：`category`、`opportunity`、`风格偏好`、`材质偏好`、`清洁痛点`、`场景改造`、`内容钩子`、`拍照出片`、`价格敏感`、`尺寸适配`

桌布 demo 示例（MediaCrawler XHS 源）：

- `entity_refs: ["category_tablecloth"]`
- `platform_refs: ["xiaohongshu"]`
- `raw_source_type: "mediacrawler_jsonl"`
- `topic_tags` 还会包含 XHS 专属标签：`用户真实体验`、`购买意向`、`负面反馈`、`推荐种草`

### EvidenceRef

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `str` | evidence id |
| `title` | `str` | 标题 |
| `summary` | `str` | 摘要 |
| `source_name` | `str?` | 来源名 |
| `source_url` | `str?` | 来源 URL |
| `source_refs` | `list[str]` | 来源引用 |
| `entity_refs` | `list[str]` | 关联实体 |
| `topic_tags` | `list[str]` | 关联主题 |
| `timestamps` | `dict[str, str]` | `published_at`、`captured_at` |
| `confidence` | `float` | 证据置信度 |
| `evidence_refs` | `list[str]` | 自引用，便于统一接口 |
| `review_status` | `ReviewStatus` | 当前默认 `pending` |
| `author` | `str?` | 作者 |
| `account` | `str?` | 账号 |
| `watchlist_hits` | `list[str]` | watchlist 命中上下文 |
| `raw_source_type` | `str?` | 原始来源类型 |
| `raw_text` | `str` | 原始正文/摘要 |

### OpportunityCard / RiskCard

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `str` | card id |
| `card_type` | `CardKind` | `opportunity` / `risk` |
| `title` | `str` | 卡片标题 |
| `summary` | `str` | 卡片摘要 |
| `source_refs` | `list[str]` | 聚合来源 |
| `entity_refs` | `list[str]` | 聚合实体 |
| `topic_tags` | `list[str]` | 聚合主题 |
| `platform_refs` | `list[str]` | 聚合平台 |
| `timestamps` | `dict[str, str]` | 至少包含 `compiled_at`、`latest_signal_at` |
| `confidence` | `float` | 聚合置信度 |
| `evidence_refs` | `list[str]` | evidence ids |
| `review_status` | `ReviewStatus` | `pending` / `accepted` / `rejected` / `needs_followup` |
| `review_notes` | `str` | review 备注 |
| `reviewer` | `str?` | reviewer |
| `reviewed_at` | `str?` | review 时间 |
| `review_decision_source` | `ReviewDecisionSource?` | `manual` / `system` |
| `feedback_tags` | `list[str]` | 轻量反馈标签 |
| `trigger_signals` | `list[str]` | 兼容字段，等于聚合后的 signal ids |
| `dedupe_key` | `str` | 显式 dedupe key |
| `merged_signal_ids` | `list[str]` | 合并后的 signal ids |
| `merged_evidence_refs` | `list[str]` | 合并后的 evidence refs |
| `suggested_actions` | `list[str]` | 建议动作 |
| `impact_hint` | `str` | 业务影响提示 |
| `business_priority_score` | `float` | 聚合优先级 |

### Watchlist

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `str` | watchlist id |
| `watchlist_type` | `WatchlistType` | `competitor` / `category` / `platform_policy` |
| `title` | `str` | 标题 |
| `summary` | `str` | 范围说明 |
| `entity_refs` | `list[str]` | canonical entity ids |
| `keywords` | `list[str]` | 主匹配词 |
| `aliases` | `list[str]` | 别名 |
| `priority` | `float` | 优先级 |

桌布 demo watchlist 示例：

- `id: category_tablecloth`
- `watchlist_type: category`
- `entity_refs: ["category_tablecloth"]`
- `keywords`: 桌布 / 餐桌布 / 桌垫 / 茶几桌布 / 防水桌布 / PVC桌布 / 棉麻桌布

## 状态字段

### `review_status`

```text
pending
accepted
rejected
needs_followup
```

兼容旧值：

- `pending_review` -> `pending`
- `dismissed` -> `rejected`
- `human_reviewed` -> `accepted`

### `review_decision_source`

```text
manual
system
```

当前首版 API 回写固定使用 `manual`。

## 对象关系

- `Signal 1 -> N EvidenceRef`
  - 当前首版每条 signal 生成 1 条 evidence ref。
- `OpportunityCard N -> N Signal`
  - 通过 `trigger_signals` / `merged_signal_ids` 关联。
- `RiskCard N -> N Signal`
  - 通过 `trigger_signals` / `merged_signal_ids` 关联。
- `Signal N -> N Watchlist`
  - 通过 canonical entity projection 命中后写回 `canonical_entity_refs`。

## evidence_refs 如何挂载

- `Signal.evidence_refs`：记录该 signal 的 evidence ids。
- `OpportunityCard.evidence_refs` / `RiskCard.evidence_refs`：聚合信号后保留的 evidence ids。
- `merged_evidence_refs`：dedupe 解释字段，当前与 `evidence_refs` 同义但单独暴露，便于后续演进。

## Canonical entity 的含义

- `raw_entity_hits`：文本中真实命中的 alias。
- `canonical_entity_refs`：将 alias 归一后的 canonical entity ids。
- `entity_refs`：对外兼容字段，当前保持与 `canonical_entity_refs` 一致。

## dedupe 的含义

- `dedupe_key`：同实体/主题/时间窗/标题 token 签名的稳定键。
- `merged_signal_ids`：被合并进该 card 的 signals。
- `merged_evidence_refs`：合并后的 evidence refs。

## 配置对象与模型关系

- `config/watchlists.yaml`
  - 定义 watchlist 对象本身。
- `config/ontology_mapping.yaml`
  - 定义 topics、platform refs、canonical entities。
- `config/scoring.yaml`
  - 定义优先级权重。
- `config/dedupe.yaml`
  - 定义 merge window、evidence 下限、title overlap 阈值、每窗最大卡片数。
- `config/runtime.yaml`
  - 定义 output 路径、SQLite 路径与 fallback。

## MediaCrawler 原生笔记字段映射

MediaCrawler XHS 笔记数据通过 `mediacrawler_loader.py` 映射为 raw signal dict：

| MediaCrawler 字段 | raw signal 字段 |
|---|---|
| `note_id` | `raw_payload.note_id`（也用于 `source_url` 拼接） |
| `title` | `title` |
| `desc` | `raw_text` |
| `note_url` | `source_url` |
| `source_keyword` | `keyword` |
| `nickname` | `author` |
| `time` | `published_at`（unix ts -> ISO 8601） |
| `last_modify_ts` | `captured_at`（13位毫秒 -> ISO 8601） |
| `liked_count` / `collected_count` / `comment_count` / `share_count` | `metrics.*` |
| `tag_list` | `tags`（逗号分隔 -> list） |

固定值：`platform: "xiaohongshu"`、`source_name: "小红书"`。

## XHS 三维结构化流水线 Schema（V0.5）

详见 [XHS_OPPORTUNITY_PIPELINE.md](./XHS_OPPORTUNITY_PIPELINE.md)。

### XHSEvidenceRef（轻量证据引用）

| 字段 | 类型 | 说明 |
|---|---|---|
| `evidence_id` | `str` | 自动生成 12 位 hex |
| `source_kind` | `Literal["title","body","tag","image","comment"]` | 来源字段 |
| `source_ref` | `str` | 笔记 ID 或 comment 索引 |
| `snippet` | `str` | 匹配上下文片段 |
| `confidence` | `float` | 0~1 |

### XHSNoteRaw

| 字段 | 类型 | 说明 |
|---|---|---|
| `note_id` | `str` | 笔记 ID |
| `title_text` | `str` | 标题 |
| `body_text` | `str` | 正文 |
| `tag_list` | `list[str]` | 标签列表 |
| `like_count` / `collect_count` / `comment_count` / `share_count` | `int` | 互动数据 |
| `image_list` | `list[XHSImageFrame]` | 图片列表 |
| `comments` | `list[XHSComment]` | 评论列表 |
| `top_comments` | `list[XHSComment]` | 高赞评论 |

### XHSParsedNote

| 字段 | 类型 | 说明 |
|---|---|---|
| `raw_note` | `XHSNoteRaw` | 原始笔记引用 |
| `normalized_title` | `str` | 归一化标题 |
| `normalized_body` | `str` | 归一化正文 |
| `normalized_tags` | `list[str]` | 归一化标签 |
| `engagement_summary` | `dict` | 互动摘要 |

### VisualSignals / SellingThemeSignals / SceneSignals

三类信号均含 `note_id` + `evidence_refs: list[XHSEvidenceRef]`，各有独立子字段。

### XHSOntologyMapping (V0.6)

| 字段 | 类型 | 说明 |
|---|---|---|
| `note_id` | `str` | 笔记 ID |
| `category_refs` | `list[str]` | 品类 canonical refs |
| `scene_refs` | `list[str]` | 场景 canonical refs |
| `style_refs` | `list[str]` | 风格 canonical refs |
| `need_refs` | `list[str]` | 需求 canonical refs |
| `risk_refs` | `list[str]` | 风险 canonical refs（含 cross_modal 增补） |
| `audience_refs` | `list[str]` | 受众 canonical refs |
| `visual_pattern_refs` | `list[str]` | 视觉模式 canonical refs |
| `content_pattern_refs` | `list[str]` | 内容模式 canonical refs |
| `value_proposition_refs` | `list[str]` | 价值主张 refs（need+style 组合） |
| `source_signal_summary` | `str \| None` | **V0.6 新增** 一句话信号摘要 |
| `evidence_refs` | `list[XHSEvidenceRef]` | 汇总证据 |

### XHSOpportunityCard (V0.6)

| 字段 | 类型 | 说明 |
|---|---|---|
| `opportunity_id` | `str` | 自动生成 |
| `title` | `str` | 机会卡标题 |
| `summary` | `str` | 摘要 |
| `opportunity_type` | `Literal["visual","demand","product","content","scene"]` | 类型 |
| `entity_refs` | `list[str]` | 品类 refs |
| `scene_refs` | `list[str]` | 场景 refs |
| `style_refs` | `list[str]` | 风格 refs |
| `need_refs` | `list[str]` | 需求 refs |
| `risk_refs` | `list[str]` | 风险 refs |
| `visual_pattern_refs` | `list[str]` | 视觉模式 refs |
| `content_pattern_refs` | `list[str]` | **V0.6 新增** 内容模式 refs |
| `value_proposition_refs` | `list[str]` | **V0.6 新增** 价值主张 refs |
| `audience_refs` | `list[str]` | **V0.6 新增** 受众 refs |
| `evidence_refs` | `list[XHSEvidenceRef]` | 证据链 |
| `confidence` | `float` | 置信度 |
| `suggested_next_step` | `list[str]` | **V0.6 改为 list** 多条建议下一步 |
| `review_status` | `str` | 默认 `pending` |
| `source_note_ids` | `list[str]` | 来源笔记 |

### OpportunityReview (V0.7)

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

### XHSOpportunityCard 聚合字段 (V0.7 新增)

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `review_count` | `int` | `0` | 检视次数 |
| `manual_quality_score_avg` | `float?` | `None` | 平均质量评分 |
| `actionable_ratio` | `float?` | `None` | 可执行率 |
| `evidence_sufficient_ratio` | `float?` | `None` | 证据充分率 |
| `composite_review_score` | `float?` | `None` | 综合评分 |
| `qualified_opportunity` | `bool` | `False` | 是否已升级 |
| `opportunity_status` | `str` | `"pending_review"` | 状态 (pending_review / reviewed / promoted / rejected) |

详见 [OPPORTUNITY_REVIEW.md](./OPPORTUNITY_REVIEW.md)。

## 当前局限

- canonicalization 仍是规则匹配，不处理跨语言同义词扩展。
- dedupe 依赖标题 token overlap，对非常短或非常长标题仍有限制。
- 桌布 topic tags 目前是轻量规则，不是可学习分类器。
