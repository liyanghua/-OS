# 《PRD + 技术升级（Part 2）：品牌资产融入（商品经营数据 / 商品库 / 素材库 / 品牌规则）》

> 本部分只聚焦第二个升级方向：
> **把品牌自己的数据资产接入编译链，让系统产出的内容方案更贴近品牌自己的品类、商品、素材与经营结果。**
> 不包含长视频策划生成，避免链路和对象模型混杂。

---

## 1. 升级背景与问题定义

### 1.1 当前问题

如果系统只依赖外部热点、公开内容、通用模型与行业泛知识，它可以做到“行业通用的创意建议”，但很难做到：

* 对这个品牌自己的品类特点更贴合
* 对这个品牌自己卖得好的 SKU 更敏感
* 对这个品牌自己已经验证过的主图 / 前3秒 / 长视频模式更复用
* 对这个品牌自己的素材资产更充分调用
* 对这个品牌自己的风险边界、表达规范和平台打法更一致

也就是说，缺少品牌资产融入时，系统很难比市面上的通用 AI 创意工具更强。

### 1.2 为什么品牌资产融入是第二个核心升级点

对于天空树/众唯这类客户，真正能形成壁垒的是：

1. **经营数据**：哪些 SKU 真卖得好，哪些版本 CTR 高但退款高，哪些卖点长期有效
2. **商品库**：不同商品、不同 SKU、不同改款方向的结构化信息
3. **素材库**：哪些主图、片段、模特、细节镜头已经验证过有效
4. **品牌规则与经验**：品牌调性、禁用表达、平台适配规则、历史 SOP 和打法总结

把这些接进来后，你的系统就能从：

* “看到热点后给一个泛化创意方案”

升级成：

* “看到热点后，基于品牌已有高表现商品、高表现素材、高表现卖点和品牌规则，编译出更贴近品牌自己的内容方案”

### 1.3 升级目标

建立一个独立能力层：

**Brand Data Hub + Brand-Aware Compiler**

一句话定义：
**让系统在每个编译阶段都能读取品牌自己的经营数据、商品库、素材库和规则库，生成更贴合品牌自己的策划与裂变方案。**

---

## 2. 产品定位与设计原则

## 2.1 产品定位

这不是一个传统 BI 报表模块，也不是一个单独的 DAM（Digital Asset Management）系统。

它的准确定位是：

**品牌上下文与资产编译层**

作用是：

* 给机会编译器提供品牌语境
* 给卖点编译器提供品牌历史表现
* 给主图/前3秒/长视频生成器提供品牌素材与模式参考
* 给测试板和回流系统提供品牌级对照与模式沉淀

## 2.2 设计原则

### 原则 A：数据不是只用来看，而是要参与编译

品牌数据资产不是放在单独页面供人查看，而是要被系统在：

* 机会判断
* 卖点编译
* 版本生成
* 测试放大
* 资产沉淀

这五个阶段调用。

### 原则 B：先接“对内容决策最有用”的数据，不先追求全量打通

优先接：

* SKU 经营结果
* 版本表现结果
* 素材元数据
* 品牌规则

不先做全量 ERP / 财务 / 供应链大一统。

### 原则 C：结构化优先于报表化

先把数据变成对象：

* 商品对象
* SKU 对象
* 表现对象
* 素材对象
* 规则对象
* 模式对象

而不是一开始先做很多报表。

### 原则 D：前台极简，后台深度引用

前台给用户看到的是：

* 当前方案用了哪些品牌资产
* 当前推荐依据是什么
* 当前引用了哪些高表现商品 / 素材 / 模式

不把复杂的底层数据关系都暴露给业务用户。

---

## 3. 品牌资产范围定义

建议把品牌资产拆成 4 层。

## 3.1 第 1 层：经营数据层

包括：

* 商品 / SKU 基础信息
* SKU 级销售表现
* 平台 / 店铺 / 链接级表现
* 主图版本 / 视频版本级表现
* CTR / CVR / 收藏加购 / 退款率 / 评论信号

## 3.2 第 2 层：商品库层

包括：

