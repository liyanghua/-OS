
# 《视觉策划层右侧 Creative Inspector PRD v1》

**含 Lite / Pro / Expert 三种模式 + 开源参考融合方式 + Skill Map 与产品架构整合方案**

这版文档不是只写 UI，而是把三件事一起讲清楚：

1. **右侧 Creative Inspector 本身怎么设计**
2. **如何吸收开源项目的长处，而不是直接拼凑功能**
3. **如何把视觉精修 Skill Map 放进整体产品架构里**

我会默认它挂在你们的 **Creation Workspace** 右侧，服务对象是 `NewNotePlan / MainImagePlan / ImageSlotPlan / TitleCandidateSet / BodyOutline` 等对象化内容。你前面的视觉架构升级文档已经明确提出：不要再把系统中心放在 prompt，而应升级为“视觉决策编译器 + 可学习的生成工作流”，用 `ImageSpec` 作为内部真相层，prompt 降级为执行层的编译结果。

同时，这版 PRD 参考的开源方向主要包括：

* **ComfyUI**：节点化图像工作流与可组合执行图。([GitHub][1])
* **InvokeAI**：Unified Canvas + workflows + gallery 的统一创作界面思路。([GitHub][2])
* **Jaaz**：prompt-free、多模态 canvas creative assistant 的对象直操交互。([GitHub][3])
* **ComfyUI-PolotnoCanvasEditor**：生成工作流与画布编辑器集成。([GitHub][4])
* **Hermes-Agent**：memory / skills / learning loop 的 Agent 基座。([GitHub][5])
* **DeerFlow**：subagents / memory / sandboxes / workflow orchestration 的执行层。([GitHub][6])
* **awesome-agent-skills**：Skill 作为独立目录与文档资产的组织方式。([GitHub][7])

---

# 一、产品定位

## 1.1 组件名称

**Creative Inspector**

## 1.2 组件定位

它不是一个 “Prompt Builder 2.0”，而是：

## **对象化视觉决策控制器**

围绕当前被选中的内容对象，提供：

* 方向控制
* 结构化视觉编辑
* 高级执行层控制
* AI 建议与一键应用
* 局部重生成
* 模板与品牌偏好沉淀

## 1.3 在产品中的角色

Creative Inspector 是 **Creation Workspace** 右侧的核心 AI 原生控制面板，负责把：

* `Opportunity / Brief / Strategy / Plan`
  下发到：
* `ImageSpec / ImageExecutionBrief / VisualTemplate / BrandPreferencePatch`

它是从策划对象到执行对象的桥梁。

---

# 二、要解决的核心问题

## 2.1 当前问题

你现在右侧只有 `prompt builder`，会遇到 4 个核心问题：

### 问题 1：普通用户不会改 prompt

他们想表达的是：

* 更像小红书
* 不要太广告
* 商品再突出一点
* 更有生活感
  而不是改一长段 prompt。

### 问题 2：高端用户觉得控制不够

资深策划 / 设计负责人会希望控制：

* 场景真实度
* 构图与镜头
* 文案留白
* 商品与人物关系
* 参考距离
* 规避项与品牌 patch

### 问题 3：交互一旦暴露太多，会立刻失控

如果把所有视觉参数都堆在侧栏，业务用户会被吓退。

### 问题 4：prompt 不适合作为长期资产

真正应该沉淀的不是 prompt，而是：

* `ImageSpec`
* `VisualTemplate`
* `BrandVisualPreferenceProfile`
* 生成前后评估与反馈资产。

---

# 三、产品原则

## 原则 1：对象优先，不是 prompt 优先

右侧始终围绕当前选中对象展开，而不是给一个全局大 prompt 框。

## 原则 2：渐进披露

Lite 给方向，Pro 给结构，Expert 给执行层。

## 原则 3：结构化编辑优先

先改决策变量，再决定是否进入 prompt / JSON / renderer patch。

## 原则 4：建议必须带动作

AI 输出不只是一段分析，而是：

* insight
* diff
* action

