
**现在的系统更像“多源 prompt 拼接器”，还不是“可学习的视觉决策编译器”。**

所以更优方案，不建议继续围绕弹窗、小修 prompt 字段、再补几个标签去做，而要整体升级成一套：

# 生图策划优化 V2

## 从 Prompt Inspector 升级为「视觉决策编译器 + 可学习的生成工作流」

我先抓最核心的判断。

---

## 一、先给结论：真正要补的不是 7 个散点，而是 4 个能力层


### 1. 缺“视觉语义层”

现在系统有文本 brief、有策略、有参考图 URL，但没有把原图、爆文图、品牌历史图**转成结构化视觉语义**。

也就是说：

* 你有图
* 你也有生成模型
* 但中间缺了一个 **Visual Understanding / Visual DSL 层**

这是最大短板。

---

### 2. 缺“结构化编辑层”

当前 Inspector 允许改 prompt，但用户改的是一坨自由文本，不是改“决策变量”。

真正该让用户编辑的是：

* 主体
* 场景
* 构图
* 风格
* 色调
* 文案叠字
* 禁忌元素
* 与原图的距离
* 商业目标偏向

不是一个大 textarea。

---

### 3. 缺“评估与反馈层”

现在生成完只是“看图”，没有形成：

* 生成前预判
* 生成后对齐评估
* 用户偏好回写
* 品牌级偏好累积

所以系统无法知道：

* 为什么这次变好了
* 这次好是因为构图、风格、色调还是主体关系
* 下次该默认偏向什么

---

### 4. 缺“品牌学习层”

你已经有 prompt_log，但还没把它升级为真正的：

* 用户视觉偏好画像
* 品牌视觉偏好画像
* campaign 级视觉策略模板
* 高分图的 prompt pattern 库

这决定了系统会不会越用越懂品牌。

---

# 二、我建议的总体升级思路

不要把终点定义成“更好的 Prompt Inspector”。

应该把终点定义成：

## 一个 5 段式视觉生成闭环

### 1）视觉理解

把原始笔记图、参考图、历史高分图转成结构化视觉描述

### 2）视觉编译

把 brief / strategy / opportunity / visual evidence / brand preference 编译成结构化 image spec

### 3）可控编辑

用户不是改全文 prompt，而是改 image spec 的字段

### 4）生成与比较

按 spec 生成多个变体，并与原图/目标风格做对比

### 5）反馈学习

把“用户改了什么、选了什么、满意什么”回流成品牌视觉偏好

---

# 三、最优架构：从 Prompt 拼接改成“双层表示”

这是最关键的一步。

## 现状

你现在大概率是：

* 多源字段融合
* 产出 final_prompt
* 用户编辑 final_prompt
* 发给模型

这会导致：

* 逻辑不可解释
* 难以复用
* 难以比较
* 难以学习

---

## 建议改成双层结构

### 第一层：结构化视觉规格 ImageSpec

这是内部真相层。

示例字段建议：

```json
{
  "goal": {
    "image_role": "cover|body|comparison|detail",
    "business_intent": "种草|建立信任|展示质感|突出差异点|制造点击欲"
  },
  "subject": {
    "main_subject": "",
    "secondary_subjects": [],
    "product_visibility": "high|medium|low",
    "human_presence": "none|implicit|explicit"
  },
  "scene": {
    "target_scene": "",
    "usage_context": "",
    "time_of_day": "",
    "environment_style": ""
  },
  "composition": {
    "shot_type": "close-up|mid|wide|top-down",
    "layout": "",
    "focus_point": "",
    "depth": "",
    "camera_angle": ""
  },
  "style": {
    "visual_style": [],
    "tone": [],
    "color_palette": [],
    "texture_keywords": [],
    "reference_distance": "tight|medium|loose"
  },
  "text_overlay": {
    "enabled": true,
    "headline": "",
    "subline": "",
    "placement": "",
    "style_hint": ""
  },
  "constraints": {
    "must_include": [],
    "avoid": [],
    "brand_safety": [],
    "platform_safety": []
  },
  "adaptation": {
    "aspect_ratio": "3:4",
    "platform": "xiaohongshu",
    "slot_type": "cover"
  },
  "evidence": {
    "source_note_visual_summary": "",
    "high_performing_visual_patterns": [],
    "brand_preference_patterns": []
  }
}
```

---

### 第二层：ModelPrompt

这是给具体模型的执行层。

由 `ImageSpec -> prompt renderer` 转换生成：

* 通义版 prompt
* Gemini 版 prompt
* 参考图版 prompt
* 纯文生图版 prompt

这样做的价值非常大：

#### 好处 1：编辑对象稳定

用户改的是 spec 字段，不是整段 prompt

#### 好处 2：模型切换更容易

底层 spec 不变，只换 renderer

#### 好处 3：更容易做学习

你可以比较“高分图对应什么 spec”，而不是只看一长串 prompt 文本

#### 好处 4：可解释

可以清楚告诉用户：
“这张图的生成逻辑由主体/风格/构图/叠字/限制项组成”

---

# 四、补齐最关键的新模块：Visual Evidence Layer