* 商品主档
* SKU 编码
* 商品属性
* 发色 / 发型 / 材质 / 功能 / 价格带 / 场景标签
* 老品 / 新品 / 改款关系

## 3.3 第 3 层：素材资产层

包括：

* 主图素材
* 视频片段
* 爆款视频
* 模特图
* 细节图
* 历史详情页素材

## 3.4 第 4 层：品牌知识与规则层

包括：

* 品牌调性
* 禁用词 / 风险词
* 必提点
* 平台表达规则
* SOP / 经验总结
* 已验证有效模式 / 失败模式

---

## 4. 产品形态：Brand Data Hub + Brand Context Inspector

## 4.1 页面一：Brand Data Hub

### 页面定位

统一管理品牌自己的经营数据、商品库、素材库、规则与模式资产。

### 页面目标

让品牌资产变成：

* 可检索
* 可追溯
* 可被编译器调用
* 可沉淀为高表现模式

### 页面布局

#### 左栏：资产类型切换

* 商品 / SKU
* 经营表现
* 主图素材
* 视频素材
* 品牌规则
* 高表现模式
* 失败模式

#### 顶部筛选条

* 平台
* 店铺
* 商品
* SKU
* 时间范围
* 场景
* 卖点
* 表现标签（高 CTR / 高 CVR / 低退款 等）

#### 中栏：列表 / 搜索结果

以表格或卡片形式展示资产。

#### 右栏：详情与引用方式

包括：

* 资产详情
* 关联表现
* 关联商品 / SKU
* 关联卖点
* 关联素材
* 被哪些版本调用
* 可复用建议

### 页面核心动作

* 导入经营数据
* 导入商品库
* 导入素材资产
* 添加品牌规则
* 标记赢家模式 / 失败模式
* 查看哪些编译器引用了该资产

---

## 4.2 页面二：Brand Context Inspector

### 页面定位

在所有关键编译页面中，以右侧 inspector 的形式显示：
**当前 AI 用了哪些品牌自己的数据与资产。**

### 作用

提高：

* 可解释性
* 可控性
* 业务信任感

### 展示内容

#### 在 Opportunity Radar 中

* 当前机会参考了哪些历史高表现商品
* 哪些类似机会在该品牌历史上做过
* 是否已有相关素材储备

#### 在 Selling Point Compiler 中

* 当前卖点参考了哪些高表现商品/SKU
* 哪些历史卖点在这个品牌上长期有效
* 哪些负面反馈提示该卖点需要规避

#### 在 Main Image Lab / First3s Lab / Video Flow Studio 中

* 当前版本引用了哪些高表现素材
* 当前模式参考了哪些赢家模板
* 当前受哪些品牌规则约束

### 页面交互

* 可展开看引用证据
* 可切换“引用更多品牌资产 / 少引用品牌资产”
* 可禁用某类资产参与编译

---

## 5. 用户角色与核心任务

## 5.1 用户角色

1. 运营负责人
2. 内容负责人
3. 视觉负责人
4. 商品/产品负责人
5. 数据/IT 对接人
6. 老板/总监

## 5.2 核心任务

* 把品牌经营数据导入系统
* 把品牌商品库和素材库接进系统
* 给品牌建立自己的规则与模式库
* 在内容策划时调用品牌资产
* 用品牌历史结果指导热点判断、卖点编译和裂变生成

---

## 6. 对象模型设计

## 6.1 经营数据对象

### 1）ProductRecord

```yaml
object_type: ProductRecord
fields:
  - product_id
  - brand_id
  - product_name
  - category
  - product_line
  - launch_date
  - lifecycle_stage
  - tags
```

### 2）SKURecord

```yaml
object_type: SKURecord
fields:
  - sku_id
  - product_id
  - sku_name
  - price_band
  - color
  - style
  - function_tags
  - scenario_tags
  - availability_status
```

### 3）ProductPerformanceRecord

```yaml
object_type: ProductPerformanceRecord
fields:
  - record_id
  - platform
  - store_id
  - link_id
  - product_id
  - sku_id
  - date_window
  - impressions
  - clicks
  - ctr
  - orders
  - cvr
  - refund_rate
  - save_rate
  - add_to_cart_rate
  - comments_summary
```