## 原则 5：精修不是一次性操作，要可沉淀成 Skill / Template / Brand Preference

---

# 四、用户分层与模式设计

## 4.1 Lite 模式

### 目标用户

* 内容运营
* 商品运营
* 普通策划
* 客户侧轻度用户

### 用户诉求

* 快速调方向
* 不想学 prompt
* 希望“一键应用”和“少量关键控制”

### 设计目标

让用户用业务语言控制结果。

---

## 4.2 Pro 模式

### 目标用户

* 资深策划
* 视觉策略用户
* 设计负责人
* 高级运营

### 用户诉求

* 希望控制更多视觉变量
* 希望针对单个图位做精细调整
* 希望知道系统为什么这么生成

### 设计目标

让用户直接操作 `ImageSpec` 的结构化字段，但不暴露 JSON。

---

## 4.3 Expert 模式

### 目标用户

* Prompt 工程师
* 视觉策略专家
* 算法 / 模型实验同学

### 用户诉求

* 查看真实 spec
* 查看 renderer 输出
* 做 model-specific patch
* 做对比与调试

### 设计目标

提供透明执行层与调试层，但默认隐藏。

---

# 五、信息架构

## 5.1 顶部固定区（所有模式共用）

### 模块 A：对象头部

字段：

* `Object Type`：Plan / Title / Body / Image Slot / Reference
* `Object Name`：例如 `Image Slot 3`
* `Version`
* `Lock Status`
* `Source Lineage`：strategy / plan / template 来源

### 模块 B：状态摘要

显示：

* `Readiness`
* `Alignment`
* `Risk`

### 模块 C：快捷动作

按钮：

* `AI 建议`
* `比较版本`
* `锁定对象`
* `重生成`
* `应用建议`

---

## 5.2 中部主内容区

根据 Lite / Pro / Expert 三种模式切换内容。

---

## 5.3 底部固定操作区

### 主按钮

* `应用修改`
* `仅重生成当前对象`

### 次按钮

* `保存为 Visual Template`
* `保存到品牌偏好`
* `重置为系统建议`

---

# 六、Lite 模式 PRD

## 6.1 目标

让普通业务用户“用业务语言控制视觉结果”。

## 6.2 区块设计

### 区块 L1：生成目标

字段：

* `Primary Goal`

  * 更像参考图
  * 更符合品牌
  * 更适合封面点击
  * 更生活化真实
  * 更突出商品卖点
* `Business Intent`

  * 种草
  * 建立信任
  * 展示质感
  * 突出差异点
  * 制造点击欲
* `Platform Fit Priority`

  * 更广告
  * 更原生

### 区块 L2：风格方向

字段：

* `Visual Feel`

  * 生活感
  * 高级感
  * 原生感
  * 杂志感
  * 松弛感
* `Tone`

  * 暖
  * 冷
  * 柔和
  * 明亮
  * 克制
* `Reference Distance`

  * 紧贴参考
  * 中等借鉴
  * 自由发挥

### 区块 L3：场景与商品

字段：

* `Scene Direction`
* `Product Visibility`
* `Human Presence`

### 区块 L4：封面信息感

字段：

* `Text Overlay` 开关
* `Overlay Style`

  * 不叠字
  * 轻叠字
  * 标题优先
  * 留白优先
* `Clickability`

### 区块 L5：快速规避项

字段：

* 太广告
* 太棚拍
* 太 AI 感
* 背景过杂
* 过饱和
* 廉价道具
* 商品不突出

### 区块 L6：AI 建议卡

每条建议包括：

* 建议标题
* 建议解释
* 影响预测
* `一键应用`

## 6.3 核心动作

* `应用修改`
* `生成 3 个变体`
* `仅重生成当前对象`

## 6.4 成功标准

普通用户在不改 prompt 的情况下，也能明显改善结果。

---

# 七、Pro 模式 PRD

## 7.1 目标

给高端用户真正的“结构化对象控制”。

## 7.2 区块设计

### 区块 P1：Subject

字段：

* `Main Subject`
* `Secondary Subjects`
* `Product Visibility`
* `Human Presence`
* `Human-Product Relation`

