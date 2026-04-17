
# 《PRD + 技术升级（Part 1）：长视频策划生成板块》

> 本部分只聚焦一个升级方向：
> **把“前3秒裂变”扩展为“15–20s / 30s 长视频策划与生成”的独立产品板块**。
> 不包含品牌资产融入，避免对象模型、链路和页面混杂。品牌资产融入将单独作为 Part 2 输出。

---

## 1. 升级背景与问题定义

### 1.1 当前状态

当前系统在短视频侧，已经形成了围绕“前3秒钩子”的策划与裂变能力，适合：

* 抢停留
* 抢点击
* 快速混剪派生版本
* 小流量低成本测试

但它仍然偏“短钩子编译”，还不是完整的“视频叙事编译系统”。现有 Visual Builder 更偏图像生成与 prompt 控制，原有内容策划链路 `Brief -> Strategy -> Plan -> AssetBundle` 也更适合内容方案层，而不是直接支持 15–20s / 30s 视频结构化生成。来源：当前产品功能 PRD。fileciteturn6file2L160-L258

### 1.2 为什么要升级成长视频板块

前3秒解决的是“停下来”和“点不点”；但长视频还要解决：

* 用户是否理解自己适不适合
* 是否能建立信任感
* 是否能在中段承接卖点
* 是否能把点击、收藏、加购和购买动作引出来

对天空树这类客户来说，前3秒已经比较成熟，下一步更高价值的方向不是继续只做钩子，而是让高表现前3秒能系统化扩展为 15–20s / 30s 短视频结构，从而提升：

* 点击后的转化承接
* 素材生命周期
* 品牌表达完整度
* 广告创意测试深度

### 1.3 升级目标

把现有“前3秒裂变能力”升级成一个独立的：

**Video Flow Studio（长视频策划与生成工作台）**

一句话定义：
**将卖点、人群、场景、平台机制和参考素材，编译为 15–20s / 30s 可执行的短视频结构、脚本、镜头计划和版本集合。**

---

## 2. 产品定位与设计原则

## 2.1 产品定位

Video Flow Studio 不是剪辑工具，不是通用 AIGC 生视频页，也不是直播脚本页。

它的准确定位是：

**短视频结构编译系统**

核心做的是：

* 从 hook 出发扩写完整短视频
* 从卖点对象直接生成视频结构
* 组织品牌已有素材和新补充镜头
* 输出可测试的视频版本，而不是只给一个创意 idea

## 2.2 设计原则

### 原则 A：先编排，后生成

第一阶段先做结构、脚本、镜头与素材装配，不把“纯 AI 生成整条视频”作为主路径。

### 原则 B：前台极简，内部结构化

前台用户看到的是：

* 目标长度
* 核心卖点
* 视频结构
* 候选版本
* 测试任务

内部对象层则保持结构化：

* hook block
* bridge block
* proof block
* CTA block

### 原则 C：前3秒是入口，但不是全部

前3秒仍然是长视频的入口，但不是唯一对象。系统必须支持从：

* 高表现前3秒扩写成长视频
* 卖点对象直接生成长视频
* 旧爆款视频拆解出新的长视频结构

### 原则 D：为测试而生

每一个长视频版本都必须能直接进入测试板，而不是停在内容方案阶段。

---

## 3. 目标用户与核心任务

## 3.1 目标用户

1. 内容负责人
2. 短视频团队负责人
3. 剪辑组长
4. 运营负责人
5. 广告素材负责人

## 3.2 核心任务

* 把一个高表现前3秒扩展成 15–20s / 30s 视频
* 围绕某个卖点快速生成多个视频结构版本
* 给剪辑团队明确分镜、口播、字幕和镜头调用计划
* 将视频版本直接进入测试
* 根据测试回流快速优化中段承接和 CTA

---

## 4. 产品目标与业务指标

## 4.1 产品目标

1. 缩短长视频策划时间
2. 降低内容负责人对“从0写视频方案”的依赖
3. 增强从前3秒到完整视频的承接能力
4. 提升视频版本管理与测试效率

