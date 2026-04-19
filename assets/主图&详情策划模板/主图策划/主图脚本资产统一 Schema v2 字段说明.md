# 主图脚本资产统一 Schema v2 字段说明

## 设计目标

v2 相比上一版，重点做了三件事：

1. 把**业务语义**补齐：加入 `business_context`、`strategy_pack`，不再只是“图怎么做”，而是“为什么这样做”。
2. 把**单图规范**拆清：每张图同时拥有 `visual_spec`、`copy_spec`、`compile_spec`。
3. 把**下游可执行性**补齐：加入 `prompt_compile_spec`、`review_spec`、`lineage`，便于进入 AIGC、评审、资产治理链路。

## 一级字段

### `asset_id`
资产唯一 ID。

### `schema_version`
Schema 版本号。当前固定为 `main_image_script_v2`。

### `asset_type`
资产类型。当前固定为 `main_image_script_bundle`，表示一组主图脚本资产。

### `business_context`
业务上下文。定义产品类目、人群、渠道、目标，解决“这套主图是给谁、在哪用、要达成什么效果”。

### `strategy_pack`
策略包。定义定位、差异化、用户痛点、信息层级，是主图脚本的策略源头。

### `global_style`
全局风格。定义统一语调、风格标签、颜色系统、正负向视觉关键词。

### `script_asset`
脚本级元信息。描述整套主图叙事链、评估策略、发版门槛。

### `cards`
单图数组，是核心主体。每个 card 对应一张主图。

### `prompt_compile_spec`
编译规范。定义从策略与脚本字段，如何编译到 AIGC prompt / layout hints。

### `review_spec`
评审规范。定义角色、检查项和打分维度。

### `lineage`
血缘关系。记录来源资产、派生资产和下游资产。

## Card 内部结构

### `visual_spec`
回答“这一张图视觉上怎么做”。

关键子字段：
- `layout_type`：版式类型
- `shot_type`：镜头类型
- `scene`：场景
- `subjects`：主体对象及角色
- `composition`：焦点、产品占比、文字占比
- `background`：背景类型与复杂度
- `lighting`：光线风格
- `labels`：可视化标签

### `copy_spec`
回答“这一张图文案上怎么说”。

关键子字段：
- `headline`
- `subheadline`
- `promo_text`
- `selling_points`
- `text_position`

### `compile_spec`
回答“这一张图如何编译给生图或设计系统”。

关键子字段：
- `prompt_intent`
- `positive_prompt_blocks`
- `negative_prompt_blocks`
- `render_hints`

## 推荐下游对象映射

- `MainImageScriptAssetV2` → 主图脚本总资产
- `CardSpec` → 单图执行单元
- `PromptBundle` → 生图编译结果
- `DesignBrief` → 设计任务单
- `ReviewRecord` → 评审记录
- `PerformanceCard` → 上线效果回流卡

## 推荐实践

### 适合直接入库的场景
- 主图模板库
- 品类策略资产库
- AIGC 编译资产库
- 主图评审与复盘系统

### 建议补充的后续字段
后面可继续扩展：
- `platform_constraints`
- `compliance_rules`
- `ab_test_spec`
- `performance_metrics`
- `template_refs`
- `evidence_refs`