### 区块 P2：Scene

字段：

* `Target Scene`
* `Usage Context`
* `Time of Day`
* `Environment Style`
* `Scene Realism`

### 区块 P3：Composition

字段：

* `Shot Type`
* `Camera Angle`
* `Focus Point`
* `Depth`
* `Whitespace`
* `Layout Density`
* `Text Safe Area`

### 区块 P4：Style

字段：

* `Visual Style`
* `Color Palette`
* `Lighting`
* `Texture Keywords`
* `Style Intensity`
* `Reference Distance`

### 区块 P5：Text Overlay

字段：

* `Enabled`
* `Headline`
* `Subline`
* `Placement`
* `Style Hint`
* `Reserved Space Strength`

### 区块 P6：Constraints

字段：

* `Must Include`
* `Avoid`
* `Brand Safety`
* `Platform Safety`
* `Commercial Bias`

### 区块 P7：Evidence

字段：

* `Source Visual Summary`
* `High-performing Patterns`
* `Brand Preference Patterns`

### 区块 P8：Spec Readiness

字段：

* 主体清晰度
* 场景完整度
* 风格一致性
* 约束充分度
* 平台适配度

## 7.3 核心动作

* `应用修改`
* `生成 3 个变体`
* `保存为 Visual Template`
* `保存到品牌偏好`

## 7.4 成功标准

高端用户可以不改 prompt，也能做精细控制与局部优化。

---

# 八、Expert 模式 PRD

## 8.1 目标

给专家用户执行层透明度与调试能力。

## 8.2 区块设计

### 区块 E1：ImageSpec JSON

* JSON viewer / editor
* diff compare
* export / copy

### 区块 E2：Prompt Renderer

* renderer 选择
* rendered prompt
* negative prompt
* renderer patch

### 区块 E3：Evidence Injection

* high-performing patterns 命中项
* brand preference 注入项
* 参考图摘要
* 注入权重

### 区块 E4：Diff View

* 当前版本 vs 上一版本
* 结构化 diff
* prompt diff
* 影响预测

### 区块 E5：Post-eval Preview

* brief alignment
* product prominence
* xiaohongshu nativeness
* style stability
* reference distance

### 区块 E6：Debug Info

* object ID
* version ID
* plan ID
* renderer ID
* source refs
* model config

## 8.3 核心动作

* `应用 patch`
* `仅重新渲染 prompt`
* `导出 spec`
* `复制完整 prompt`
* `回退到上一版本`

## 8.4 成功标准

专家用户可以调试系统，而不需要绕到后端或日志里。

---

# 九、状态设计

## 9.1 通用状态

* Default
* Editing
* Applying
* Regenerating
* Locked
* Error

## 9.2 AI 建议状态

* default
* hover
* applied
* dismissed

## 9.3 Diff 状态

* added
* removed
* modified
* auto-injected
* user-overridden

---

# 十、如何融入开源项目参考

这里要讲清楚：**不要把开源项目直接塞进产品 UI，而要按层吸收它们。**

---

## 10.1 ComfyUI：放在执行工作流层，不放在业务主 UI 层

ComfyUI 最强的是 graph / nodes / modular workflows。它适合做：

* 生成
* 参考图控制
* inpaint / outpaint
* upscale
* background patch
* post-processing
  这种可组合图像执行流。([GitHub][1])

### 对 Creative Inspector 的作用

* Inspector 改的是 `ImageSpec`
* `ImageSpec` 通过 renderer 和 workflow mapper，映射到 ComfyUI graph
* 用户不用直接看到 node graph

### 产品结论

**借 ComfyUI 的执行能力，不借它的 node editor 作为业务主界面。**

---

## 10.2 InvokeAI：借 Unified Canvas 思路

InvokeAI 的公开定位里，Unified Canvas 支持 generation、inpainting/outpainting、brush tools，同时保留 workflows & nodes。([GitHub][2])

### 对 Creative Inspector 的作用