## 4.2 业务指标建议

### 北极星指标

* 长视频版本生成到进入测试的平均耗时

### 过程指标

* 每个卖点平均生成的视频版本数
* 从前3秒扩展成长视频的成功率
* 长视频结构脚本被采用率
* 视频预览导出率

### 结果指标

* 15s 视频 CTR
* 5s / 8s / 15s retention
* 点击后 CVR
* 视频疲劳周期
* 高表现版本占比

---

## 5. 页面 PRD：Video Flow Studio

## 5.1 页面定位

这是长视频策划与生成的独立一级页面，不并入 Main Image Lab，也不并入 First3s Lab。

### 页面入口

建议一级导航：

* Radar
* Compiler
* Lab
* **Video**
* Board
* Assets

其中 `Video` 就是 Video Flow Studio。

## 5.2 页面结构

### 左栏：输入与参考

#### 模块 1：来源对象

* 来源卖点对象 `SellingPointSpec`
* 来源前3秒版本 `First3sVariant`
* 来源机会对象 `TrendOpportunity`

#### 模块 2：基础配置

* 目标平台
* 视频长度：15s / 20s / 30s
* 目标人群
* 目标场景
* 目标：引流 / 转化 / 测款 / 品牌表达

#### 模块 3：参考素材

* 参考爆款视频
* 参考高表现片段
* 品牌已有视频素材（未来 Part 2 深接）
* 系统推荐模式模板

### 中栏：结构编译画布

按时间与功能拆成 4 段：

#### Block A：Hook（0–3s）

* 钩子类型
* 强问题 / 强结果 / 强反差 / 强场景代入
* 口播开头
* 视觉冲击建议

#### Block B：Bridge（3–8s）

* 用户是谁
* 解决什么问题
* 为什么和你有关
* 与场景绑定

#### Block C：Proof（8–15s）

* 前后对比
* 细节镜头
* 使用演示
* 评论/证据
* 功能说明

#### Block D：CTA（15–20s 或 30s 收口）

* CTA 类型
* 利益点提示
* 行动指令
* 平台化收尾方式

每个 block 都支持：

* 自动生成
* 手动编辑
* 切换模板
* 替换素材
* 查看高表现模式参考

### 右栏：输出与评估

#### 模块 1：版本列表

* 版本 A/B/C
* 长度
* 风格差异
* 适合平台
* 预期目标

#### 模块 2：脚本输出

* 全视频脚本
* 分镜列表
* 字幕文案
* 口播文案
* 镜头调用计划

#### 模块 3：预评分与建议

* hook 强度评分
* 承接清晰度评分
* 证据充分度评分
* CTA 完整度评分
* 平台适配评分

#### 模块 4：动作区

* 导出视频脚本包
* 导出剪辑执行包
* 生成预览视频
* 创建测试任务

---

## 6. 用户故事

### 用户故事 1：从前3秒扩写成长视频

作为短视频负责人，我希望把一个点击率很高的前3秒版本，快速扩写成 15–20s 的完整视频脚本和分镜，以便继续测试点击后转化。

### 用户故事 2：从卖点对象直生成长视频

作为运营负责人，我希望围绕一个新卖点，直接生成多个 15–20s 视频结构版本，而不是先靠人工写完整脚本。

### 用户故事 3：给剪辑团队明确执行包

作为内容组长，我希望系统输出明确的镜头顺序、字幕和口播，不只是一个抽象创意方向。

### 用户故事 4：直接进入测试

作为投放负责人，我希望长视频版本可以和主图、前3秒一样进入测试板，并在回流后继续优化。

---

## 7. 对象模型设计

## 7.1 核心对象

### 1）VideoNarrativeSpec

```yaml
object_type: VideoNarrativeSpec
fields:
  - narrative_id
  - source_selling_point_id
  - source_hook_variant_id
  - source_opportunity_id
  - target_platform
  - target_length_sec
  - target_people
  - target_scenario
  - goal_type       # 引流 / 转化 / 测款 / 品牌表达
  - hook_block_id
  - bridge_block_id
  - proof_block_ids
  - cta_block_id
  - style_profile
  - confidence_score
  - status
```

