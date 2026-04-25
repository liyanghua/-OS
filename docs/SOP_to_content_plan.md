

# 《Visual Strategy Compiler 融入内容策划工作台 PRD + 技术实现参考方案》

目标是把你现有的 **内容策划工作台** 升级为：

```text
机会卡 / 卖点策略 / 商品信息
        ↓
视觉策略编译器
        ↓
一组可测的生图策划案
        ↓
视觉工作台交互式生图
        ↓
专家评分 / 测图数据回流
        ↓
规则权重与策略模板沉淀
```

不是单独做一个“Prompt 工具”，而是在内容策划链路里增加一个核心中间层：

```text
Content Strategy → Visual Strategy → Creative Brief → Image Generation → Test Feedback
```

---

# 一、产品定位

## 1.1 产品模块名称

建议命名为：

```text
Visual Strategy Compiler
视觉策略编译器
```

在内容策划工作台里的页面名称可以叫：

```text
视觉策略编译
或
主图策划编译器
```

它不是生图模型，也不是单纯 Prompt Builder，而是把 **MD/SOP 专家规则** 编译成一组可执行、可编辑、可测试的视觉策划方案。

---

## 1.2 核心用户

| 用户    | 主要诉求        | 在本模块里的动作           |
| ----- | ----------- | ------------------ |
| 业务专家  | 把经验变成可复用规则  | 审核 RuleSpec，调整规则权重 |
| 操盘手   | 快速判断哪套图值得测  | 查看策略候选、选择测图方向      |
| 内容策划  | 从机会卡生成视觉方案  | 选择策划案、改卖点、改文案      |
| 视觉运营  | 快速生成图并修改    | 使用视觉工作台生图、局部调整     |
| 设计/美工 | 接收结构化 Brief | 按策划案做精修            |
| 产品负责人 | 沉淀类目方法论     | 查看规则效果、沉淀 RulePack |

---

## 1.3 MVP 场景

第一版只聚焦一个场景：

```text
儿童学习桌垫 / 淘宝主图 / 小红书封面可选 / 生图策划
```

因为你现在已有 6 个 MD 文件，且已经覆盖视觉核心、人物互动、功能卖点、图案风格、营销信息、竞争差异化六大层。比如视觉核心层要求先匹配店铺视觉体系，再做人群适配；人物互动层明确要求 6 岁以下围绕宝妈决策，7 岁以上围绕儿童使用者决策；功能卖点层要求优先竞品差异化，其次材质升级，再用效果对比。 

---

# 二、在现有内容策划工作台中的位置

你现有工作台大概率已经有这些对象：

```text
OpportunityCard 机会卡
SellingPointSpec 卖点规格
ProductProfile 商品信息
BrandProfile 品牌/店铺视觉
ContentPlan 内容计划
VisualWorkbench 视觉工作台
```

现在新增一个中间对象：

```text
VisualStrategyPack 视觉策略包
```

整体链路变成：

```text
热点/竞品/商品数据
        ↓
OpportunityCard 机会卡
        ↓
SellingPointSpec 卖点规格
        ↓
Visual Strategy Compiler
        ↓
VisualStrategyPack 视觉策略包
        ↓
CreativeBrief 生图策划案
        ↓
PromptSpec / WorkflowSpec
        ↓
Visual Workbench 交互式生图
        ↓
ImageVariant 图片版本
        ↓
TestTask 测图任务
        ↓
ResultSnapshot / FeedbackRecord
        ↓
Rule Weight 回流
```

---

# 三、PRD：核心功能设计

## 3.1 功能总览

| 模块          | 功能                                | MVP 是否做         |
| ----------- | --------------------------------- | --------------- |
| MD/SOP 导入   | 上传或读取专家 MD 文件                     | 做               |
| RuleSpec 抽取 | LLM 从 MD 中抽取候选规则                  | 做               |
| 专家审核        | 规则通过、拒绝、修改、调权重                    | 做               |
| RulePack 构建 | 形成儿童桌垫类目规则包                       | 做               |
| 策略编译        | 输入上下文，生成 6 类策略候选                  | 做               |
| 策划案生成       | StrategyCandidate → CreativeBrief | 做               |
| Prompt 生成   | CreativeBrief → PromptSpec        | 做               |
| 视觉工作台       | 选择方案、编辑字段、生图                      | 做 Lite          |
| 专家评分        | 对图片按维度评分                          | 做               |
| 测图回流        | CTR/CVR 等指标回传                     | 做字段预留，MVP 可手动录入 |
| 权重更新        | 高分规则加权，低分规则降权                     | 做简单版            |

---

# 四、用户主流程

## 4.1 业务专家：从 MD 到 RulePack

```text
上传 6 个 MD
  ↓
系统自动抽取 RuleSpec 候选
  ↓
专家在审核台查看规则
  ↓
通过 / 拒绝 / 修改 / 调权重
  ↓
构建 RulePack
  ↓
发布 children_desk_mat_rulepack_v1
```

这里要注意：RuleSpec 不要完全人工写。人工只负责定义元模型、审核核心规则和调权重。比如图案与风格层里明确“清新森系”适合低饱和绿色/棕色/白色，主打护眼自然，优先局部印花，这类内容应该由 LLM 抽取为候选 RuleSpec，再由专家确认。

---

## 4.2 内容策划：从机会卡到视觉策略包

```text
进入某个商品 / 机会卡
  ↓
点击「生成视觉策略」
  ↓
系统读取商品、店铺、人群、竞品、卖点信息
  ↓
调用 RulePack
  ↓
生成 6 个 StrategyCandidate
  ↓
内容策划选择 1-3 个进入视觉工作台
```

默认生成 6 类策略：

```text
1. 安全护眼型
2. 儿童代入型
3. 低龄温馨型
4. 高端质感型
5. 功能演示型
6. 差异突围型
```

---

## 4.3 视觉运营：从策划案到生图

```text
选择一个 StrategyCandidate
  ↓
查看 CreativeBrief
  ↓
编辑背景 / 人物 / 道具 / 卖点 / 文案 / 构图 / 风格
  ↓
生成 Prompt
  ↓
调用生图模型
  ↓
得到 4-8 张 ImageVariant
  ↓
人工选择 / 局部修改 / 再生成
  ↓
进入测图池
```

---

