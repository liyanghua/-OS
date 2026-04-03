# XHS 三维结构化机会卡流水线

## 概述

本流水线从小红书原始笔记出发，围绕 **视觉**、**卖点主题**、**场景** 三个核心维度进行结构化提取，经由本体映射与规则判定生成 `XHSOpportunityCard`（机会卡）。

## 数据流

```
MediaCrawler JSONL
  ↓ parse_raw_note()
XHSNoteRaw
  ↓ parse_note()
XHSParsedNote
  ├─→ extract_visual_signals()         → VisualSignals V2
  ├─→ extract_selling_theme_signals()  → SellingThemeSignals V2
  └─→ extract_scene_signals()          → SceneSignals V2
        ↓ validate_cross_modal_consistency()
    CrossModalValidation
        ↓ project_xhs_signals()
    XHSOntologyMapping
        ↓ compile_xhs_opportunities()
    list[XHSOpportunityCard]
```

## Schema 层

| Schema | 文件 | 说明 |
|--------|------|------|
| `XHSNoteRaw` | `schemas/xhs_raw.py` | 直接映射 MediaCrawler JSONL 字段 |
| `XHSComment` | `schemas/xhs_raw.py` | 评论结构 |
| `XHSImageFrame` | `schemas/xhs_raw.py` | 图片结构 |
| `XHSParsedNote` | `schemas/xhs_parsed.py` | 归一化后的笔记 |
| `VisualSignals` | `schemas/xhs_signals.py` | 视觉维度信号 V2（含 primary_style / 评分 / 差异化） |
| `SellingThemeSignals` | `schemas/xhs_signals.py` | 卖点维度信号 V2（含优先级 / 卖点分类） |
| `SceneSignals` | `schemas/xhs_signals.py` | 场景维度信号 V2（含隐式推断 / 机会提示） |
| `CrossModalValidation` | `schemas/xhs_validation.py` | 跨模态一致性校验结果 |
| `XHSEvidenceRef` | `schemas/evidence.py` | 轻量证据引用 |
| `XHSOntologyMapping` | `schemas/ontology_mapping_model.py` | 本体映射结果 |
| `XHSOpportunityCard` | `schemas/opportunity.py` | 最终机会卡 |

## 四维提取器 (V2)

每个 extractor 采用分层架构：规则层 → LLM/VLM 层（可选）→ 合并层。

### 视觉 (`extraction/visual_extractor.py`) — 三层架构
- **规则层** `extract_visual_signals_from_metadata()`: 纯关键词匹配，零依赖必定运行
- **VLM 层** `extract_visual_signals_with_vlm()`: 通过 `llm_client.call_vlm()` 调用 DashScope Qwen-VL，无 API key 时跳过
- **合并层** `merge_visual_signals()`: VLM 补充但不覆盖规则层
- 风格: 奶油风/ins风/北欧/法式/原木/复古/极简（含 primary_style + style_confidence）
- 构图: 俯拍/全景/局部特写/前后对比/氛围图/功能说明图
- 场景: 餐桌/书桌/茶几/出租屋/宿舍/拍照布景（V2 修复: 独立关键词，不复用构图）
- 色彩: 暖白/木色/低饱和/高对比
- 质感: 柔和/有纹理/轻薄/厚重/高级感
- 卖点可视化: 防水展示/贴合展示/出片感展示/高级感展示/材质纹理展示/尺寸适配展示
- 风险: 滤镜重/尺寸感不清楚/材质厚薄感不明确/质感夸大/场景过于样板间化
- V2 新增评分: `click_differentiation_score` / `conversion_alignment_score` / `visual_risk_score` / `information_density`

### 卖点主题 (`extraction/selling_theme_extractor.py`) — 三层架构
- **文本承诺层** `extract_claimed_selling_points()`: 从标题/正文/标签抽显性卖点，按位置优先级排序
- **评论验证层** `extract_comment_validation_signals()`: 从评论抽验证/质疑/购买意图/信任差距
- **卖点分类层** `classify_selling_theme()`: 区分点击型/转化型/可产品化/纯内容型卖点
- 卖点: 防水/防油/好打理/出片/显高级/平价/易铺平/尺寸适配/颜值高/厚实/材质有质感
- 挑战: 卷边/廉价感/尺寸难选/实物翻车/难清洁/防水存疑
- 分类: click_oriented / conversion_oriented / productizable / content_only
- 主题归纳: 清洁便利主题/氛围升级主题/平价高级感主题/场景改造主题/材质质感主题
- V2 新增: `primary_selling_points` / `secondary_selling_points` / `selling_point_priority`

