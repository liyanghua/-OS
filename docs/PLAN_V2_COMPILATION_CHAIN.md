# V2 四层编译链实施计划

> **目标**：把小红书笔记从"内容样本"编译成"经营决策资产"。

## 现状 vs 目标

| 维度 | 现状 (V1) | 目标 (V2) |
|------|-----------|-----------|
| 信号抽取 | 标题 + desc 扁平文本 | 标题/正文/标签/评论/视觉 **多维字段级抽取** |
| 本体对象 | 3 类（competitor / category / platform_policy） | **10+ 类**（品类/场景/风格/需求/风险/材质/内容模式/视觉模式/人群/竞品） |
| 输出卡片 | OpportunityCard + RiskCard | + **InsightCard** + **VisualPatternAsset** + **DemandSpecAsset** |
| 角色化 | 无 | CEO / 营销总监 / 产品总监 / 视觉总监 **角色标记与过滤** |
| 证据链 | 笔记级 1:1 | **字段级**（title / body / comment_12 / image_1） |
| 评论分析 | 仅 comment_count 计数 | **评论级信号分类**（购买意向/负面/比较/需求补充/信任缺口） |

## 四层架构

```
Layer 1: 内容解析层 (Content Parser)
  笔记 → NoteContentFrame（文本槽位 + 视觉槽位 + 评论槽位 + 互动槽位）

Layer 2: 经营信号抽取层 (Business Signal Extractor)
  NoteContentFrame → BusinessSignalFrame（场景/风格/需求/风险/卖点/人群/内容钩子/视觉模式）

Layer 3: 本体映射层 (Ontology Projector V2)
  BusinessSignalFrame → 归一化本体 refs（scene_refs / style_refs / need_refs / risk_refs / ...）

Layer 4: 决策资产编译层 (Decision Asset Compiler)
  归一化 Signal → OpportunityCard / RiskCard / InsightCard / VisualPatternAsset / DemandSpecAsset
  + 角色化标记 target_roles
```

## 分阶段实施

### Phase 1: 基础扩展（数据模型 + 本体 + watchlist）

**范围**：不改 pipeline 流程，只扩展底层定义。

1. **schemas 新增**
   - `NoteContentFrame`（Layer 1 输出）
   - `BusinessSignalFrame`（Layer 2 输出）
   - `InsightCard` / `VisualPatternAsset` / `DemandSpecAsset`（Layer 4 输出）
   - `enums` 扩展：`CardKind` + `OpportunityType` / `RiskType` / `InsightType` / `TargetRole`
   - `Signal` 扩展：多维 refs 字段（scene_refs / style_refs / need_refs / risk_refs 等）

2. **ontology_mapping.yaml 扩展**
   - 新增 7 类本体：scenes / styles / needs / risks / materials / content_patterns / visual_patterns / audiences
   - 每类带 keywords + aliases + watchlist_ids

3. **watchlists.yaml 扩展**
   - 按场景/风格/需求/风险维度新增细分 watchlist

4. **scoring.yaml 扩展**
   - 新增 topic_impacts 条目

### Phase 2: 抽取与归一化升级

1. **新增 `apps/intel_hub/extractor/` 目录**
   - `content_parser.py`：笔记 → NoteContentFrame
   - `signal_extractor.py`：NoteContentFrame → BusinessSignalFrame
   - `comment_classifier.py`：评论级信号分类

2. **升级 normalizer**
   - 在 normalize_raw_signals 中调用 extractor 产出多维字段
   - Signal 模型填充 scene_refs / style_refs / need_refs 等

3. **升级 topic_tagger / entity_resolver**
   - 利用新本体做更精确的映射

### Phase 3: 新卡片编译器 + 角色化

1. **新增编译器**
   - `insight_compiler.py`
   - `visual_pattern_compiler.py`
   - `demand_spec_compiler.py`

2. **角色化输出**
   - 每张卡片带 `target_roles` 标记
   - API / Dashboard 按角色过滤

### Phase 4: 整合与验证

1. `run_pipeline` 串联新层
2. 阶段日志覆盖新层
3. 演示脚本验证端到端
4. Repository 支持新表

## 文件变更预览

```
apps/intel_hub/
  schemas/
    enums.py              ← 扩展
    signal.py             ← 扩展多维 refs
    cards.py              ← + InsightCard / VisualPatternAsset / DemandSpecAsset
    content_frame.py      ← 新增 NoteContentFrame + BusinessSignalFrame
  extractor/              ← 新增目录
    __init__.py
    content_parser.py     ← Layer 1
    signal_extractor.py   ← Layer 2
    comment_classifier.py ← 评论信号分类
  projector/
    topic_tagger.py       ← 升级
    entity_resolver.py    ← 升级
    canonicalizer.py      ← 升级
  compiler/
    insight_compiler.py         ← 新增
    visual_pattern_compiler.py  ← 新增
    demand_spec_compiler.py     ← 新增
    opportunity_compiler.py     ← 升级
    risk_compiler.py            ← 升级
  normalize/
    normalizer.py         ← 升级
  workflow/
    refresh_pipeline.py   ← 串联新层
  storage/
    repository.py         ← 新表
config/
  ontology_mapping.yaml   ← 大幅扩展
  watchlists.yaml         ← 扩展
  scoring.yaml            ← 扩展
```