### 2）VideoBlock

```yaml
object_type: VideoBlock
fields:
  - block_id
  - narrative_id
  - block_type      # hook / bridge / proof / cta
  - start_sec
  - end_sec
  - purpose
  - core_message
  - subtitle_text
  - spoken_text
  - visual_instruction
  - selected_asset_ids
  - pattern_refs
  - confidence_score
```

### 3）ClipAssemblyPlan

```yaml
object_type: ClipAssemblyPlan
fields:
  - plan_id
  - narrative_id
  - ordered_clip_ids
  - transition_style
  - subtitle_style
  - voiceover_mode
  - asset_mix_ratio
  - generation_mode      # 混剪优先 / 素材优先 / AI补镜优先
  - export_targets
```

### 4）VideoNarrativeVariant

```yaml
object_type: VideoNarrativeVariant
fields:
  - variant_id
  - narrative_id
  - length_sec
  - hook_style
  - bridge_style
  - proof_style
  - cta_style
  - asset_mix_profile
  - expected_goal
  - readiness_score
  - status
```

### 5）VideoQualityScore

```yaml
object_type: VideoQualityScore
fields:
  - score_id
  - variant_id
  - hook_strength
  - bridge_clarity
  - proof_adequacy
  - cta_clarity
  - platform_fit
  - narrative_coherence
  - overall_score
  - suggestions
```

---

## 8. 编译链设计

## 8.1 主链路

```text
SellingPointSpec / First3sVariant / TrendOpportunity
    ↓
Narrative Planner
    ↓
Video Block Compiler
    ↓
Clip Retriever / Matcher
    ↓
Clip Assembly Plan
    ↓
Video Variant Generator
    ↓
Preview / Export / TestTask
```

## 8.2 模块说明

### 模块 1：Narrative Planner

输入：

* 卖点对象
* 平台
* 长度
* 人群
* 场景
* 目标

输出：

* VideoNarrativeSpec
* 各 block 的时间占比与目标

### 模块 2：Video Block Compiler

输入 NarrativeSpec，输出：

* Hook block
* Bridge block
* Proof block(s)
* CTA block

### 模块 3：Clip Retriever / Matcher

根据 block 需求去找合适片段：

* 来源爆款视频
* 来源品牌素材（未来 Part 2 深接）
* 参考视频库
* AI 补镜候选

### 模块 4：Assembly Plan Generator

把片段、字幕、口播、镜头顺序与转场编译成剪辑执行包。

### 模块 5：Video Variant Generator

基于不同 hook/proof/CTA 风格派生 2–5 个可测试版本。

---

## 9. 技术架构升级

## 9.1 新增服务

### `video_narrative_service`

负责：

* 长视频结构规划
* 视频块生成
* 视频版本派生

### `clip_assembly_service`

负责：

* 片段顺序编排
* 转场、字幕、口播组织
* 导出剪辑计划

### `video_preview_service`

负责：

* 生成预览视频
* ffmpeg 任务编排
* 字幕/音频合成

### `video_scoring_service`

负责：

* 视频结构预评分
* narrative coherence / proof adequacy / CTA clarity 打分

## 9.2 技术栈建议

* `ffmpeg`：切片、拼接、字幕烧录、音频混合
* `whisper` / ASR：转写与字幕对齐
* `scene detection`：镜头切分
* `LLM`：视频结构编译与脚本生成
* `object storage`：片段管理
* `queue/worker`：重任务异步执行

## 9.3 运行策略

### 第一阶段

只做：

* 结构化脚本
* 分镜
* 镜头调用计划
* 版本生成

### 第二阶段

增加：

* 自动预览视频生成
* 字幕和音频合成

### 第三阶段

增加：

* 自动补镜
* 更细的镜头级优化

---