这是我认为你当前最应该优先做的升级。

你现在最浪费的资产是：

* 原始笔记图
* 爆文图
* 参考图
* 历史生成图

这些图只被当成 URL，不被当成“可计算证据”。

---

## 新增模块 1：视觉抽取器 Visual Extractor

对原始笔记封面、参考图、爆文图做 VLM 分析，提取：

### A. 基础视觉属性

* 画面主体
* 构图方式
* 镜头距离
* 前景/背景关系
* 色调
* 光感
* 情绪氛围
* 材质感
* 是否有人物
* 商品出镜方式

### B. 平台表达属性

* 是否像小红书
* 是否更像广告图
* 是否有生活感
* 是否有“可点击封面感”
* 是否具备封面文案承载空间

### C. 商业表达属性

* 卖点显著度
* 产品辨识度
* 使用场景清晰度
* 信任感
* 对比感
* 记忆点

---

## 新增模块 2：视觉模式归纳器 Visual Pattern Miner

基于高互动笔记图，抽取“视觉共性”：

例如输出：

* 封面更偏近景特写
* 暖白自然光更高频
* 人手持/桌面摆拍优于纯产品白底
* 文案叠字通常落左上
* 色彩对比不过强，偏奶油灰粉
* 第一眼焦点集中在产品轮廓而非背景装饰

这些不是直接给用户看，而是进入 `evidence.high_performing_visual_patterns`。

这比“参考爆文”强得多，因为它是**提炼后的规律**。

---

# 五、交互层不要再做“Prompt Inspector”，而要做“Visual Builder”

## 当前问题

你现在的弹窗是“给懂 prompt 的人用的”。

但你真正的用户想改的是：

* 这图太像广告了
* 不够像真实生活
* 场景太空
* 商品不够突出
* 配色太冷
* 看不出高级感
* 不像我们品牌

所以 UI 应该围绕“视觉决策变量”设计，而不是 prompt 文本。

---

## 推荐 UI 结构

### 左侧：来源与证据

* 原始笔记大图
* 参考图
* 爆文视觉模式摘要
* 当前 brief/strategy 摘要
* 品牌偏好提示

### 中间：Visual Builder

按模块编辑：

#### 1. 主体

* 主体是什么
* 商品露出程度
* 是否需要人物
* 人物与商品关系

#### 2. 场景

* 什么场景
* 场景真实度
* 氛围关键词
* 时间感

#### 3. 构图

* 近景/中景/远景
* 俯拍/平拍/特写
* 留白程度
* 文案位置预留

#### 4. 风格

* 生活感 / 高级感 / 杂志感 / 原生感
* 色调
* 光线
* 材质感

#### 5. 叠字

* 是否叠字
* 主标题
* 副标题
* 字体感觉
* 位置

#### 6. 规避项

* 不要太广告
* 不要过度 AI 感
* 不要廉价道具
* 不要过饱和
* 不要复杂背景

---

### 右侧：结果区

* 当前 prompt 预览
* 生成图
* 原图 vs 生成图对比
* 多变体对比
* 历史版本

---

## 文本 prompt 怎么办？

不要取消，但把它降级成：

* 高级模式
* 可展开
* 面向专业用户

默认让普通用户编辑结构化字段。

---

# 六、引入“多目标生图”，不要只追求“更像原图”

你现在的系统默认目标，可能隐含是：

* 参考原图
* 符合 brief
* 生出来能看

但小红书生图真正至少有 4 个目标：

### 1. Brief 对齐

符合策划意图

### 2. 平台适配

像小红书，不像广告 banner

### 3. 商业表达

卖点清楚，能服务点击和种草

### 4. 品牌一致性

不像其他牌子

所以建议在生成前就显式让用户选生成目标偏向：

* 更像原始爆文风格
* 更符合品牌气质
* 更突出商品卖点
* 更适合封面点击
* 更生活化真实
* 更高级质感

这个选择会直接影响 `ImageSpec.goal.business_intent` 和 renderer。

否则所有图都在一个模糊目标下生成，效果会不稳定。

---

# 七、评估层要补成“生成前 + 生成后”双评估

## 1. 生成前预评估

在点击生成前，给一个 Spec Readiness Score，不只是 prompt 质量分。

分成 5 项更有用：

* 主体清晰度
* 场景完整度
* 风格一致性
* 约束充分度
* 平台适配度

并告诉用户缺什么：

* 缺少明确构图
* 缺少场景约束
* 缺少规避项
* 封面未设置叠字预留
* 当前比例不适合封面

这比一个总分更能指导修改。

---

## 2. 生成后自动评估

生成图出来后，做图像评估：

* 与 brief 一致性
* 商品突出度
* 小红书原生感
* 商业点击感
* 风格稳定性
* 与参考图距离

再叠加用户反馈：

* 满意
* 可用但需改
* 不满意

这样你就有了可训练的 reward signal。

---

## 3. diff 解释

用户每次编辑后，系统给出一句解释：

* 你增强了场景描述，画面可能更有生活感
* 你增加了“避免广告感”，会降低硬广风格
* 你提升了商品露出优先级，商品识别度可能更强
* 你缩小了参考距离，生成图可能更贴近原图风格

