# 桌布主图策略模板库提取

---

# 一、标签体系


## L1. 任务标签：这张首图/这组图在完成什么任务

### 首图任务标签

* `hook_click`：强停留、强点击
* `scene_seed`：场景种草
* `style_anchor`：风格定锚
* `texture_detail`：材质/工艺/细节打动
* `feature_explain`：卖点解释
* `price_value`：平价替代/性价比
* `gift_event`：节庆/礼赠/纪念
* `set_combo`：桌搭方案/套装组合
* `before_after`：改造前后对比
* `shopping_guide`：尺寸/选购/避坑指导

### 图组任务标签

* `cover_hook`：封面负责点击
* `style_expand`：补风格和整体搭配
* `texture_expand`：补材质细节
* `usage_expand`：补场景使用
* `guide_expand`：补选购建议/购买引导

---

## L2. 视觉结构标签：它是怎么完成任务的

这一层是给模型做聚类和模板归纳的关键。

### 镜头与构图

* `shot_topdown`：俯拍
* `shot_angled`：斜侧拍
* `shot_closeup`：近景特写
* `shot_wide_scene`：完整桌面/空间全景
* `composition_centered`
* `composition_diagonal`
* `composition_layered`
* `composition_dense`
* `composition_minimal`

### 主体与陪体

* `has_tablecloth_main`
* `has_tableware`
* `has_food`
* `has_flower_vase`
* `has_candle`
* `has_hand_only`
* `has_people`
* `has_chair_or_room_bg`
* `has_gift_box`
* `has_festival_props`

### 商品露出方式

* `cloth_full_spread`
* `cloth_partial_visible`
* `cloth_texture_emphasis`
* `cloth_pattern_emphasis`
* `cloth_edge_emphasis`
* `cloth_with_other_products`

### 文案覆盖

* `text_none`
* `text_light`
* `text_medium`
* `text_heavy`
* `text_style_label`
* `text_price_label`
* `text_transformation_claim`
* `text_scene_claim`

### 色彩与氛围

* `palette_warm`
* `palette_cool`
* `palette_neutral`
* `palette_cream`
* `palette_french_vintage`
* `palette_mori`
* `palette_festival_red_green`
* `lighting_soft`
* `lighting_natural`
* `lighting_dramatic`

---

## L3. 经营语义标签：它在卖什么命题

这一层决定后面模板命名。

* `mood_daily_healing`：日常治愈
* `mood_refined_life`：精致生活
* `mood_brunch_afternoontea`：早餐/下午茶仪式感
* `mood_friends_gathering`：朋友聚餐
* `mood_festival_setup`：节庆布置
* `mood_anniversary`：纪念日/生日
* `mood_low_cost_upgrade`：低成本改造
* `mood_small_space_upgrade`：小户型提气质
* `mood_photo_friendly`：出片感
* `mood_style_identity`：风格身份认同
* `mood_giftable`：适合作礼物
* `mood_practical_value`：耐脏/易打理/实用

---

## L4. 风险与边界标签：避免聚类后模板不可用

这一层对后续生成很重要。

* `risk_too_generic`
* `risk_no_product_focus`
* `risk_overstyled_low_sellability`
* `risk_text_too_ad_like`
* `risk_scene_not_reproducible`
* `risk_holiday_only`
* `risk_style_too_niche`
* `risk_cloth_not_visible_enough`

---

## 建议的人审标签格式

每条笔记至少产出：

* `cover_task_labels`
* `visual_structure_labels`
* `business_semantic_labels`
* `risk_labels`
* `confidence_score`
* `evidence_notes`

---

# 二、聚类字段设计

聚类不要只用图像 embedding。用 **多视角特征拼接**：

## A. 图像特征字段

用于理解视觉原型。

### 基础视觉特征

* `img_embedding_cover`
* `img_embedding_top3_mean`
* `dominant_color_vector`
* `brightness_score`
* `contrast_score`
* `text_area_ratio`
* `object_count_estimate`
* `tablecloth_area_ratio`
* `food_area_ratio`
* `tableware_area_ratio`
* `festival_prop_ratio`

### 结构特征

* `is_topdown`
* `is_closeup`
* `is_full_table_scene`
* `is_room_context`
* `is_texture_focused`
* `is_style_focused`

---

## B. 文本特征字段

用于理解标题钩子与表达命题。

### 标题/文案 embedding

* `title_embedding`
* `title_keyword_vector`
* `body_intro_embedding`

### 规则关键词

* 是否包含：

  * “桌布”
  * “桌搭”
  * “氛围感”
  * “法式”
  * “奶油风”
  * “改造”
  * “租房”
  * “平价”
  * “生日”
  * “圣诞”
  * “聚餐”
  * “出片”
  * “高级感”
  * “百元内”

对应字段：