* 说明 “结构化控制面板 + 画布式局部修改” 可以并存
* 后续你可以让 Creation Workspace 从 Plan Board 逐步升级到更强的 Visual Planning Canvas
* Inspector 作为右侧控制器，Canvas 作为中部工作面

### 产品结论

**借它的“统一创作工作面”思路，不直接照抄它的 AI art studio 外形。**

---

## 10.3 Jaaz：借 prompt-free / object-direct 的交互方式

Jaaz 公开强调 prompt-free creation、paint directly、point with arrows、AI instantly understands。([GitHub][3])

### 对 Creative Inspector 的作用

* 右栏不该只是表单
* 未来可以支持“点图位 / 画框 / 标记区域 / 箭头说明”
* 对象驱动和局部意图表达会更自然

### 产品结论

**借它的对象直操与多模态意图输入，不直接做成通用白板产品。**

---

## 10.4 ComfyUI-PolotnoCanvasEditor：借“生成 + 设计编辑器”融合方式

这个项目说明，生成工作流和 canvas editor 是可以打通的。([GitHub][4])

### 对 Creative Inspector 的作用

* 说明 Inspector 不必承担所有精修工作
* 一部分精修可以进入真正的 canvas editor
* 但 canvas editor 仍然由 Inspector 和 `ImageSpec` 驱动

### 产品结论

**借它的“生成后进入画布编辑”模式，作为后续高级精修层。**

---

## 10.5 Hermes-Agent：借 Skill / Memory / Learning Loop

Hermes 官方强调：

* built-in learning loop
* create and improve skills
* persistent knowledge
* search past conversations
* deeper model of who you are。([GitHub][5])

### 对 Creative Inspector 的作用

* 保存品牌偏好
* 记录用户常用 patch
* 把高频精修动作沉淀成 skill
* 根据历史自动生成 AI suggestions

### 产品结论

**Hermes 放在 Agent Base 层，不放在前端交互层。**

---

## 10.6 DeerFlow：借 workflow / subagents / sandboxes

DeerFlow 官方强调 orchestrates sub-agents, memory, sandboxes；后端基于 LangGraph，并支持 per-thread isolated environments。([GitHub][6])

### 对 Creative Inspector 的作用

* 将“重生成当前对象”“生成 3 个变体”“保存模板并应用品牌 patch”等动作编排成执行流
* 把局部精修作为 sub-workflow
* 把导出、批量比较、回填等放在 workflow 层

### 产品结论

**DeerFlow 放在长链路执行与任务编排层。**

---

# 十一、Skill Map：视觉精修能力如何放进产品架构

这里是最关键的架构问题。

我的判断是：

## 视觉精修不是“全部 skill 化”，而是：

* **判断层**：对象化工作流 + 人机协作
* **执行层**：高度可 skill 化
* **编排层**：workflow 化
* **学习层**：memory / preference / template 化

---

## 11.1 三层 Skill Map

### 第一层：Atomic Skills（原子技能）

面向单个视觉变量的最小动作。

示例：

* `adjust_scene_realism`
* `increase_product_visibility`
* `reserve_text_safe_area`
* `shift_color_palette_warmer`
* `reduce_advertorial_feel`
* `tighten_reference_distance`
* `apply_brand_style_patch`

### 第二层：Composite Skills（组合技能）

组合多个原子动作，解决常见业务问题。

示例：

* `make_cover_more_xhs_native`
* `make_slot_more_clickable`
* `upgrade_to_lifestyle_scene`
* `convert_to_brand_consistent_variant`
* `prepare_cover_with_text_overlay_space`

### 第三层：Workflow Skills（工作流技能）

面向完整任务链。

示例：

* `generate_and_rank_cover_variants`
* `refine_selected_slot_then_export`
* `post_generate_evaluate_and_patch`
* `prepare_asset_bundle_for_designer`

---

## 11.2 Skill 与 Workspace 的关系

### Opportunity Workspace

更偏判断，不宜过度 skill 化
适合：

* `summarize_visual_evidence`
* `detect_high_performing_patterns`

### Planning Workspace

