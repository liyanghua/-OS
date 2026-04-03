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
  ├─→ extract_visual_signals()    → VisualSignals
  ├─→ extract_selling_theme_signals() → SellingThemeSignals
  └─→ extract_scene_signals()     → SceneSignals
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
| `VisualSignals` | `schemas/xhs_signals.py` | 视觉维度信号（8 个子字段） |
| `SellingThemeSignals` | `schemas/xhs_signals.py` | 卖点维度信号（6 个子字段） |
| `SceneSignals` | `schemas/xhs_signals.py` | 场景维度信号（5 个子字段） |
| `XHSEvidenceRef` | `schemas/evidence.py` | 轻量证据引用 |
| `XHSOntologyMapping` | `schemas/ontology_mapping_model.py` | 本体映射结果 |
| `XHSOpportunityCard` | `schemas/opportunity.py` | 最终机会卡 |

## 三维提取器

### 视觉 (`extraction/visual_extractor.py`)
- 风格: 奶油风/ins风/北欧/法式/原木/复古/极简
- 构图: 俯拍/全景/局部特写/前后对比/氛围图/功能说明图
- 色彩: 暖白/木色/低饱和/高对比
- 质感: 柔和/有纹理/轻薄/厚重/高级感
- 风险: 滤镜重/尺寸感不清楚/质感夸大

### 卖点主题 (`extraction/selling_theme_extractor.py`)
- 卖点: 防水/防油/好打理/出片/显高级/平价/易铺平/尺寸适配
- 挑战: 卷边/廉价感/尺寸难选/实物翻车/难清洁
- 购买意向: 求链接/想买/已下单/求同款
- 信任缺口: 真的吗/会不会/实物一样吗

### 场景 (`extraction/scene_extractor.py`)
- 场景: 出租屋/餐桌/茶几/书桌/宿舍/宝宝家庭/宠物家庭/小户型
- 目标: 改造氛围/提升高级感/防脏防油/方便清洁/适合拍照/平价升级
- 约束: 预算敏感/尺寸多样/小空间显乱/清洁压力大

## 本体映射

通过 `config/ontology_mapping.yaml` 配置，支持 alias -> canonical ref 映射：
- `scene_rental_room`, `scene_dining_table`, `scene_tea_table`, `scene_study_desk`, `scene_small_space`
- `style_creamy`, `style_ins`, `style_nordic`, `style_french`, `style_wood`, `style_vintage`
- `need_waterproof`, `need_oilproof`, `need_easy_clean`, `need_photogenic`, `need_premium_feel`, `need_affordable`
- `risk_edge_curl`, `risk_cheap_texture`, `risk_size_mismatch`, `risk_hard_to_clean`, `risk_visual_misleading`
- `visual_top_view_table`, `visual_texture_closeup`, `visual_before_after`, `visual_soft_light`, `visual_dense_instruction`
- `content_recommendation`, `content_review`, `content_makeover`, `content_comparison`, `content_pitfall`

## 机会卡规则 (`config/opportunity_rules.yaml`)

三类机会卡独立触发：

| 类型 | 触发条件 | 输出 opportunity_type |
|------|----------|----------------------|
| 视觉差异化 | style_signals >= 1, expression/feature >= 1, misleading_risk <= 2 | `visual` |
| 卖点主题 | selling_points >= 1, validated 或 purchase_intent 存在 | `demand` / `product` / `content` |
| 场景专属 | scenes >= 1, goals >= 1, combos >= 1 | `scene` |

每张卡必须包含 `evidence_refs`、`summary`、`suggested_next_step`、`confidence`。

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

## 当前限制

1. 视觉提取基于关键词规则，未接入多模态模型实时分析
2. 不支持 RiskCard / DemandSpec / VisualPatternAsset 生成
3. 聚合仅限单篇 → 多篇需下游合并
4. 置信度为规则评分，非模型预测

## 后续扩展方向

1. 接入 Qwen-VL 对图片做实时视觉分析，补充 VisualSignals
2. 支持 RiskCard（复用 risk_refs）和 VisualPatternAsset
3. 多篇笔记聚合生成更高层决策资产
4. 接入 LLM 做语义级卖点提取（超越关键词匹配）