### 场景 (`extraction/scene_extractor.py`) — 四层架构
- **显式场景层** `extract_explicit_scene_signals()`: 直接关键词匹配
- **隐式推断层** `infer_scene_signals()`: 规则推断（如"大学生"→宿舍），可选接入视觉摘要
- **目标/约束层** `extract_scene_goals_and_constraints()`: 场景目标、约束、受众
- **组合生成层** `build_scene_style_value_combos()`: 场景×风格×卖点组合 + 机会提示
- 场景: 出租屋/餐桌/茶几/书桌/宿舍/宝宝家庭/宠物家庭/小户型/拍照布景
- 目标: 改造氛围/提升高级感/防脏防油/方便清洁/适合拍照/平价升级
- 约束: 预算敏感/尺寸多样/小空间显乱/清洁压力大/有孩子宠物/需要不易卷边
- V2 新增: `inferred_scene_signals` / `inference_confidence` / `scene_opportunity_hints`

### 跨模态校验 (`extraction/cross_modal_validator.py`) — V2 新增
- **视觉支持校验** `validate_visual_support()`: 检查文本卖点是否被图片信号支持
- **评论验证校验** `validate_comment_support()`: 检查卖点是否被评论验证/质疑
- **场景一致性校验** `validate_scene_alignment()`: 检查场景在标题/图片/评论间是否一致
- 输出: `high_confidence_claims` / `unsupported_claims` / `challenged_claims` / `overall_consistency_score`

### LLM 客户端 (`extraction/llm_client.py`) — V2 新增
- `call_text_llm()`: DashScope 文本 LLM 封装
- `call_vlm()`: DashScope VLM 封装（复用 Qwen-VL 调用模式）
- `is_llm_available()` / `is_vlm_available()`: 可用性检查
- 无 `DASHSCOPE_API_KEY` 时静默返回空结果，不阻塞 pipeline

## 本体映射 (V0.6 升级)

通过 `config/ontology_mapping.yaml` 配置，支持 alias -> canonical ref 映射。

`ontology_projector.py` 中 `project_xhs_signals()` 拆分为 8 个独立子函数 + 1 个入口：

| 子函数 | 输入 | 映射目标 |
|--------|------|----------|
| `map_styles(visual, scene, config)` | 视觉风格 + 场景风格信号 | `style_*` refs |
| `map_scenes(scene, visual, config)` | 显式+隐式场景信号 | `scene_*` refs |
| `map_needs(selling, scene, config)` | 卖点+场景目标信号 | `need_*` refs |
| `map_risks(selling, visual, cross_modal, config)` | 挑战+风险 + 跨模态无支撑 | `risk_*` refs |
| `map_visual_patterns(visual, config)` | 构图+表达+特征 | `visual_*` refs |
| `map_content_patterns(selling, scene, config)` | 卖点主题归纳 | `content_*` refs |
| `map_value_propositions(selling, visual, scene, config)` | need+style 组合 | `vp_*` + combo refs |
| `map_audiences(scene, config)` | 受众信号 | `audience_*` refs |
| `build_source_signal_summary(visual, selling, scene)` | 全维度信号 | 一句话摘要 |

`cross_modal` 参数贯穿 `map_risks()`，当 `unsupported_claims` 非空时自动映射到 `risk_claim_unverified`。

已有 canonical refs：
- 场景: `scene_rental_room`, `scene_dining_table`, `scene_tea_table`, `scene_study_desk`, `scene_small_space`
- 风格: `style_creamy`, `style_ins`, `style_nordic`, `style_french`, `style_wood`, `style_vintage`
- 需求: `need_waterproof`, `need_oilproof`, `need_easy_clean`, `need_photogenic`, `need_premium_feel`, `need_affordable`, `need_size_fit`
- 风险: `risk_edge_curl`, `risk_cheap_texture`, `risk_size_mismatch`, `risk_hard_to_clean`, `risk_visual_misleading`, `risk_claim_unverified`
- 视觉: `visual_top_view_table`, `visual_texture_closeup`, `visual_before_after`, `visual_soft_light_creamy`, `visual_dense_instruction`
- 内容: `content_recommendation`, `content_review`, `content_makeover`, `content_comparison`, `content_pitfall`