更偏策略，不宜把策略本身 skill 化
适合：

* `suggest_visual_direction_candidates`
* `suggest_brand_preference_patch`

### Creation Workspace

最适合 skill 化
适合：

* `regenerate_image_slot`
* `make_cover_more_xhs_native`
* `reduce_advertorial_feel`
* `increase_product_visibility`
* `reserve_text_safe_area`

### Asset Workspace

适合 workflow skill 化
适合：

* `generate_variants`
* `compare_variants`
* `prepare_export_package`
* `record_publish_feedback`

---

## 11.3 Skill 资产组织方式

参考 `awesome-agent-skills` 的思路，可以让每个 skill 作为独立目录与说明文档存在。([GitHub][7])

### 建议目录

```text
skills/
  visual_atomic/
    adjust_scene_realism/
      SKILL.md
      schema.json
      examples.json
    increase_product_visibility/
      SKILL.md
      schema.json
  visual_composite/
    make_cover_more_xhs_native/
      SKILL.md
      schema.json
  visual_workflows/
    generate_and_rank_cover_variants/
      SKILL.md
      workflow.json
      schema.json
```

### 每个 Skill 最少包含

* 名称
* 适用对象
* 输入 schema
* 输出 schema
* 依赖约束
* 可解释说明
* 示例
* 可评估指标

---

# 十二、产品架构建议

## 12.1 分层架构

### Layer 1：Product Layer

* Opportunity Workspace
* Planning Workspace
* Creation Workspace
* Asset Workspace
* Creative Inspector

### Layer 2：Object Layer

* OpportunityCard
* OpportunityBrief
* RewriteStrategy
* NewNotePlan
* MainImagePlan
* ImageSlotPlan
* ImageSpec
* AssetBundle
* VariantSet
* BrandPreferenceProfile
* VisualTemplate

### Layer 3：Agent Base Layer（Hermes）

* memory
* skill registry
* learning loop
* preference store

### Layer 4：Workflow Harness Layer（DeerFlow）

* subagent orchestration
* sandbox execution
* partial rerun
* async tasks
* action execution

### Layer 5：Visual Execution Layer

* renderer
* ComfyUI workflows
* image processing
* evaluation
* export

---

## 12.2 Creative Inspector 在架构中的位置

它不在最底层，也不在最顶层。

它属于：

## **Product Layer 与 Object Layer 的中间控制器**

作用是：

* 显示当前对象
* 编辑当前对象
* 触发 action
* 调用 skill / workflow
* 写回对象

---

# 十三、关键 MVP 建议

如果你现在不要一次做满，我建议按下面顺序做：

## P0

* Lite / Pro / Expert 三模式
* `ImageSpec` 映射到 Inspector
* `apply / regenerate / save template / save brand preference` 动作闭环

## P1

* 接 Hermes 记忆与 Skill Registry
* 接 DeerFlow 局部工作流
* 接 ComfyUI 执行 graph

## P2

* 接 Unified Canvas / 局部编辑工作面
* 接版本比较
* 接 post-eval + feedback loop

---

# 十四、AI-coding Prompt

下面给你一版可直接给 AI coding 工具的 Prompt。

项目背景：
我们已有一个 AI-native 内容策划与视觉生成工作台，当前在 Creation Workspace 右侧只有一个简单的 Prompt Builder。现要升级为“Creative Inspector”，支持 Lite / Pro / Expert 三种模式，围绕当前选中的对象（Plan / Title / Body / Image Slot / Reference）进行对象化视觉控制。

设计原则：

1. 不再以 prompt 作为核心对象，而以 ImageSpec / VisualDecision variables 为核心对象
2. Lite 给普通业务用户：控制方向
3. Pro 给高端用户：控制结构化视觉变量
4. Expert 给专家用户：查看 spec / prompt / renderer / diff / debug
5. 右栏必须对象驱动，不是全局表单
6. 支持 AI 建议 + 可执行动作 + 局部重生成
7. 支持保存为 Visual Template / 保存到 Brand Preference
8. 后续会接 Hermes-Agent 做 skill / memory，接 DeerFlow 做 workflow orchestration，底层可能映射到 ComfyUI workflow