这会显著提升用户控制感。

---

# 八、真正的复用机制，不是“保存 prompt”，而是保存 3 类资产

不要只做 saved_image_prompts。

建议拆成 3 层：

## 1. Prompt Snapshot

一次性快照，复现某次生成

适合：

* 历史追溯
* 结果回放
* 多轮对比

---

## 2. Visual Template

抽象成可复用模板

例如：

* 小红书封面-产品特写-生活感模板
* 对比型封面模板
* 情绪氛围型封面模板
* 手持使用场景模板

适合跨 opportunity 复用。

---

## 3. Brand Visual Preference Profile

品牌级长期偏好画像

例如：

* 更偏暖灰奶油色
* 商品露出要高
* 避免过度棚拍
* 喜欢有轻微生活杂乱感
* 封面偏近景，不偏远景
* 叠字通常保留左上留白

这才是最值钱的资产。

---

# 九、自进化建议：先别急着上复杂模型，先做规则学习 + 偏好聚合

你提到长期训练信号，这方向对，但不建议第一阶段就做复杂学习器。

## Phase 1：规则型自进化

从历史 `user_edited=True` 中提取：

* 总是新增什么
* 总是删掉什么
* 总是偏好什么风格
* 哪些字段经常被覆盖

形成品牌级 patch 规则：

例如：

* 默认加“自然生活光感”
* 默认避免“过度广告感”
* 默认提升“商品主体突出度”
* 默认启用左上叠字空间

这是最快见效的。

---

## Phase 2：偏好统计模型

按 brand / campaign / slot_type 聚合高满意样本，统计：

* 哪些 style tag 更常出现
* 哪些 scene/composition 更高分
* 哪类 negative 更有帮助
* 哪类参考距离更稳定

用于调整融合权重。

---

## Phase 3：学习型 Prompt Optimizer

再上一个 LLM / reranker / policy 模块，输入：

* ImageSpec
* 参考图视觉摘要
* 品牌偏好画像
* 历史高分样本

输出：

* 优化后的 spec
* 或多候选 spec 排序

这样才稳。

---

# 十、关于“借鉴 GitHub 高 star skill”，我的建议是：借鉴框架，不要依赖社区 prompt 套话

这个点很容易走偏。

## 可以借鉴的，不是现成文案，而是 3 类能力

### 1. 结构化 prompt 模板能力

把散乱需求压成稳定模板

### 2. Prompt 迭代策略能力

如何从弱 prompt 变成强 prompt

### 3. 自检 checklist 能力

生成前检查缺项，生成后解释问题

---

## 不建议过度依赖的

* Midjourney 社区那种冗长风格词堆叠
* 通用“电影感、史诗感、高级感”类空泛词库
* 脱离你业务目标的 prompt 炫技

因为你不是做艺术图，而是做：
**服务小红书内容效果的商业图。**

所以 skill 更适合沉淀为你自己的：

* 小红书封面图 skill
* 生活感商品图 skill
* 卖点对比图 skill
* 场景种草图 skill
* 文案留白图 skill

每个 skill 对应：

* 适用场景
* spec 结构
* renderer 模板
* 负向规则
* 评估标准

---

# 十一、我给你的最优实施优先级

如果只抓 ROI，建议按这个顺序做。

## P0：先做结构升级

### 1. 引入 `ImageSpec`

把 prompt 文本变成结构化规格
这是整个系统的地基。

### 2. 把 `style_tags / text_overlay / target_user / target_scene / aspect_ratio` 真正接入编译链

这些是低成本高收益项。

### 3. Prompt Inspector 改成 Visual Builder

先做半结构化都行，不必一步到位。

---

## P1：补视觉理解

### 4. 增加原图/参考图的 VLM 视觉摘要

这会立刻提升参考图模式下的效果稳定性。

### 5. 增加高互动图视觉共性提炼

让系统学会“为什么它像小红书爆图”。

---

## P2：补评估闭环

### 6. 做生成前 readiness score

### 7. 做生成后 brief alignment score + 用户满意度

### 8. 接通原图 vs 生成图并排对比

---

## P3：补品牌学习

### 9. 把历史编辑行为沉淀成 brand preference profile

### 10. 做可复用 Visual Template 库

---

# 十二、你可以直接采用的一版产品定义

我建议你把这一块产品重新命名为：

## Visual Strategy Studio

而不是 Prompt Inspector

它的核心对象不是 prompt，而是：

* `VisualEvidence`
* `ImageSpec`
* `GenerationVariant`
* `BrandVisualPreference`
* `VisualTemplate`
* `GenerationFeedback`

这会让你的系统从“生成工具”升级成“视觉策略资产工作台”。

---

# 十三、最后给你一句最核心的产品判断

你现在离更强，只差一件事：

## 把“prompt”从最终产物，降级成“编译结果”。

真正的核心资产应该是：

* 视觉证据
* 结构化视觉规格
* 品牌视觉偏好
* 生成评估与反馈

这样你做出来的就不是一个生图弹窗，而是一个**会学习的品牌视觉生成系统**。