## 4.4 操盘手：从测图结果到规则沉淀

```text
查看测图结果
  ↓
识别胜出图片
  ↓
系统反查该图片使用了哪些规则
  ↓
高分规则自动加权
  ↓
低分规则进入复审
  ↓
沉淀新的类目策略模板
```

---

# 五、页面设计

## 5.1 页面一：Rule Review Console 规则审核台

### 页面目标

让业务专家快速审核 LLM 抽取出来的 RuleSpec。

### 页面结构

```text
左侧：规则列表
中间：规则详情
右侧：专家审核操作
底部：来源原文与影响预览
```

### 左侧规则列表

筛选项：

```text
维度：视觉核心 / 人物互动 / 功能卖点 / 图案风格 / 营销信息 / 竞争差异
状态：draft / approved / rejected / needs_edit / active
置信度：高 / 中 / 低
影响等级：高影响 / 普通 / 低影响
场景：淘宝主图 / 小红书封面 / 详情页首屏 / 视频首帧
```

列表字段：

```text
规则名称
所属维度
变量类别
推荐变量
适用条件
LLM 置信度
当前权重
审核状态
```

### 中间规则详情

展示：

```yaml
rule_id: rule_pattern_forest_local_print
dimension: pattern_style
variable_category: 图案位置
variable_name: 局部印花
trigger:
  - 店铺视觉为森系/简约/护眼
  - 商品卖点包含护眼/自然
recommendation:
  pattern_style: 清新森系
  pattern_position: 局部印花
constraints:
  must_avoid:
    - 高饱和满印
    - 过度花哨 IP
source_quote: ...
confidence: 0.87
```

### 右侧专家操作

按钮：

```text
通过
拒绝
修改后通过
标记为高影响规则
调高权重
调低权重
加入冲突规则
```

### 关键交互

专家点击“预览影响”后，系统展示：

```text
如果启用该规则，将影响哪些策略候选：
- 安全护眼型
- 高端质感型
- 差异突围型
```

---

## 5.2 页面二：Visual Strategy Compiler 策略编译页

### 页面目标

把内容策划工作台里的商品/机会/卖点上下文，编译成一组视觉策略候选。

### 页面结构

```text
左侧：输入上下文
中间：策略候选集
右侧：策略详情
底部：生成 Brief / 进入视觉工作台
```

### 左侧：输入上下文

字段：

```text
商品名称
商品类目
商品材质
价格带
目标年龄
性别倾向
核心卖点
店铺视觉体系
竞品主图特征
竞品核心卖点
平台场景
目标指标
```

示例：

```yaml
category: 儿童学习桌垫
scene: taobao_main_image
product:
  name: 叶子儿童学习桌垫
  material: 食品级硅胶
  claims:
    - 食品级无异味
    - 柔光护眼
    - 一擦即净
store_visual_system:
  style: 清新森系
  colors:
    - 奶白
    - 低饱和绿色
    - 原木色
competitor_context:
  common_visuals:
    - 满印卡通
    - 低价促销
  common_claims:
    - 防水
    - 耐磨
```

### 中间：策略候选集

每个策略卡片显示：

```text
策略名称
策略假设
目标人群
核心变量
预期优势
风险
综合评分
```

示例卡片：

```text
安全护眼型
假设：宝妈优先点击安全、护眼、干净、有质感的主图
核心变量：清新森系 / 无人物 / 食品级无异味 / 柔光护眼 / 局部印花
评分：91
风险：画面可能偏温和，点击冲击力不如 IP 满印
```

### 右侧：策略详情

展示六大维度变量：

```text
视觉核心层
人物互动层
功能卖点层
图案风格层
营销信息层
竞争差异化层
```

竞争差异化层尤其重要。你的专家文件强调差异化设计要先对齐店铺视觉体系，再优先打造视觉差异，同时不能脱离类目核心标签；例如同行多用纯色背景时，可以用森系叶子场景，同行多用满印图案时，可以用局部特写与留白。

---

## 5.3 页面三：Creative Brief 编辑页

### 页面目标

把策略候选转成可编辑的生图策划案。

### 页面结构

```text
左侧：策划案大纲
中间：画面结构预览
右侧：Creative Inspector
底部：Prompt 预览
```

### Creative Inspector 字段

```text
画布比例
平台场景
主体位置
产品占比
背景
人物
道具
图案
风格
光影
卖点文案
营销标签
负向约束
```

### 可编辑字段

| 字段   | 示例                         |
| ---- | -------------------------- |
| 背景   | 儿童书桌实景 / 纯色背景 / 森系场景       |
| 人物   | 无人物 / 儿童专注书写 / 低龄画画 / 家长陪伴 |
| 道具   | 台灯 / 书本 / 铅笔 / 小绿植 / 水滴    |
| 图案   | 局部叶子印花 / 满印卡通 / 极简线条       |
| 卖点   | 食品级无异味 / 柔光护眼 / 一擦即净       |
| 文案   | 孩子学习桌上的护眼小森林               |
| 负向约束 | 不要满屏卡通 / 不要强促销 / 不要杂乱桌面    |

---

## 5.4 页面四：Visual Workbench 视觉工作台

### 页面目标

完成交互式生图和多版本管理。

### 页面结构建议

```text
左栏：策略/Brief 列表
中间：图片画布与结果
右栏：对话 Agent + 字段编辑
底部：版本历史 + 评分 + 测图状态
```

### 右侧 Agent 支持的自然语言操作

用户输入：

```text
这个图太素了，加一点儿童感，但不要太卡通。
```

系统转为结构化 Patch：

```json
{
  "patch_type": "brief_patch",
  "changes": {
    "style.tone": "清新森系+轻童趣",
    "scene.props.add": ["彩色铅笔", "小动物书签"],
    "negative.add": ["高饱和卡通", "满屏图案"]
  }
}
```

用户输入：

```text
更突出一擦即净，但不要变成强功能演示图。
```

系统转为：

```json
{
  "changes": {
    "function_claims.add": ["一擦即净"],
    "scene.props.add": ["少量水滴"],
    "copywriting.selling_points": ["食品级无异味", "柔光不反光", "脏了一擦净"],
    "negative.add": ["夸张对比", "杂乱污渍"]
  }
}
```