### 4）CreativePerformanceRecord

```yaml
object_type: CreativePerformanceRecord
fields:
  - record_id
  - creative_id
  - creative_type    # 主图 / 前3秒 / 长视频
  - platform
  - store_id
  - product_id
  - sku_id
  - date_window
  - impressions
  - clicks
  - ctr
  - cvr
  - refund_rate
  - retention_3s
  - retention_8s
  - retention_15s
  - fatigue_score
```

---

## 6.2 商品库对象

### 5）ProductFeatureProfile

```yaml
object_type: ProductFeatureProfile
fields:
  - profile_id
  - product_id
  - feature_points
  - target_people
  - target_scenarios
  - differentiation_notes
  - risk_notes
```

### 6）ProductLineage

```yaml
object_type: ProductLineage
fields:
  - lineage_id
  - source_product_id
  - derived_product_id
  - lineage_type   # 改款 / 裂变 / 同系列 / 衍生款
  - reason
```

---

## 6.3 素材资产对象

### 7）BrandAsset

```yaml
object_type: BrandAsset
fields:
  - asset_id
  - brand_id
  - asset_type     # 主图 / 视频片段 / 模特图 / 详情图 / 爆款视频
  - source_platform
  - linked_product_ids
  - linked_sku_ids
  - linked_selling_points
  - linked_scenarios
  - file_refs
  - tags
  - quality_score
  - reuse_score
```

### 8）AssetPerformanceCard

```yaml
object_type: AssetPerformanceCard
fields:
  - card_id
  - asset_id
  - best_platform
  - best_people
  - best_scenario
  - best_metrics
  - usage_count
  - reusable
  - reuse_directions
```

### 9）AssetCluster

```yaml
object_type: AssetCluster
fields:
  - cluster_id
  - cluster_type   # 主图风格 / 钩子类型 / 长视频结构 / 模特风格
  - asset_ids
  - cluster_summary
  - winning_score
```

---

## 6.4 品牌规则与模式对象

### 10）BrandRule

```yaml
object_type: BrandRule
fields:
  - rule_id
  - brand_id
  - rule_type      # 调性 / 禁用词 / 风险词 / 必提点 / 平台规范
  - applies_to     # 主图 / 前3秒 / 长视频 / 标题 / 口播
  - rule_content
  - priority
```

### 11）WinningPattern

```yaml
object_type: WinningPattern
fields:
  - pattern_id
  - brand_id
  - pattern_type   # main_image / first3s / long_video / selling_point
  - platform
  - linked_asset_ids
  - linked_product_ids
  - linked_selling_points
  - linked_metrics
  - why_it_works
  - reuse_guidelines
```

### 12）FailedPattern

```yaml
object_type: FailedPattern
fields:
  - pattern_id
  - brand_id
  - pattern_type
  - platform
  - linked_asset_ids
  - linked_product_ids
  - linked_metrics
  - failure_reason
  - avoidance_guidelines
```

---

## 7. Brand-Aware 编译链设计

## 7.1 总体思路

品牌资产不应该作为“看板旁路”，而应当直接进入每个编译阶段。

### 统一链路

```text
外部机会信号
  + 品牌商品经营数据
  + 品牌商品库
  + 品牌素材库
  + 品牌规则与模式库
    ↓
Brand-Aware Opportunity Compiler
    ↓
Brand-Aware Selling Point Compiler
    ↓
Brand-Aware Variant Generator
    ↓
Brand-Aware Test & Scale
    ↓
Pattern Runtime 更新
```

---

## 7.2 各阶段怎么用品牌资产

### A. Opportunity 阶段

目标：判断这个热点对这个品牌值不值得做。

调用品牌资产：

* 历史高表现商品 / SKU
* 历史同类机会结果
* 品牌是否已有相关素材储备
* 品牌是否已有类似模式资产

输出时新增判断：

* 这个热点和品牌高表现商品的相似度
* 这个热点是值得新开，还是值得围绕现有商品做裂变
* 这个热点对品牌是否有素材准备优势

### B. Selling Point 阶段