请你输出并实现：

一、前端组件方案

* 组件树设计
* 推荐目录结构
* 状态管理方案
* TypeScript 类型定义
* mock schema

二、核心组件
实现以下组件：

* CreativeInspectorPanel
* InspectorHeader
* LiteModePanel
* ProModePanel
* ExpertModePanel
* SuggestionCardList
* ReadinessScoreCard
* BottomActionBar
* DiffPreviewBlock
* PromptRendererBlock
* ImageSpecEditorBlock

三、Lite 模式字段

* primaryGoal
* businessIntent
* platformFitPriority
* visualFeel
* tone
* referenceDistance
* sceneDirection
* productVisibility
* humanPresence
* textOverlayEnabled
* overlayStyle
* clickability
* quickAvoidTags

四、Pro 模式字段
按结构化 ImageSpec 实现：

* subject
* scene
* composition
* style
* textOverlay
* constraints
* evidence
* readiness

五、Expert 模式字段

* imageSpecJson
* rendererType
* renderedPrompt
* negativePrompt
* rendererPatch
* evidenceInjectionItems
* diffPreview
* postEvalPreview
* debugInfo

六、交互要求

* 顶部有模式切换：Lite / Pro / Expert
* 根据 selectedObject 动态切换内容
* 底部固定 action bar
* 支持 unsaved changes / locked / loading / regenerating / error 状态
* 每条 AI suggestion 支持 apply / dismiss
* 每个模块支持 restore default / reset block
* Expert 模式支持 copy prompt / export spec / revert version

七、产品架构要求

* 给出该组件在整体产品架构中的位置说明
* 说明哪些能力应走 Hermes（skill / memory）
* 说明哪些动作应走 DeerFlow（workflow / rerun / sandbox）
* 说明哪些执行最终映射到底层 ComfyUI workflow
* 给出 Skill Map 接入点：

  * Atomic Skills
  * Composite Skills
  * Workflow Skills

八、工程要求

* 优先 React + TypeScript + Tailwind
* 高度组件化
* 类型完整
* mock 数据可直接跑
* 不要把所有逻辑堆到一个文件
* 先输出组件设计与类型，再输出核心 UI 代码，再输出架构说明

---

# 十五、最后一句产品判断

**右侧 Creative Inspector 不该被定义成“更复杂的 prompt builder”，而应该被定义成：**

## **面向对象、面向技能、面向工作流的视觉决策控制台**

它的价值不在于让用户输入更多，而在于让用户和系统一起：

* 看懂当前对象
* 调整关键视觉决策变量
* 触发结构化 skill
* 调用编排工作流
* 最终把修改沉淀成模板与品牌偏好资产


[1]: https://github.com/comfy-org/ComfyUI "GitHub - Comfy-Org/ComfyUI: The most powerful and modular diffusion model GUI, api and backend with a graph/nodes interface. · GitHub"
[2]: https://github.com/invoke-ai/InvokeAI/blob/main/README.md "InvokeAI/README.md at main · invoke-ai/InvokeAI · GitHub"
[3]: https://github.com/11cafe/jaaz "GitHub - 11cafe/jaaz: The world's first open-source multimodal creative assistant  This is a substitute for Canva and Manus that prioritizes privacy and is usable locally. · GitHub"
[4]: https://github.com/jtydhr88/ComfyUI-PolotnoCanvasEditor "GitHub - jtydhr88/ComfyUI-PolotnoCanvasEditor · GitHub"
[5]: https://github.com/NousResearch/hermes-agent/blob/main/README.md "hermes-agent/README.md at main · NousResearch/hermes-agent · GitHub"
[6]: https://github.com/bytedance/deer-flow/blob/main/README.md "deer-flow/README.md at main · bytedance/deer-flow · GitHub"
[7]: https://github.com/heilcheng/awesome-agent-skills "GitHub - heilcheng/awesome-agent-skills: Tutorials, Guides and Agent Skills Directories · GitHub"