功能卖点文件里已经说明，防水、防油、防烫、耐磨、防卷边等功能展示需要真实清晰，动作统一，并与店铺实用、品质的视觉定位一致，所以 Agent 修改时也要受这些约束控制。

---

## 5.5 页面五：Image Evaluation 测图与回流页

### 页面目标

让专家评分和真实数据都能回流到规则权重。

评分维度：

| 评分项   |  权重 | 说明              |
| ----- | --: | --------------- |
| 第一眼停留 | 20% | 搜索页是否有点击吸引力     |
| 人群匹配  | 15% | 是否匹配宝妈和儿童       |
| 功能清晰  | 20% | 安全、护眼、易清洁是否表达清楚 |
| 风格一致  | 15% | 是否符合店铺视觉体系      |
| 竞争差异  | 20% | 是否避开同质化         |
| 生图质量  | 10% | 是否真实、干净、可用      |

反馈字段：

```yaml
image_id: img_001
strategy_id: strat_safe_eye_care_001
rule_ids:
  - rule_visual_scene_desk
  - rule_pattern_forest_local
  - rule_function_eye_care
expert_score:
  first_glance: 8
  audience_fit: 9
  function_clarity: 8
  style_fit: 9
  differentiation: 8
  generation_quality: 8
business_metrics:
  impressions: 10000
  clicks: 530
  ctr: 0.053
decision: winner
```

---

# 六、核心对象模型

## 6.1 SourceDocument

```ts
export type SourceDocument = {
  id: string;
  category: string;
  title: string;
  fileName: string;
  dimension:
    | "visual_core"
    | "people_interaction"
    | "function_selling_point"
    | "pattern_style"
    | "marketing_info"
    | "differentiation";
  rawMarkdown: string;
  version: string;
  status: "uploaded" | "parsed" | "archived";
  createdAt: string;
};
```

---

## 6.2 RuleSpec

```ts
export type RuleSpec = {
  id: string;
  rulePackId?: string;

  dimension:
    | "visual_core"
    | "people_interaction"
    | "function_selling_point"
    | "pattern_style"
    | "marketing_info"
    | "differentiation";

  variableCategory: string;
  variableName: string;
  optionName: string;

  categoryScope: string[];
  sceneScope: string[];

  trigger: {
    conditions: string[];
    requiredContext: string[];
  };

  recommendation: {
    variableSelection: Record<string, unknown>;
    creativeDirection: Record<string, unknown>;
    copywritingDirection?: Record<string, unknown>;
    promptDirection?: Record<string, unknown>;
  };

  constraints: {
    mustFollow: string[];
    mustAvoid: string[];
    conflictRules: string[];
  };

  scoring: {
    baseWeight: number;
    boostFactors: string[];
    penaltyFactors: string[];
  };

  evidence: {
    sourceDocumentId: string;
    sourceQuote: string;
    confidence: number;
  };

  review: {
    status: "draft" | "approved" | "rejected" | "needs_edit";
    reviewer?: string;
    comments?: string;
  };

  lifecycle: {
    version: string;
    status: "candidate" | "active" | "deprecated";
    createdAt: string;
    updatedAt: string;
  };
};
```

---

## 6.3 RulePack

```ts
export type RulePack = {
  id: string;
  category: string;
  name: string;
  version: string;
  dimensions: string[];
  ruleIds: string[];
  defaultStrategyArchetypes: StrategyArchetype[];
  status: "draft" | "active" | "archived";
  metrics: {
    ruleCount: number;
    approvedRuleCount: number;
    avgConfidence: number;
  };
  createdAt: string;
  updatedAt: string;
};

export type StrategyArchetype =
  | "safe_eye_care"
  | "child_engagement"
  | "warm_low_age"
  | "premium_texture"
  | "function_demo"
  | "differentiation_breakthrough";
```

---

## 6.4 VisualStrategyPack

这是要接入你内容策划工作台的核心对象。

```ts
export type VisualStrategyPack = {
  id: string;
  source: {
    opportunityCardId?: string;
    sellingPointSpecId?: string;
    productId: string;
    brandId?: string;
    contentPlanId?: string;
  };

  category: string;
  scene: "taobao_main_image" | "xhs_cover" | "detail_first_screen" | "video_first_frame";

  rulePackId: string;
  contextSpecId: string;

  candidates: StrategyCandidate[];

  status:
    | "compiled"
    | "partially_selected"
    | "sent_to_visual_workbench"
    | "testing"
    | "completed";

  createdAt: string;
  updatedAt: string;
};
```

---

## 6.5 StrategyCandidate

```ts
export type StrategyCandidate = {
  id: string;
  visualStrategyPackId: string;
  name: string;
  archetype: StrategyArchetype;
  hypothesis: string;
  targetAudience: string[];

  selectedVariables: {
    visualCore: Record<string, unknown>;
    peopleInteraction: Record<string, unknown>;
    functionSellingPoint: Record<string, unknown>;
    patternStyle: Record<string, unknown>;
    marketingInfo: Record<string, unknown>;
    differentiation: Record<string, unknown>;
  };

  rationale: string[];
  risks: string[];

  score: {
    total: number;
    brandFit: number;
    audienceFit: number;
    differentiation: number;
    functionClarity: number;
    generationControl: number;
    conversionPotential: number;
  };

  ruleRefs: string[];
  status: "generated" | "edited" | "approved" | "rejected" | "sent_to_workbench";
};
```

---

## 6.6 CreativeBrief

```ts
export type CreativeBrief = {
  id: string;
  strategyCandidateId: string;

  canvas: {
    ratio: "1:1" | "3:4" | "4:5" | "16:9";
    platform: string;
    textArea: "left" | "right" | "top" | "bottom" | "none";
    productVisibilityMin: number;
  };

  scene: {
    background: string;
    environment: string;
    props: string[];
    forbiddenProps: string[];
  };

  product: {
    placement: string;
    scale: string;
    angle: string;
    visibleFeatures: string[];
  };

  style: {
    tone: string;
    colorPalette: string[];
    lighting: string;
    texture: string;
  };

  people: {
    enabled: boolean;
    age?: string;
    gender?: string;
    action?: string;
    adultVisible?: boolean;
  };

  copywriting: {
    headline?: string;
    sellingPoints: string[];
    labels: string[];
    priceVisible: boolean;
  };

  negative: string[];
};
```

---

## 6.7 PromptSpec