## 机会卡规则 (`config/opportunity_rules.yaml`)

三类机会卡独立触发，V0.6 新增 cross_modal 评分调节：

| 类型 | 触发条件 | cross_modal 影响 | 输出 opportunity_type |
|------|----------|-----------------|----------------------|
| 视觉差异化 | style >= 1, expression/feature >= 1, misleading_risk <= 2, visual_risk_score <= 0.5 | click_diff_bonus +0.1 (当 score > 0.2) | `visual` |
| 卖点主题 | selling_points >= 1, validated 或 purchase_intent 存在, unsupported_ratio <= 0.7 | 无 unsupported/challenged 时 +0.05 | `demand` / `product` / `content` |
| 场景专属 | scenes >= 1, goals >= 1, combos >= 1, scene_alignment_score >= 0.3 | alignment 通过时 +0.1 | `scene` |

V0.6 新增 `merge_opportunities()` — 按 `opportunity_type + scene_refs + need_refs` 去重，合并 `evidence_refs`。

每张卡必须包含 `evidence_refs`、`summary`、`suggested_next_step`（list[str]）、`confidence`。

## 运行方式

```bash
# 批量处理
python -m apps.intel_hub.workflow.xhs_opportunity_pipeline

# 指定笔记
python -m apps.intel_hub.workflow.xhs_opportunity_pipeline --note-id <id>

# 自定义目录
python -m apps.intel_hub.workflow.xhs_opportunity_pipeline --jsonl-dir path/to/dir --output-dir path/to/out
```

输出保存至 `data/output/xhs_opportunities/`：
- `opportunity_cards.json` — 所有机会卡
- `pipeline_details.json` — 完整中间结果
- `pipeline_report.md` — Markdown 报告

## 与现有 Pipeline 关系

- 与 `refresh_pipeline.py` 并行运行，不修改现有流程
- 新 `extraction/` 与 `extractor/` 独立
- 新 `parsing/` 与 `content_parser.py` 独立
- 共享 `config/ontology_mapping.yaml`

## 数据流（V0.6 完整版）

```
MediaCrawler JSONL
  ↓ parse_raw_note()
XHSNoteRaw
  ↓ parse_note()
XHSParsedNote
  ├─→ extract_visual_signals()         → VisualSignals V2
  ├─→ extract_selling_theme_signals()  → SellingThemeSignals V2
  └─→ extract_scene_signals()          → SceneSignals V2
        ↓ validate_cross_modal_consistency()
    CrossModalValidation
        ↓ project_xhs_signals(cross_modal=validation)     ← V0.6: 传入 cross_modal
    XHSOntologyMapping (含 source_signal_summary)
        ↓ compile_xhs_opportunities(cross_modal=validation) ← V0.6: 传入 cross_modal
        ↓ merge_opportunities()                              ← V0.6: 新增去重
    list[XHSOpportunityCard]
```

## 当前限制

1. VLM 层需要 `DASHSCOPE_API_KEY`，无 key 时仅走规则层
2. 卖点分类（click/conversion/productizable）基于规则词表，LLM 辅助分类为占位接口
3. 不支持 RiskCard / DemandSpec / VisualPatternAsset 生成
4. 聚合仅限单篇 → 多篇需下游合并（merge_opportunities 仅单篇内去重）
5. 跨模态校验基于规则匹配，非语义级比对
6. value_proposition_refs 基于 need+style 组合规则，非语义推理

## 后续扩展方向

1. 启用 VLM 层（配置 DASHSCOPE_API_KEY）对图片做实时视觉分析
2. LLM 辅助卖点分类和语义级卖点提取
3. 支持 RiskCard（复用 risk_refs）和 VisualPatternAsset
4. 多篇笔记聚合生成更高层决策资产
5. 跨模态校验引入语义相似度模型
6. VP 映射引入 embedding 相似度而非规则组合