目标：不是生成行业通用卖点，而是生成该品牌自己的高适配卖点。

调用品牌资产：

* 历史高表现卖点
* 高退款商品的负面反馈
* 商品特征 profile
* 品牌规则

输出时新增：

* 推荐卖点与历史高表现卖点的关系
* 需规避的历史高退款表达
* 平台化表达与品牌规则匹配度

### C. Variant 阶段

目标：主图 / 前3秒 / 长视频版本要优先调用品牌自己的高表现素材和模式。

调用品牌资产：

* 高表现主图 / 视频片段
* 资产 cluster
* WinningPattern / FailedPattern
* 品牌规则

输出时新增：

* 当前版本引用了哪些品牌高表现素材
* 当前版本避开了哪些失败模式
* 当前版本最接近哪些赢家模板

### D. Test / Scale 阶段

目标：放大不只是看当前版本数据，还要和品牌历史同类版本做对照。

调用品牌资产：

* 历史基线
* 历史同卖点 / 同平台 / 同商品表现
* 历史放大成功模板

输出时新增：

* 当前版本相对品牌历史基线的表现
* 是否进入品牌级 winner queue
* 是否值得沉淀为新模式

---

## 8. 技术架构升级

## 8.1 新增服务

### `brand_data_service`

职责：

* 接收经营数据导入
* 提供商品 / SKU / 表现查询
* 对外提供统一品牌数据 API

### `brand_asset_service`

职责：

* 管理主图 / 视频 / 模特 / 爆款素材
* 维护资产标签与关联关系
* 支持标签检索 + embedding 检索

### `brand_rule_service`

职责：

* 管理品牌规则
* 为各编译器提供规则检查

### `pattern_runtime_service`

职责：

* 管理 WinningPattern / FailedPattern
* 给编译器提供模式引用能力
* 负责模式回流更新

### `brand_context_service`

职责：

* 统一组装当前请求的品牌上下文
* 输出给 Opportunity / SellingPoint / Variant 编译器

---

## 8.2 Brand Context Assembler

建议新增一个核心底座组件：

### `BrandContextAssembler`

输入：

* brand_id
* platform
* product_id / sku_id（可选）
* target_people
* target_scenario
* current_stage

输出：

* 相关商品记录
* 相关表现记录
* 相关素材资产
* 相关品牌规则
* 相关赢家 / 失败模式

这个组件是品牌资产真正进入编译链的统一入口。

---

## 8.3 数据接入策略

## 第一阶段（最小可落地）

先接：

* 商品主档 / SKU 表
* SKU 基础经营数据
* 创意版本表现数据
* 素材库元数据
* 品牌规则文本

## 第二阶段

再接：

* 评论文本 / 退货原因摘要
* 素材自动标签
* 商品特征自动抽取
* 赢家 / 失败模式自动归纳

## 第三阶段

再接：

* 更细的人群与广告分组
* 更细的投放目标与归因数据
* 自动更新规则与模式

---

## 8.4 存储设计建议

### 关系型表

* products
* skus
* product_performance_records
* creative_performance_records
* brand_assets
* asset_performance_cards
* asset_clusters
* brand_rules
* winning_patterns
* failed_patterns

### 对象存储

* 图片 / 视频原文件
* 预览文件
* 详情页原文件

### 检索层

* 标签检索
* SKU / 商品 / 卖点 / 场景维度检索
* embedding 检索（后续增强）

---

## 9. 页面 PRD：Brand Data Hub

## 9.1 页面目标

把品牌自己的数据与素材，组织成一个可被系统调用的 Brand Asset Layer。

## 9.2 页面布局

### 左栏

* 商品 / SKU
* 经营表现
* 主图素材
* 视频素材
* 品牌规则
* 赢家模式
* 失败模式

### 中栏

资产列表 / 查询结果

### 右栏

资产详情 + 被引用情况 + 推荐动作

## 9.3 页面动作

* 导入数据
* 打标签
* 绑定商品与素材
* 标记高表现模式
* 标记失败模式
* 查看哪些方案引用了该资产

---

## 10. 页面 PRD：Brand Context Inspector

## 10.1 页面目标