```ts
export type PromptSpec = {
  id: string;
  creativeBriefId: string;

  provider: "midjourney" | "comfyui" | "sdxl" | "flux" | "jimeng" | "tongyi";

  positivePromptZh: string;
  negativePromptZh: string;
  positivePromptEn?: string;
  negativePromptEn?: string;

  generationParams: {
    width: number;
    height: number;
    steps?: number;
    cfgScale?: number;
    seed?: number;
  };

  workflowJson?: Record<string, unknown>;
};
```

---

## 6.8 FeedbackRecord

```ts
export type FeedbackRecord = {
  id: string;
  imageVariantId: string;
  strategyCandidateId: string;
  ruleIds: string[];

  expertScore: {
    firstGlance: number;
    audienceFit: number;
    functionClarity: number;
    styleFit: number;
    differentiation: number;
    generationQuality: number;
    overall: number;
  };

  businessMetrics?: {
    impressions?: number;
    clicks?: number;
    ctr?: number;
    favorites?: number;
    addToCart?: number;
    conversionRate?: number;
  };

  decision: "enter_test_pool" | "revise" | "reject" | "winner";
  comments?: string;
  createdAt: string;
};
```

---

# 七、后端技术架构

## 7.1 推荐目录结构

假设你现有内容策划平台类似 Growth Lab，可以新增模块：

```text
apps/content_planning/
  modules/
    visual_strategy_compiler/
      api/
        routes.py
      schemas/
        source_document.py
        rule_spec.py
        rule_pack.py
        context_spec.py
        visual_strategy_pack.py
        strategy_candidate.py
        creative_brief.py
        prompt_spec.py
        feedback_record.py
      services/
        md_ingestion_service.py
        rule_extractor.py
        rule_normalizer.py
        rule_review_service.py
        rulepack_builder.py
        context_compiler.py
        strategy_compiler.py
        brief_compiler.py
        prompt_compiler.py
        workbench_adapter.py
        feedback_engine.py
        weight_updater.py
      prompts/
        extract_rules.md
        normalize_rules.md
        compile_strategy.md
        compile_brief.md
        compile_prompt.md
        patch_brief.md
      storage/
        repository.py
      tests/
        test_rule_extractor.py
        test_rulepack_builder.py
        test_strategy_compiler.py
        test_brief_compiler.py
        test_prompt_compiler.py
        test_feedback_engine.py
```

如果你想独立部署，可以是：

```text
apps/visual_strategy_compiler/
```

如果要深度融入内容策划工作台，建议放在：

```text
apps/content_planning/modules/visual_strategy_compiler/
```

---

## 7.2 服务分层

```text
API Layer
  接收前端请求

Application Service Layer
  处理业务流程：导入、抽取、审核、编译、生图、反馈

Domain Layer
  RuleSpec / RulePack / StrategyCandidate / CreativeBrief

Compiler Layer
  StrategyCompiler / BriefCompiler / PromptCompiler

Infrastructure Layer
  DB / LLM / Image Provider / File Storage / Metrics Connector
```

---

# 八、数据库设计

第一版 SQLite，后续 PostgreSQL。

```sql
CREATE TABLE source_documents (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  title TEXT,
  file_name TEXT,
  dimension TEXT,
  raw_markdown TEXT,
  version TEXT,
  status TEXT,
  created_at TEXT
);

CREATE TABLE rule_specs (
  id TEXT PRIMARY KEY,
  rule_pack_id TEXT,
  dimension TEXT,
  variable_category TEXT,
  variable_name TEXT,
  option_name TEXT,
  category_scope_json TEXT,
  scene_scope_json TEXT,
  trigger_json TEXT,
  recommendation_json TEXT,
  constraints_json TEXT,
  scoring_json TEXT,
  evidence_json TEXT,
  review_json TEXT,
  lifecycle_json TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE rule_packs (
  id TEXT PRIMARY KEY,
  category TEXT,
  name TEXT,
  version TEXT,
  dimensions_json TEXT,
  rule_ids_json TEXT,
  archetypes_json TEXT,
  status TEXT,
  metrics_json TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE context_specs (
  id TEXT PRIMARY KEY,
  source_type TEXT,
  source_id TEXT,
  category TEXT,
  scene TEXT,
  context_json TEXT,
  created_at TEXT
);

CREATE TABLE visual_strategy_packs (
  id TEXT PRIMARY KEY,
  source_json TEXT,
  category TEXT,
  scene TEXT,
  rule_pack_id TEXT,
  context_spec_id TEXT,
  status TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE strategy_candidates (
  id TEXT PRIMARY KEY,
  visual_strategy_pack_id TEXT,
  name TEXT,
  archetype TEXT,
  hypothesis TEXT,
  target_audience_json TEXT,
  selected_variables_json TEXT,
  rationale_json TEXT,
  risks_json TEXT,
  score_json TEXT,
  rule_refs_json TEXT,
  status TEXT,
  created_at TEXT
);

CREATE TABLE creative_briefs (
  id TEXT PRIMARY KEY,
  strategy_candidate_id TEXT,
  canvas_json TEXT,
  scene_json TEXT,
  product_json TEXT,
  style_json TEXT,
  people_json TEXT,
  copywriting_json TEXT,
  negative_json TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE prompt_specs (
  id TEXT PRIMARY KEY,
  creative_brief_id TEXT,
  provider TEXT,
  positive_prompt_zh TEXT,
  negative_prompt_zh TEXT,
  positive_prompt_en TEXT,
  negative_prompt_en TEXT,
  generation_params_json TEXT,
  workflow_json TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE image_variants (
  id TEXT PRIMARY KEY,
  strategy_candidate_id TEXT,
  creative_brief_id TEXT,
  prompt_spec_id TEXT,
  image_url TEXT,
  provider TEXT,
  seed TEXT,
  generation_params_json TEXT,
  status TEXT,
  created_at TEXT
);

CREATE TABLE feedback_records (
  id TEXT PRIMARY KEY,
  image_variant_id TEXT,
  strategy_candidate_id TEXT,
  rule_ids_json TEXT,
  expert_score_json TEXT,
  business_metrics_json TEXT,
  decision TEXT,
  comments TEXT,
  created_at TEXT
);

CREATE TABLE rule_weight_history (
  id TEXT PRIMARY KEY,
  rule_id TEXT,
  old_weight REAL,
  new_weight REAL,
  delta REAL,
  reason TEXT,
  feedback_record_id TEXT,
  created_at TEXT
);
```