## 10. API 设计（第一版）

### Narrative

* `POST /api/video/narratives`
* `GET /api/video/narratives/:id`
* `PUT /api/video/narratives/:id`

### Blocks

* `POST /api/video/narratives/:id/compile-blocks`
* `GET /api/video/blocks/:id`
* `PUT /api/video/blocks/:id`

### Variants

* `POST /api/video/narratives/:id/variants`
* `GET /api/video/variants/:id`
* `POST /api/video/variants/:id/score`

### Assembly / Preview

* `POST /api/video/variants/:id/assembly-plan`
* `GET /api/video/assembly-plans/:id`
* `POST /api/video/variants/:id/preview`

### Board Integration

* `POST /api/video/variants/:id/create-test-task`

---

## 11. 前端组件骨架

### 页面级组件

* `VideoFlowStudioPage`
* `VideoInputPanel`
* `NarrativeCanvas`
* `VideoBlockEditor`
* `VariantListPanel`
* `VideoQualityPanel`
* `ClipAssemblyPlanPanel`
* `VideoPreviewPanel`

### Block 组件

* `HookBlockCard`
* `BridgeBlockCard`
* `ProofBlockCard`
* `CTABlockCard`

### 动作组件

* `GenerateNarrativeButton`
* `GenerateVariantsButton`
* `CreatePreviewButton`
* `CreateTestTaskButton`

---

## 12. 与现有系统的衔接方式

### 12.1 输入衔接

来自现有对象：

* `TrendOpportunity`
* `SellingPointSpec`
* `First3sVariant`
* （可选）`OpportunityBrief`

### 12.2 输出衔接

输出给现有系统：

* `TestTask`
* `ResultSnapshot`
* `Asset Graph`

### 12.3 页面衔接

* 从 Radar/Compiler/Lab 进入 Video 页
* 从 Video 页直接创建测试任务进入 Board
* 长视频高表现版本进入 Assets

---

## 13. 实施计划（长视频专项）

### 阶段 1：0–3 周

目标：打通 Video Flow Studio 最小链路

交付：

* 页面框架
* VideoNarrativeSpec / VideoBlock / Variant schema
* Narrative Planner
* Block Compiler
* 版本生成与导出脚本包

### 阶段 2：4–6 周

目标：打通预览与测试

交付：

* ClipAssemblyPlan
* 视频预览生成
* 接 Board 的测试任务
* 视频结构预评分

### 阶段 3：7–10 周

目标：打通版本优化与模式沉淀

交付：

* 回流后的视频结构调整建议
* 长视频赢家结构模板
* 版本对比与复用机制

---

## 14. 验收标准

### 产品验收

* 能从前3秒对象扩展生成长视频结构
* 能从卖点对象直接生成 15–20s / 30s 视频版本
* 能输出脚本、分镜、口播、字幕与剪辑计划
* 能生成预览视频
* 能创建测试任务并进入 Board

### 业务验收

* 长视频策划时间缩短
* 版本产出更稳定
* 视频中段承接能力提升
* 长视频测试效率提升

---

## 15. AI-coding 开工建议

### 第一批对象

* `VideoNarrativeSpec`
* `VideoBlock`
* `ClipAssemblyPlan`
* `VideoNarrativeVariant`
* `VideoQualityScore`

### 第一批页面

* `/video`
* `/video/:id`
* `/video/variants/:id`

### 第一批服务

* `video_narrative_service`
* `clip_assembly_service`
* `video_preview_service`
* `video_scoring_service`

### 第一批接口

* `POST /api/video/narratives`
* `POST /api/video/narratives/:id/compile-blocks`
* `POST /api/video/narratives/:id/variants`
* `POST /api/video/variants/:id/preview`
* `POST /api/video/variants/:id/create-test-task`

---

## 16. 一句话总结

**Part 1 的交付目标，是把“前3秒裂变能力”正式升级成一个可独立运行的“长视频策划与生成工作台”，让系统具备从 hook 到完整视频叙事的编译能力。**