* `kw_style`
* `kw_scene`
* `kw_price`
* `kw_event`
* `kw_upgrade`
* `kw_gift`
* `kw_aesthetic`

---

## C. 标签特征字段

这是最有业务解释性的部分。

### One-hot 或 multi-hot

* `task_label_vector`
* `visual_label_vector`
* `semantic_label_vector`
* `risk_label_vector`

---

## D. 图组结构字段

非常关键。模板本质上常常是“图组骨架”。

### 图组长度和顺序

* `image_count`
* `cover_role`
* `role_seq_top5`

例如：

* `hook_click -> style_expand -> texture_expand -> usage_expand -> guide_expand`

### 图组一致性

* `style_consistency_score`
* `color_consistency_score`
* `scene_consistency_score`
* `text_density_variance`

### 图组功能覆盖

* `has_scene_image`
* `has_texture_closeup`
* `has_buying_guide`
* `has_before_after`
* `has_set_combo`

---

## E. 互动和表现字段

这部分不直接决定模板，但用于后验排序。

* `like_count`
* `save_count`
* `comment_count`
* `engagement_proxy_score`
* `save_like_ratio`
* `comment_like_ratio`

建议重点看：

* `save_like_ratio`
  因为桌布/桌搭内容通常收藏价值更高，适合做模板提取。

---

## 聚类建议：两段式

### 第一步：封面原型聚类

输入：

* `img_embedding_cover`
* `title_embedding`
* `task_label_vector`
* `visual_label_vector`
* `semantic_label_vector`

目标：
先得到 10–20 个首图原型簇。

### 第二步：图组策略聚类

输入：

* `role_seq_top5`
* `style_consistency_score`
* `has_scene_image`
* `has_texture_closeup`
* `has_buying_guide`
* `semantic_label_vector`
* `engagement_proxy_score`

目标：
收敛为 6–8 套策略模板。

---

# 三、模板 Schema

最终模板不要只存名字。
建议存成一个可直接被 Visual Agent 消费的对象。

## `TableclothMainImageStrategyTemplate`

```json
{
  "template_id": "xhs_tablecloth_tpl_001",
  "template_name": "氛围感场景种草型",
  "template_version": "v1",
  "template_goal": "通过完整桌面场景和生活方式氛围提升点击与收藏",
  "fit_platform": ["xiaohongshu"],
  "fit_category": ["桌布", "餐桌布", "桌搭"],
  "fit_scenarios": ["早餐", "下午茶", "居家晚餐", "朋友聚餐"],
  "fit_styles": ["奶油风", "法式", "北欧", "中古"],
  "fit_price_band": ["中低", "中"],
  "core_user_motive": [
    "想要提升家居氛围",
    "想低成本改造餐桌",
    "想做出片桌搭"
  ],
  "hook_mechanism": [
    "一眼看到完整桌面效果",
    "风格与氛围统一",
    "让用户代入理想生活方式"
  ],
  "cover_role": "hook_click",
  "image_sequence_pattern": [
    "cover_hook_scene",
    "style_expand",
    "texture_expand",
    "usage_expand",
    "buying_guide"
  ],
  "visual_rules": {
    "preferred_shots": ["topdown", "wide_scene"],
    "required_elements": ["tablecloth", "tableware"],
    "optional_elements": ["flowers", "food", "candles"],
    "text_overlay_level": "light",
    "color_direction": ["warm", "cream", "soft"],
    "lighting_direction": ["natural", "soft"]
  },
  "copy_rules": {
    "title_style": [
      "氛围感导向",
      "风格标签导向",
      "低成本改造导向"
    ],
    "cover_copy_style": "short",
    "recommended_phrases": [
      "一块桌布把餐桌气质拉满",
      "周末在家也能有小仪式感",
      "低成本拥有法式餐桌氛围"
    ],
    "avoid_phrases": [
      "全网最低",
      "强促销词",
      "纯参数堆砌"
    ]
  },
  "scene_rules": {
    "must_have_scene": true,
    "scene_types": ["居家餐桌", "早餐角", "周末下午茶"],
    "avoid_scenes": ["过度商业棚拍", "背景过杂"]
  },
  "product_visibility_rules": {
    "tablecloth_visibility_min": 0.35,
    "must_show_pattern_or_texture": true,
    "avoid_over_occlusion": true
  },
  "risk_rules": [
    "避免桌布被食物和道具遮挡过多",
    "避免画面只有氛围没有商品识别",
    "避免过重文案影响平台感"
  ],
  "best_for": [
    "高收藏内容",
    "风格型桌布",
    "希望走种草路线的商品"
  ],
  "avoid_when": [
    "核心卖点是防水防油等功能且需强解释",
    "需要突出超低价心智",
    "节庆场景过强但非节点期"
  ],
  "seed_examples": [],
  "cluster_features": {
    "dominant_task_labels": ["scene_seed", "style_anchor"],
    "dominant_visual_labels": ["shot_topdown", "cloth_full_spread"],
    "dominant_semantic_labels": ["mood_refined_life", "mood_photo_friendly"]
  },
  "evaluation_metrics": {
    "target_save_like_ratio": 0.35,
    "target_click_proxy_score": 0.7,
    "scene_visibility_score_min": 0.6
  },
  "derivation_rules": {
    "can_extend_to": ["title", "detail_page", "short_video_outline"],
    "prompt_style": "scene-first"
  }
}
```