---

# 九、API 设计

## 9.1 导入 MD/SOP

```http
POST /api/content-planning/visual-strategy/source-documents/import
```

请求：

```json
{
  "category": "children_desk_mat",
  "documents": [
    {
      "file_name": "6大维度·42个细分变量选择逻辑01.md",
      "dimension": "visual_core",
      "raw_markdown": "..."
    }
  ]
}
```

返回：

```json
{
  "source_document_ids": ["src_001", "src_002"],
  "status": "uploaded"
}
```

---

## 9.2 抽取 RuleSpec 候选

```http
POST /api/content-planning/visual-strategy/rules/extract
```

请求：

```json
{
  "category": "children_desk_mat",
  "source_document_ids": ["src_001", "src_002", "src_003"],
  "mode": "llm_extract"
}
```

返回：

```json
{
  "candidate_rule_count": 126,
  "rules": [
    {
      "id": "rule_001",
      "dimension": "pattern_style",
      "variable_category": "图案位置",
      "variable_name": "局部印花",
      "option_name": "边角印花/中间留白",
      "review": {
        "status": "draft"
      }
    }
  ]
}
```

---

## 9.3 专家审核 RuleSpec

```http
PATCH /api/content-planning/visual-strategy/rules/{rule_id}/review
```

请求：

```json
{
  "status": "approved",
  "base_weight": 0.88,
  "comments": "适合清新森系儿童桌垫主图"
}
```

---

## 9.4 构建 RulePack

```http
POST /api/content-planning/visual-strategy/rulepacks/build
```

请求：

```json
{
  "category": "children_desk_mat",
  "name": "儿童桌垫主图视觉策略规则包",
  "version": "v1",
  "include_status": ["approved"]
}
```

返回：

```json
{
  "rule_pack_id": "rulepack_children_desk_mat_v1",
  "rule_count": 52,
  "status": "active"
}
```

---

## 9.5 从内容策划对象编译视觉策略

```http
POST /api/content-planning/visual-strategy/compile-from-content
```

请求：

```json
{
  "source": {
    "opportunity_card_id": "opp_001",
    "selling_point_spec_id": "sp_001",
    "product_id": "prod_001",
    "brand_id": "brand_001"
  },
  "scene": "taobao_main_image",
  "rule_pack_id": "rulepack_children_desk_mat_v1",
  "candidate_count": 6
}
```

后端做：

```text
读取 OpportunityCard
读取 SellingPointSpec
读取 ProductProfile
读取 BrandProfile / StoreVisualSystem
读取 CompetitorContext
组装 ContextSpec
调用 StrategyCompiler
生成 VisualStrategyPack
```

返回：

```json
{
  "visual_strategy_pack_id": "vsp_001",
  "candidates": [
    {
      "strategy_id": "strat_001",
      "name": "安全护眼型",
      "score": {
        "total": 0.91
      },
      "brief_id": "brief_001",
      "prompt_spec_id": "prompt_001"
    }
  ]
}
```

---

## 9.6 手动输入上下文编译

```http
POST /api/content-planning/visual-strategy/compile
```

请求：

```json
{
  "rule_pack_id": "rulepack_children_desk_mat_v1",
  "candidate_count": 6,
  "context": {
    "category": "children_desk_mat",
    "scene": "taobao_main_image",
    "product": {
      "name": "叶子儿童学习桌垫",
      "material": "食品级硅胶",
      "priceBand": "mid",
      "claims": ["食品级无异味", "柔光护眼", "一擦即净"],
      "targetAgeRange": "3-9",
      "gender": "neutral",
      "patternTheme": "叶子"
    },
    "storeVisualSystem": {
      "style": "清新森系",
      "colors": ["奶白", "浅绿色", "原木色"],
      "typography": "简约黑体",
      "imageTone": "明亮通透",
      "avoid": ["强促销", "高饱和卡通", "杂乱背景"]
    },
    "audience": {
      "buyer": "宝妈",
      "user": "儿童",
      "decisionLogic": ["安全", "护眼", "易清洁", "好看"]
    },
    "competitorContext": {
      "commonVisuals": ["纯色背景", "满印卡通", "低价促销"],
      "commonClaims": ["防水", "耐磨"],
      "differentiationOpportunities": ["食品级无异味", "柔光护眼", "森系学习场景"]
    },
    "platformConstraints": {
      "ratio": "1:1",
      "copyLimit": 3,
      "productVisibilityMin": 0.65
    }
  }
}
```

---

## 9.7 修改策划案

```http
POST /api/content-planning/visual-strategy/candidates/{strategy_id}/patch
```

请求：

```json
{
  "instruction": "更突出一擦即净，但保持清新森系，不要变成强功能演示图"
}
```

返回：

```json
{
  "strategy_id": "strat_001",
  "updated_brief_id": "brief_001_v2",
  "updated_prompt_spec_id": "prompt_001_v2",
  "changed_fields": [
    "scene.props",
    "copywriting.sellingPoints",
    "negative"
  ]
}
```

---

## 9.8 推送到视觉工作台

```http
POST /api/content-planning/visual-strategy/candidates/{strategy_id}/send-to-workbench
```

请求：

```json
{
  "brief_id": "brief_001",
  "prompt_spec_id": "prompt_001",
  "workspace_id": "workspace_001"
}
```

返回：

```json
{
  "workbench_project_id": "vwb_001",
  "status": "created"
}
```

---

## 9.9 生图

```http
POST /api/visual-workbench/generate
```

请求：

```json
{
  "workbench_project_id": "vwb_001",
  "strategy_candidate_id": "strat_001",
  "prompt_spec_id": "prompt_001",
  "provider": "comfyui",
  "num_images": 4
}
```

---

## 9.10 评分与回流

```http
POST /api/content-planning/visual-strategy/feedback
```

请求：

```json
{
  "image_variant_id": "img_001",
  "strategy_candidate_id": "strat_001",
  "expert_score": {
    "firstGlance": 8,
    "audienceFit": 9,
    "functionClarity": 8,
    "styleFit": 9,
    "differentiation": 8,
    "generationQuality": 8,
    "overall": 8.4
  },
  "business_metrics": {
    "impressions": 10000,
    "clicks": 530,
    "ctr": 0.053
  },
  "decision": "winner",
  "comments": "画面干净，护眼感强，一擦即净表达可再增强"
}
```