在关键编译页面告诉用户：当前方案背后用了哪些品牌自己的上下文。

## 10.2 展示内容

* 当前卖点引用了哪些高表现商品
* 当前主图/视频引用了哪些高表现素材
* 当前建议遵循了哪些品牌规则
* 当前模式参考了哪些赢家模板

## 10.3 嵌入位置

* Radar 详情页右栏
* Compiler 右栏
* Main Image Lab / First3s Lab / Video Flow Studio 右栏
* Board 结果详情侧栏

---

## 11. API 设计（第一版）

### 数据导入

* `POST /api/brand-data/products/import`
* `POST /api/brand-data/skus/import`
* `POST /api/brand-data/performance/import`
* `POST /api/brand-data/assets/import`
* `POST /api/brand-data/rules/import`

### 数据查询

* `GET /api/brand-data/products`
* `GET /api/brand-data/skus`
* `GET /api/brand-data/performance`
* `GET /api/brand-data/assets`
* `GET /api/brand-data/rules`
* `GET /api/brand-data/patterns`

### Inspector / Context

* `GET /api/brand-context/opportunity/:id`
* `GET /api/brand-context/selling-point/:id`
* `GET /api/brand-context/variant/:id`

### 模式库

* `POST /api/brand-data/patterns/winning`
* `POST /api/brand-data/patterns/failed`

---

## 12. 与现有系统的衔接方式

## 12.1 输入衔接

* Opportunity Radar 在机会判断时调用品牌上下文
* Selling Point Compiler 在编译卖点时调用品牌上下文
* Main Image Lab / First3s Lab / Video Flow Studio 在生成版本时调用品牌上下文

## 12.2 输出衔接

* 测试板回流结果更新到 `creative_performance_records`
* 高表现版本更新到 `winning_patterns`
* 失败版本更新到 `failed_patterns`
* 资产复用信息更新到 `asset_performance_cards`

---

## 13. 实施计划（品牌资产专项）

### 阶段 1：0–3 周

目标：打通最小品牌数据层

交付：

* Product / SKU schema
* Performance schema
* BrandAsset schema
* BrandRule schema
* Brand Data Hub 基础页
* 手工/CSV 数据导入

### 阶段 2：4–6 周

目标：打通 Brand Context Assembler 与 Inspector

交付：

* BrandContextAssembler
* Compiler / Lab 页中的 Brand Context Inspector
* 基础品牌规则检查

### 阶段 3：7–10 周

目标：打通模式沉淀与编译器调用

交付：

* WinningPattern / FailedPattern
* Variant 生成器调用品牌高表现资产
* 测试结果回流更新模式库

---

## 14. 验收标准

### 产品验收

* 用户可以导入商品、SKU、表现、素材、规则
* 系统在卖点和版本生成时能展示引用了哪些品牌上下文
* 用户可以看到高表现商品/素材如何影响当前方案
* 用户可以标记赢家模式与失败模式

### 业务验收

* 生成的方案更贴近品牌自己的品类和商品特点
* 高表现品牌素材复用效率提升
* 低价值重复制作减少
* 首轮测试命中率提高

---

## 15. AI-coding 开工建议

### 第一批对象

* `ProductRecord`
* `SKURecord`
* `ProductPerformanceRecord`
* `CreativePerformanceRecord`
* `BrandAsset`
* `BrandRule`
* `WinningPattern`
* `FailedPattern`

### 第一批页面

* `/brand-data-hub`
* `BrandContextInspector`（作为嵌入式面板）

### 第一批服务

* `brand_data_service`
* `brand_asset_service`
* `brand_rule_service`
* `brand_context_service`
* `pattern_runtime_service`

### 第一批接口

* `POST /api/brand-data/products/import`
* `POST /api/brand-data/performance/import`
* `POST /api/brand-data/assets/import`
* `GET /api/brand-context/variant/:id`

---

## 16. 一句话总结

**Part 2 的交付目标，是让系统从“基于外部热点的通用创意编译器”，升级成“能够理解品牌自己的商品经营数据、商品库、素材库和规则库，并据此生成更贴近品牌自己的内容方案的 Brand-Aware 编译系统”。**