---

## 推荐先沉淀的 6 套模板字段值

### 1. 氛围感场景种草型

核心：

* 场景先行
* 完整桌面
* 高收藏

### 2. 风格定锚型

核心：

* 法式/奶油/中古等风格标签
* 空间气质认同

### 3. 质感细节打动型

核心：

* 纹理、刺绣、垂坠、边缘工艺
* 更适合中高客单

### 4. 平价改造型

核心：

* 低成本焕新
* 文案强一点
* 前后对比可选

### 5. 节庆礼赠型

核心：

* 节日聚餐、纪念日晚餐、生日桌搭
* 节点性强

### 6. 桌搭方案型

核心：

* 桌布 + 餐具 + 花器 + 蜡烛
* 更像“整套作业”

---

# 四、Prompt 清单


---

## Prompt 1：定义桌布主图模板提取的数据模型

```text
你是一个资深多模态数据产品工程师，请为“小红书桌布主图策略模板库提取”项目设计一套可扩展的数据模型与目录结构。

项目目标：
1. 从小红书桌布/桌搭相关笔记中提取封面与图组策略特征；
2. 构建标签体系、聚类特征与模板库；
3. 最终沉淀 6-8 套可被 Visual Agent 消费的主图策略模板。

请输出：
A. 项目目录结构（Python）
B. 核心数据类 / Pydantic schema
C. 原始样本、标注样本、特征样本、聚类结果、模板结果的 schema
D. 推荐的字段命名规范
E. 一份 mock JSON 示例

必须包含这些对象：
- XHSNoteRaw
- XHSNoteLabeled
- CoverFeaturePack
- GalleryFeaturePack
- ClusterSample
- TableclothMainImageStrategyTemplate

注意：
- 标签体系要支持多标签
- 图组结构要支持 role sequence
- 后续模板要能直接供主图策划 Agent 使用
- 代码风格要工程化，便于后续接 VLM 和向量检索
```

---

## Prompt 2：实现标签体系与弱监督标注器

```text
请基于“小红书桌布主图策略模板库提取”项目，实现一套可运行的标签体系与弱监督标注器。

任务：
1. 定义四层标签：
   - L1 任务标签
   - L2 视觉结构标签
   - L3 经营语义标签
   - L4 风险标签
2. 为每个标签编写：
   - 定义
   - 触发条件
   - 反例
3. 实现一个弱监督标注器：
   - 输入：单条笔记（封面图路径、前5图路径、标题、正文）
   - 输出：标签结果 + 置信度 + 证据说明
4. 标注器先支持两种模式：
   - rule-based
   - vlm-assisted（先预留接口，mock返回）

要求：
- 用 Python 实现
- 输出为结构化 JSON
- 每个标签要能解释为什么打上
- 预留后续人工校正字段 human_override
- 给出 10 条桌布场景测试样例
```

---

## Prompt 3：实现桌布封面与图组特征提取器

```text
请实现“小红书桌布主图策略模板库提取”的特征提取模块。

目标：
把每条笔记转成可聚类的多视角特征。

输入：
- 封面图
- 前5张图
- 标题
- 正文前200字
- 互动数据

输出：
- CoverFeaturePack
- GalleryFeaturePack

需要提取的字段：
1. 图像特征
   - 图像 embedding（接口预留）
   - 主色调
   - 亮度
   - 对比度
   - 文本面积占比
   - 桌布主体面积估计
   - 食物/花器/餐具/节庆元素出现与否
2. 文本特征
   - 标题 embedding（接口预留）
   - 风格词/场景词/价格词/节庆词等规则命中
3. 标签特征
   - 多标签 multi-hot
4. 图组特征
   - 图组长度
   - 角色序列
   - 风格一致性
   - 色彩一致性
   - 是否包含场景图/特写图/指南图

要求：
- Python
- 模块化设计
- 图像 embedding 与 OCR 部分先留接口
- 输出支持 parquet / jsonl
- 给出 feature extraction pipeline 的主入口
```

---

## Prompt 4：实现两阶段聚类流程