---

# 十、策略编译算法

## 10.1 编译输入

```text
RulePack
+ ContextSpec
+ SceneAdapter
+ HistoricalWeights
```

## 10.2 编译流程

```text
Step 1：加载 RulePack
Step 2：加载 ContextSpec
Step 3：按 category / scene 过滤规则
Step 4：按 trigger.conditions 匹配规则
Step 5：按 6 大维度构建变量池
Step 6：按 6 个策略 archetype 生成候选
Step 7：执行冲突检测
Step 8：计算候选分数
Step 9：生成 StrategyCandidate
Step 10：生成 CreativeBrief
Step 11：生成 PromptSpec
```

---

## 10.3 规则匹配伪代码

```python
def match_rules(context, rules):
    matched = []

    for rule in rules:
        if context["category"] not in rule["categoryScope"]:
            continue

        if (
            context["scene"] not in rule["sceneScope"]
            and "all" not in rule["sceneScope"]
        ):
            continue

        score = rule["scoring"]["baseWeight"]

        for cond in rule["trigger"]["conditions"]:
            if condition_satisfied(cond, context):
                score += 0.05

        for boost in rule["scoring"]["boostFactors"]:
            if boost_satisfied(boost, context):
                score += 0.05

        for penalty in rule["scoring"]["penaltyFactors"]:
            if penalty_satisfied(penalty, context):
                score -= 0.05

        if score >= 0.5:
            matched.append({
                "rule": rule,
                "matchedScore": min(score, 1.0)
            })

    return matched
```

---

## 10.4 候选策略生成

固定 6 个 Archetype：

```python
ARCHETYPES = [
    "safe_eye_care",
    "child_engagement",
    "warm_low_age",
    "premium_texture",
    "function_demo",
    "differentiation_breakthrough"
]
```

每个 Archetype 有偏好：

```python
ARCHETYPE_PREFERENCES = {
    "safe_eye_care": {
        "function_keywords": ["食品级", "护眼", "无异味"],
        "style_keywords": ["清新森系", "局部印花", "明亮通透"],
        "people_keywords": ["无人物", "专注书写"]
    },
    "function_demo": {
        "function_keywords": ["防水", "一擦即净", "防卷边"],
        "style_keywords": ["真实清晰", "功能演示"],
        "people_keywords": ["无人物"]
    },
    "differentiation_breakthrough": {
        "differentiation_keywords": ["森系场景", "局部留白", "避开满印卡通"]
    }
}
```

---

## 10.5 候选评分公式

```text
total_score =
brand_fit * 0.20
+ audience_fit * 0.18
+ function_clarity * 0.18
+ differentiation * 0.18
+ category_recognition * 0.12
+ generation_control * 0.08
+ conversion_potential * 0.06
```

其中：

```text
brand_fit：是否符合店铺视觉体系
audience_fit：是否匹配宝妈/儿童年龄段
function_clarity：核心卖点是否清晰
differentiation：是否避开同质化
category_recognition：是否一眼看出儿童桌垫
generation_control：生图模型是否容易稳定生成
conversion_potential：是否有点击和转化潜力
```

---

## 10.6 冲突检测规则

第一版硬编码即可：

```python
CONFLICT_RULES = [
    {
        "if": ["style=清新森系", "marketing=强促销大红标"],
        "reason": "清新森系与强促销标签冲突"
    },
    {
        "if": ["pattern=满印IP", "claim=护眼简约"],
        "reason": "满印IP会削弱护眼简约表达"
    },
    {
        "if": ["audience=7岁以上", "adultVisible=true"],
        "reason": "7岁以上儿童可能不喜欢被监督感"
    },
    {
        "if": ["store_style=高端极简", "priceVisible=true"],
        "reason": "高端极简主图不宜突出低价"
    }
]
```

人物互动文件里也说明，家长陪伴更适合 6 岁以下宝妈安全信任诉求，7 岁以上儿童可能反感被监督，成人出镜会降低代入感。

---

# 十一、Prompt 生成方案

## 11.1 Prompt 编译模板

不要让 LLM 完全自由写 Prompt，应该用模板：

```text
[画面类型]
[平台与比例]
[产品主体]
[背景场景]
[产品材质]
[图案与风格]
[人物/无人物]
[道具]
[构图]
[光影]
[文案留白]
[画质]
[负向约束]
```

## 11.2 中文 Prompt 模板

```text
高质量电商主图，{ratio} 方图，{category} 产品摄影，
{style_tone} 风格，背景为 {background}，
主体是一张 {product_material} 的 {product_name}，
产品位于 {product_placement}，占画面约 {product_scale}，
图案为 {pattern_style}，{pattern_position}，
画面包含 {props}，
光线为 {lighting}，质感为 {texture}，
构图为 {composition}，{text_area} 留白用于卖点文案，
整体画面干净、真实、高级、清晰，
适合 {platform} 使用。
```

## 11.3 Negative Prompt 模板

```text
杂乱桌面，过多物品，高饱和卡通，满屏图案，
廉价塑料感，暗光，强阴影，模糊，低清晰度，
夸张促销标签，文字乱码，医疗化宣传，产品变形，
人物遮挡产品，过度摆拍，不符合儿童学习用品场景
```

---

# 十二、与内容策划工作台的数据打通

## 12.1 从 OpportunityCard 读取

```ts
type OpportunityCardForVisual = {
  opportunityId: string;
  category: string;
  trendSignal: string;
  targetAudience: string[];
  painPoints: string[];
  contentAngles: string[];
  recommendedClaims: string[];
};
```

映射到 ContextSpec：

```text
targetAudience → audience
painPoints → decisionLogic
recommendedClaims → product.claims
contentAngles → strategy hints
```

---

## 12.2 从 SellingPointSpec 读取

```ts
type SellingPointSpecForVisual = {
  coreClaim: string;
  supportingClaims: string[];
  proofPoints: string[];
  forbiddenClaims: string[];
  platformExpressions: {
    shelf: string;
    xhs: string;
    first3s: string;
  };
};
```

映射：