```text
请为“小红书桌布主图策略模板库提取”实现两阶段聚类流程。

阶段一：封面原型聚类
输入：
- cover image embedding
- 标题 embedding
- 任务标签向量
- 视觉结构标签向量
- 经营语义标签向量
输出：
- cover_cluster_id
- cluster_summary
- representative_samples

阶段二：图组策略聚类
输入：
- role sequence
- 图组一致性特征
- 语义标签向量
- 互动代理分数
输出：
- strategy_cluster_id
- cluster_pattern
- template_candidate_summary

要求：
1. 支持 UMAP + HDBSCAN 或 KMeans + 人工挑选版本
2. 输出每个 cluster 的：
   - 样本数
   - 高频标签
   - 高频标题关键词
   - 代表样本
3. 输出一份 markdown 报告，便于人工命名模板
4. 将最终结果映射到 6 套桌布主图模板候选：
   - 氛围感场景种草型
   - 风格定锚型
   - 质感细节打动型
   - 平价改造型
   - 节庆礼赠型
   - 桌搭方案型

请特别考虑：
- 不要让纯风格差异掩盖任务差异
- 图组策略优先于单图风格
```

---

## Prompt 5：把聚类结果编译成模板库

```text
请实现一个“模板编译器”，把桌布主图聚类结果编译成结构化模板库。

输入：
- strategy clusters
- 代表样本
- 高频标签
- 高频标题词
- 人工命名结果

输出：
- TableclothMainImageStrategyTemplate JSON
- templates/index.json
- templates/*.json
- 一份模板说明 markdown

每个模板必须包含：
- template_id
- template_name
- template_goal
- fit_scenarios
- fit_styles
- core_user_motive
- hook_mechanism
- image_sequence_pattern
- visual_rules
- copy_rules
- scene_rules
- product_visibility_rules
- risk_rules
- best_for
- avoid_when
- cluster_features
- evaluation_metrics
- derivation_rules

要求：
- 输出结果可直接供 Visual Agent 调用
- 为每套模板自动生成一段“适用场景说明”
- 为每套模板自动生成一段“不要这样用”的说明
- 给出 6 套桌布模板的 mock 结果
```

---

## Prompt 6：生成面向主图策划 Agent 的模板消费接口

```text
请基于桌布主图模板库，设计一个可供主图策划 Agent 使用的模板消费接口。

目标：
后续在“机会卡 -> 策划编译 -> 视觉共创 -> 资产生产”链路中，主图策划 Agent 可以读取桌布模板并生成5张主图方案。

请输出：
1. TemplateRetriever 接口
2. TemplateMatcher 接口
3. MainImagePlanCompiler 接口
4. 示例输入：
   - 机会卡
   - 商品brief
   - 小红书笔记视觉/场景/卖点/主题提取结果
5. 示例输出：
   - 5张主图策划方案

要求：
- 要体现模板匹配逻辑
- 支持返回 top3 模板候选
- 支持用户指定偏“种草 / 转化 / 礼赠 / 平价改造”
- 输出 JSON schema + Python 伪代码
```

---

## Prompt 7：生成标注指南文档

```text
请为“小红书桌布主图策略模板库提取”项目编写一份标注指南。

内容包括：
1. 标注目标
2. 标注对象定义（封面、前5图、标题、正文）
3. 四层标签的定义、例子、反例
4. 常见冲突标签如何处理
5. 什么情况下允许多标签
6. 什么情况下标注“不确定”
7. 10条桌布案例的标准答案示例

风格要求：
- 偏内部团队操作手册
- 可直接给标注员使用
- 语言简洁，但定义严格
```

---

## Prompt 8：生成评估与验收脚本

```text
请为“小红书桌布主图策略模板库提取”项目设计评估与验收脚本。

需要评估：
1. 标签质量
   - 人工一致性
   - 弱监督 vs 人工校正一致率
2. 聚类质量
   - cluster purity
   - cluster interpretability
   - high-engagement coverage
3. 模板质量
   - 模板是否可命名
   - 模板是否具备可执行性
   - 模板之间是否有明显边界
4. 实用性
   - 能否支撑后续主图策划 Agent

请输出：
- 指标定义
- Python 评估脚本结构
- markdown 验收报告模板
```

---

# 五、补一版你可以直接内部使用的 6 套模板名称

建议先沉淀成这 6 套，最稳：

1. **氛围感场景种草型**
2. **风格定锚型**
3. **质感细节打动型**
4. **平价改造型**
5. **节庆礼赠型**
6. **桌搭方案型**

如果后面数据量足够，再扩成 8 套，把下面两类单独拆出来：

7. **卖点解释型**
8. **前后改造对比型**

---

# 六、落地顺序建议

先做这 4 步：

### Step 1

先搭样本结构和标签体系。
不要急着聚类。

### Step 2

先标 300–500 条桌布笔记。
把四层标签打稳定。

### Step 3

再做封面聚类 + 图组聚类。
先出 6 套 v1 模板。

### Step 4

最后再接到你的 Visual Agent。
让它能根据机会卡匹配模板并生成 5 张主图策划方案。