```text
coreClaim → copywriting headline / function primary claim
supportingClaims → sellingPoints
forbiddenClaims → negative constraints
platformExpressions.shelf → taobao_main_image copy
```

---

## 12.3 从 ProductProfile 读取

```ts
type ProductProfileForVisual = {
  productId: string;
  name: string;
  category: string;
  material: string;
  priceBand: string;
  targetAgeRange?: string;
  gender?: string;
  productImages?: string[];
  claims: string[];
};
```

映射：

```text
material → product.material
claims → function layer
targetAgeRange → people_interaction
gender → people_interaction / style
```

---

## 12.4 从 BrandProfile / StoreVisualSystem 读取

```ts
type StoreVisualSystem = {
  style: string;
  colors: string[];
  typography: string;
  imageTone: string;
  allowedElements: string[];
  avoidElements: string[];
  exampleImages: string[];
};
```

映射：

```text
style → brand_fit scoring
colors → CreativeBrief.style.colorPalette
avoidElements → negative prompt
exampleImages → reference images
```

营销信息文件明确要求文案、标签、价格露出都要先对齐店铺视觉体系，再按“唯一性卖点 → 促销标签 → 低价策略”选择，因此 StoreVisualSystem 必须进入 ContextSpec，而不能只靠 Prompt 临时描述。

---

# 十三、权重回流方案

## 13.1 回流对象

每张图要记录：

```text
用了哪个 StrategyCandidate
用了哪个 CreativeBrief
用了哪个 PromptSpec
关联哪些 RuleSpec
专家评分是多少
真实 CTR/CVR 是多少
```

## 13.2 简单权重更新算法

```python
def update_rule_weights(feedback):
    rule_ids = feedback["ruleIds"]
    expert_score = feedback["expertScore"]["overall"]
    ctr = feedback.get("businessMetrics", {}).get("ctr")

    delta = 0.0

    if expert_score >= 8:
        delta += 0.02
    elif expert_score < 6:
        delta -= 0.02

    if ctr is not None:
        baseline = get_category_baseline_ctr("children_desk_mat")
        if ctr > baseline * 1.15:
            delta += 0.03
        elif ctr < baseline * 0.85:
            delta -= 0.03

    for rule_id in rule_ids:
        adjust_rule_weight(rule_id, delta)
        write_rule_weight_history(rule_id, delta, feedback["id"])
```

## 13.3 规则状态自动变化

```text
连续 3 次高分 → active_high_confidence
连续 3 次低分 → needs_review
出现合规问题 → deprecated
人工强制修正 → expert_locked
```

---

# 十四、MVP 实施分期

## Phase 0：接入点梳理，1-2 天

目标：

```text
明确现有内容策划工作台有哪些对象可以提供上下文。
```

任务：

```text
梳理 OpportunityCard
梳理 SellingPointSpec
梳理 ProductProfile
梳理 BrandProfile
梳理 VisualWorkbench 当前接口
确定 VisualStrategyPack 挂在哪个页面
```

产出：

```text
字段映射表
ContextSpec v1
API 接入点清单
```

---

## Phase 1：RuleSpec 生产线，3-5 天

目标：

```text
6 个 MD → RuleSpec 候选 → 专家审核 → RulePack
```

任务：

```text
实现 SourceDocument 导入
实现 LLM Rule Extractor
实现 Rule Review Console 简版
实现 RulePack Builder
```

验收：

```text
6 个 MD 全部入库
每个 MD 抽取 15-30 条候选规则
专家能审核 Top 50 条
生成 children_desk_mat_rulepack_v1
```

---

## Phase 2：Strategy Compiler，3-5 天

目标：

```text
从内容策划上下文生成 6 个策略候选。
```

任务：

```text
实现 ContextCompiler
实现 StrategyCompiler
实现 6 个 Archetype
实现评分和冲突检测
生成 VisualStrategyPack
```

验收：

```text
从一个儿童桌垫 OpportunityCard 生成 6 个 StrategyCandidate
每个 Candidate 有策略假设、变量组合、评分、规则来源
```

---

## Phase 3：Brief + Prompt Compiler，2-3 天

目标：

```text
StrategyCandidate → CreativeBrief → PromptSpec
```

任务：

```text
实现 BriefCompiler
实现 PromptCompiler
实现 Prompt 模板
实现负向约束生成
```

验收：

```text
每个策略候选都能生成结构化 Brief
每个 Brief 都能生成可复制 Prompt
```

---

## Phase 4：视觉工作台接入，4-7 天

目标：

```text
在视觉工作台中交互式编辑和生图。
```

任务：

```text
新增 VisualStrategyPack 入口
新增策略候选列表
新增 Creative Inspector
接入现有生图接口
保存 ImageVariant
支持自然语言 patch
```

验收：

```text
用户可以从策略候选进入视觉工作台
可以编辑背景/人物/卖点/文案
可以生成图片
可以保存版本
```

---

## Phase 5：评分与权重回流，3-5 天

目标：

```text
让专家评分和测图数据改变规则权重。
```

任务：

```text
实现 FeedbackRecord
实现专家评分 UI
实现 business_metrics 手动录入
实现 rule_weight_history
实现 WeightUpdater
```

验收：

```text
高分图片关联规则自动加权
低分图片关联规则自动降权
Rule Review Console 可查看权重变化
```

---

# 十五、验收指标

## 15.1 系统链路指标

| 指标                  | MVP 目标 |
| ------------------- | -----: |
| MD 入库成功率            |   100% |
| RuleSpec 抽取完整率      |  ≥ 80% |
| 专家审核通过率             |  ≥ 40% |
| 策略候选生成成功率           |  ≥ 95% |
| CreativeBrief 生成成功率 |  ≥ 95% |
| Prompt 可用率          |  ≥ 85% |
| 生图成功率               |  ≥ 80% |

## 15.2 业务质量指标

| 指标             |    MVP 目标 |
| -------------- | --------: |
| 策略候选专家可用率      |     ≥ 70% |
| 图片专家评分 ≥ 8 分占比 |     ≥ 30% |
| 平均人工修改次数       |     ≤ 3 次 |
| 测图 CTR 优于旧图占比  | ≥ 20%-30% |
| 有效规则沉淀数        |    ≥ 30 条 |
| 高置信策略模板        |     ≥ 3 个 |

---

# 十六、AI-coding Prompt：可直接交给 Cursor/Codex

下面这段可以直接喂给 AI-coding。

```text
请在现有内容策划工作台中新增 Visual Strategy Compiler 模块，用于将专家 MD/SOP 编译成可生图的视觉策略候选方案，并对接视觉工作台。

目标链路：
MD/SOP → RuleSpec 候选 → 专家审核 → RulePack → Strategy Compiler → VisualStrategyPack → CreativeBrief → PromptSpec → Visual Workbench 生图 → 专家评分 / 测图数据 → Rule Weight 回流。

技术要求：
1. 后端使用现有项目技术栈。如果没有明确约束，使用 FastAPI + SQLite。
2. 模块路径建议：
   apps/content_planning/modules/visual_strategy_compiler/
3. 新增 schemas：
   - SourceDocument
   - RuleSpec
   - RulePack
   - ContextSpec
   - VisualStrategyPack
   - StrategyCandidate
   - CreativeBrief
   - PromptSpec
   - ImageVariant
   - FeedbackRecord
4. 新增 services：
   - md_ingestion_service.py
   - rule_extractor.py
   - rule_normalizer.py
   - rule_review_service.py
   - rulepack_builder.py
   - context_compiler.py
   - strategy_compiler.py
   - brief_compiler.py
   - prompt_compiler.py
   - workbench_adapter.py
   - feedback_engine.py
   - weight_updater.py
5. 新增 prompts：
   - extract_rules.md
   - normalize_rules.md
   - compile_strategy.md
   - compile_brief.md
   - compile_prompt.md
   - patch_brief.md
6. 新增数据库表：
   - source_documents
   - rule_specs
   - rule_packs
   - context_specs
   - visual_strategy_packs
   - strategy_candidates
   - creative_briefs
   - prompt_specs
   - image_variants
   - feedback_records
   - rule_weight_history
7. 新增 API：
   - POST /api/content-planning/visual-strategy/source-documents/import
   - POST /api/content-planning/visual-strategy/rules/extract
   - GET /api/content-planning/visual-strategy/rules
   - PATCH /api/content-planning/visual-strategy/rules/{rule_id}/review
   - POST /api/content-planning/visual-strategy/rulepacks/build
   - GET /api/content-planning/visual-strategy/rulepacks/{rule_pack_id}
   - POST /api/content-planning/visual-strategy/compile-from-content
   - POST /api/content-planning/visual-strategy/compile
   - POST /api/content-planning/visual-strategy/candidates/{strategy_id}/patch
   - POST /api/content-planning/visual-strategy/candidates/{strategy_id}/send-to-workbench
   - POST /api/visual-workbench/generate
   - POST /api/content-planning/visual-strategy/feedback
8. Rule extraction 第一版可以使用 mock LLM extractor，但要保留 prompts/extract_rules.md，并保证返回结构化 RuleSpec。
9. Strategy Compiler 第一版使用 6 个固定 archetype：
   - safe_eye_care
   - child_engagement
   - warm_low_age
   - premium_texture
   - function_demo
   - differentiation_breakthrough
10. 每个 StrategyCandidate 必须包含：
   - name
   - archetype
   - hypothesis
   - targetAudience
   - selectedVariables 六大维度
   - rationale
   - risks
   - score
   - ruleRefs
11. CreativeBrief 必须包含：
   - canvas
   - scene
   - product
   - style
   - people
   - copywriting
   - negative
12. PromptSpec 必须输出中文 positive prompt、negative prompt，并预留英文 prompt 和 workflow_json。
13. Visual Workbench 接入：
   - 可以从 StrategyCandidate 创建 workbench_project
   - 可以展示 CreativeBrief
   - 可以编辑背景、人物、道具、卖点、文案、风格、负向约束
   - 可以生成 ImageVariant
14. FeedbackEngine：
   - 支持专家评分
   - 支持手动录入 business_metrics
   - 根据 expert_score 和 CTR 调整 rule baseWeight
   - 写入 rule_weight_history
15. 增加 seed demo：
   - 导入儿童桌垫 6 个 MD 文件
   - 抽取 mock RuleSpec
   - 审核部分规则
   - 构建 children_desk_mat_rulepack_v1
   - 模拟一个儿童桌垫商品上下文
   - 编译 6 个 StrategyCandidate
   - 生成 CreativeBrief 和 PromptSpec
16. 增加测试：
   - test_rule_extractor.py
   - test_rulepack_builder.py
   - test_context_compiler.py
   - test_strategy_compiler.py
   - test_brief_compiler.py
   - test_prompt_compiler.py
   - test_feedback_engine.py

优先保证端到端链路跑通，前端可以先做轻量版本。不要引入复杂知识图谱，不要训练模型，不要一次接入多个生图服务。第一版以儿童学习桌垫 / 淘宝主图为唯一验收场景。
```

---

# 十七、第一版产品验收 Demo 脚本

你可以要求研发最后演示这条链路：

```text
1. 上传 6 个儿童桌垫 MD 文件
2. 系统抽取 100 条左右 RuleSpec 候选
3. 专家审核通过 50 条
4. 构建 children_desk_mat_rulepack_v1
5. 从内容策划工作台选择一个儿童桌垫 OpportunityCard
6. 点击「生成视觉策略」
7. 系统生成 6 个 StrategyCandidate
8. 选择「安全护眼型」
9. 进入 CreativeBrief 编辑页
10. 修改卖点：强化“一擦即净”
11. 进入视觉工作台
12. 生成 4 张主图
13. 专家给其中 1 张评分 8.5
14. 手动录入 CTR 数据
15. 系统自动提高相关 RuleSpec 权重
16. Rule Review Console 显示权重变化
```

---

# 十八、最小闭环定义

第一版成功不以“图最好看”为唯一标准，而是看这条链路是否跑通：

```text
专家 MD
  ↓
可审核规则
  ↓
可复用 RulePack
  ↓
可解释策略候选
  ↓
可编辑 CreativeBrief
  ↓
可生图 Prompt
  ↓
可评分 ImageVariant
  ↓
可回流 Rule Weight
```

这条链路跑通后，你的内容策划工作台就从：

```text
内容机会发现 + Prompt 生图
```

升级为：

```text
内容机会发现 + 专家规则编译 + 视觉策略生成 + 交互式生图 + 数据回流自进化
```
