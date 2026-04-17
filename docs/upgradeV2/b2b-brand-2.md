# 《Growth Lab（小红书聚焦版）PRD + 技术升级方案》

版本：V1.0
日期：2026-04-17
范围：**核心工作流 A：热点驱动内容生产** + **多品牌多组织** + **品牌治理**
目标：**快速让品牌先用起来**

---

# 1. 产品目标

## 1.1 产品定义

Growth Lab 小红书聚焦版，是一个面向品牌内容与经营团队的 AI-native 内容生产与测试平台。
它围绕“小红书热点 → 卖点编译 → 主图/前3秒裂变 → 发布 → 回采 → 放大 → 资产沉淀”形成最短闭环，并通过多品牌工作区与品牌治理能力，支持多个品牌团队快速接入和实际使用。

## 1.2 本阶段目标

这一阶段不追求“大而全”，只追求三件事：

### 目标一：让品牌真的能跑通

不是只生成素材，而是品牌团队能在一周内上手，跑通：

* 导入品牌资料
* 看热点
* 编译卖点
* 生成主图/前3秒
* 发到小红书
* 回采结果
* 看结论

### 目标二：支持多个品牌并行使用

平台要支持：

* 多品牌隔离
* 多角色协作
* 品牌模板与规则隔离
* 小红书账号隔离
* 资产隔离

### 目标三：建立品牌治理底座

平台生成内容必须“像这个品牌”，而不是只“像小红书爆文”。

---

# 2. 范围定义

---

## 2.1 本期范围（P0）

### 核心主链路

1. 热点雷达
2. 卖点编译器
3. 主图裂变工作台
4. 前3秒裂变工作台
5. 发布中心（小红书）
6. 数据回采与测试放大板
7. 资产晋升与复用（轻量版）

### 平台底座

1. 多品牌工作区
2. 用户/角色/权限
3. 品牌知识与模板
4. 品牌规则治理
5. 小红书账号接入与隔离
6. 审计日志
7. 任务调度

---

## 2.2 暂不做

本期明确不做这些，避免拖慢落地：

* 多平台发布（先只做小红书）
* 广告投放自动化
* 淘系主图替换
* 自定义复杂 BI 中心
* 行业通用开放平台
* 品牌专属模型训练
* 完整项目管理系统

---

# 3. 核心用户与场景

## 3.1 用户角色

### 品牌老板 / CEO

关注：

* 热点是否值得做
* 哪些素材跑出来了
* 哪些该放大
* 品牌投入产出是否清楚

### 运营总监

关注：

* 热点筛选
* 节奏推进
* 发布执行
* 数据回采
* 放大判断

### 产品研发总监

关注：

* 卖点是否准确
* 是否符合货盘与品类策略
* 场景/人群/利益点是否合理

### 视觉总监

关注：

* 主图和首帧是否符合品牌视觉
* 是否可批量复用
* 是否形成模板

### 内容策划 / 编辑

关注：

* 快速产出
* 快速改稿
* 快速发布
* 快速复盘

### 平台管理员

关注：

* 品牌开通
* 用户权限
* 品牌知识配置
* 小红书账号接入
* 调用成本与日志

---

# 4. 核心业务闭环

```text
热点信号进入
→ 热点归一与筛选
→ 选择机会
→ 编译卖点
→ 注入品牌上下文与规则
→ 生成主图/前3秒变体
→ 人工审稿/调整
→ 发布到小红书
→ 定时回采数据
→ 自动生成测试结论
→ 放大 / 止损 / 再裂变
→ 高表现资产沉淀
```

这条链路是 P0 真正的主线。
所有页面、对象、接口都围绕它服务。

---

# 5. PRD：详细产品设计

---

## 5.1 一级导航结构

1. 首页总览
2. 热点雷达
3. 卖点编译器
4. 主图实验室
5. 前3秒实验室
6. 发布中心
7. 测试放大板
8. 品牌资产中心
9. 品牌治理中心
10. 工作区管理

---

## 5.2 首页总览

### 页面目标

让品牌团队一进来就知道今天该做什么。

### 核心信息

* 今日热点机会 Top 10
* 待编译机会
* 待审稿素材
* 待发布素材
* 今日发布结果
* 活跃测试任务
* 放大建议
* 风险预警
* 最近沉淀的高表现资产

### 核心动作

* 新建项目
* 进入某个热点
* 进入待审核素材
* 进入放大任务
* 查看品牌规则拦截情况

### 首页卡片设计

#### 卡片 A：今日热点机会

字段：

* 机会标题
* 来源
* 新鲜度
* 相关度
* 品牌匹配度
* 推荐推进理由

动作：

* 收藏
* 创建项目
* 推进编译

#### 卡片 B：待拍板素材

字段：

* 素材类型
* 关联卖点
* 生成时间
* 审稿状态
* 品牌一致性分
* 风险提示

动作：

* 审核
* 改稿
* 发布

#### 卡片 C：放大建议

字段：

* 素材
* 当前指标
* 建议动作
* 置信度
* 预估价值

动作：

* 放大
* 再裂变
* 止损

---

## 5.3 热点雷达

### 页面目标

从小红书热点、竞品动态、跨域灵感中，找到可被当前品牌使用的机会。

### 页面结构

#### 左侧：筛选区

* 来源类型
* 时间范围
* 类目
* 话题
* 品牌匹配度
* 人群标签
* 是否已收藏
* 是否已创建项目

#### 中间：机会列表

每张机会卡展示：

* 标题
* 热点摘要
* 来源平台
* 原始笔记缩略图
* 新鲜度
* 热度分
* 品牌匹配度
* 可执行性分
* 推荐理由

#### 右侧：机会详情面板

* 热点背景
* 关联内容示例
* 对品牌的潜在价值
* 适合的卖点方向
* 适合的内容表达方式
* 历史相似案例
* 风险提示

### 核心动作

* 收藏
* 标注
* 忽略
* 推进为项目
* 推进到卖点编译
* 分配负责人

### 关键升级点

当前雷达更多是“机会列表”。升级后要增加：

#### 1）品牌匹配层

每个热点都要基于品牌上下文打一个“Brand Fit Score”。

维度：

* 品类匹配
* 人群匹配
* 语气匹配
* 视觉风格匹配
* 历史高表现模式匹配

#### 2）机会晋级机制

状态流转：

* discovered
* bookmarked
* shortlisted
* in_project
* compiled
* archived

#### 3）热点分群

不是平铺 500 条机会，而是聚成：

* 热门打法簇
* 竞品动作簇
* 场景情绪簇
* 功能卖点簇
* 审美风格簇

---

## 5.4 卖点编译器

### 页面目标

把热点机会编译成“可执行的、符合品牌的、适合小红书表达的卖点规格”。

### 页面结构

#### 左侧：上下文输入区

* 机会信息
* 品牌信息
* 商品信息
* 历史资产推荐
* 用户手工补充

#### 中间：卖点编译结果

输出结构：

* 核心卖点
* 支撑卖点
* 目标人群
* 目标场景
* 差异化点
* 风险提示
* 小红书标题表达
* 小红书正文方向
* 主图表达方向
* 前3秒表达方向

#### 右侧：品牌治理与评估区

* 品牌语气检查
* 禁用词检查
* 风险内容检查
* 品牌视觉适配建议
* 卖点评分
* 改进建议
* 历史高表现模板召回

### 核心动作

* 重新编译
* 多版本对比
* 人工改写
* 写入品牌模板
* 进入主图实验室
* 进入前3秒实验室

### 输出对象

`SellingPointSpec`

新增字段建议：

* brand_id
* workspace_id
* project_id
* source_opportunity_id
* product_context
* brand_fit_score
* policy_check_result
* reusable_candidate
* xhs_title_expression
* xhs_caption_expression
* xhs_cover_expression
* first3s_expression

### 关键升级点

#### 1）卖点编译从“单次输出”变成“编译面板”

支持：

* 基于不同目标人群切换版本
* 基于不同表达策略切换版本
* 基于品牌风格切换版本
* 对比多个卖点版本

#### 2）注入品牌知识

编译时必须引用：

* 品牌画像
* 品牌调性
* 禁用表达
* 已验证高表现卖点
* 已知负反馈点

#### 3）结果可直接复用

支持一键：

* 写入 BrandTemplate
* 写入 PatternTemplate 候选
* 生成主图 brief
* 生成前3秒 hook brief

---

## 5.5 主图实验室

### 页面目标

围绕一个卖点，快速生成多个适合小红书封面/主图的高质量候选。

### 页面结构

#### 上方：项目与卖点上下文

* 当前品牌
* 当前项目
* 关联卖点
* 适用人群
* 品牌视觉模板

#### 左侧：变量矩阵区

维度：

* 模特类型
* 构图
* 背景场景
* 情绪
* 色调
* 道具
* 文案位置
* 标题风格
* 产品露出比例

#### 中间：生成结果区

* 网格展示
* 大图预览
* 评分
* 收藏
* 标记为候选
* 对比

#### 右侧：治理与评估区

* 品牌一致性评分
* 小红书封面可点击性评分
* 视觉质量评分
* 违规风险评分
* 参考素材召回
* 生成参数记录

### 核心动作

* 选择品牌模板
* 锁定变量
* 批量生成
* 删除低质量
* 进入发布/实验
* 写入资产中心

### 关键升级点

#### 1）从“生图”升级为“实验候选生成”

输出不仅是图片，还包括：

* 变量组合记录
* 首图意图说明
* 推荐标题搭配
* 适合的人群/场景标签

#### 2）加入品牌视觉模板

每个品牌要支持：

* 主视觉色系
* 构图偏好
* 字体/排版偏好
* 产品露出原则
* 禁用视觉元素

#### 3）引入质量门

生成后不直接进发布，先过三层：

* 技术质量
* 品牌一致性
* 平台适配性

---

## 5.6 前3秒实验室

### 页面目标

围绕卖点生成适合小红书短视频前3秒的钩子方案，并快速进入发布测试。

### 页面结构

#### 左侧：钩子策略区

* 痛点型
* 悬念型
* 对比型
* 利益型
* 情绪型
* 社会认同型
* 种草型

#### 中间：脚本与视频结果区

* HookScript
* 首句
* 支撑句
* CTA
* 首帧说明
* 视频预览
* 多版本对比

#### 右侧：品牌与平台适配区

* 品牌语气检查
* 内容风险检查
* 适合的小红书话题
* 推荐标题
* 推荐正文
* 推荐标签

### 核心动作

* 批量生成 hook
* 选首帧
* 生成视频
* 改脚本
* 发布预览
* 一键发布

### 关键升级点

#### 1）脚本与首帧联动

不再分离生成：

* Hook 文案
* 首帧视觉
* 标题建议
* 正文建议

要一次编译出一个“小红书首屏方案”。

#### 2）加入发布前质检

检查：

* 是否像广告
* 是否过度夸张
* 是否不符合品牌语气
* 是否含禁用表达

#### 3）发布后自动进入测试任务

发布成功自动创建：

* TestTask
* PublishJob
* Metrics Sync Schedule

---

## 5.7 发布中心

### 页面目标

统一管理小红书发布流程，支持品牌账号隔离和审核后发布。

### 页面结构

* 账号状态区
* 草稿列表
* 待审核列表
* 待发布列表
* 发布中任务
* 已发布列表
* 发布失败重试列表

### 核心动作

* 绑定账号
* 查看登录状态
* 提交审核
* 审核通过发布
* 定时发布
* 失败重试
* 关联到测试任务

### 关键升级点

#### 1）账号与品牌工作区绑定

每个品牌自己的小红书账号独立保存：

* storage_state
* 发布人
* 最近登录时间
* 可用状态

#### 2）发布前审批

简单两级：

* 编辑提交
* 运营总监/管理员批准

#### 3）发布内容模板化

标题、正文、话题、封面策略可来自：

* 品牌模板
* 卖点编译结果
* 历史高表现资产推荐

---

## 5.8 测试放大板

### 页面目标

让品牌快速看出什么内容值得继续放大。

### 页面结构

#### 上方：测试汇总

* 活跃任务数
* 审核中数
* 已发布数
* 高表现数
* 待判断数

#### 中间：任务列表

每个任务展示：

* 类型
* 关联卖点
* 关联主图/视频
* 发布时间
* 审核状态
* 当前指标
* 建议动作

#### 右侧：任务详情

* 指标时间线
* 同卖点对比
* 同品牌历史对比
* 相似资产对比
* 自动放大建议
* 再裂变建议

### 自动建议类型

* amplify
* continue_observe
* re_variant
* stop_loss

### 关键升级点

#### 1）定时回采

从手动刷新改成：

* 1 小时
* 6 小时
* 24 小时
* 72 小时
  自动回采

#### 2）统一判断逻辑

根据：

* view
* like rate
* collect rate
* comment rate
* follow gain
* 历史基线
  来生成判断

#### 3）支持放大动作

放大动作先不做广告，只做：

* 二次发布
* 扩更多标题版本
* 扩更多首帧版本
* 扩更多主图版本

---

## 5.9 品牌资产中心

### 页面目标

沉淀品牌自己的高表现内容资产，不让成功经验散失。

### 核心对象

* 高表现主图
* 高表现前3秒
* 高表现标题
* 高表现正文结构
* 高表现 hook 模板
* 品牌表达模板

### 核心动作

* 自动晋升
* 打标签
* 搜索
* 复制复用
* 推荐给新项目

### 关键升级点

本期不做复杂图谱展示，先做“可用的资产库”。

---

## 5.10 品牌治理中心

### 页面目标

保证生成结果“像品牌”。

### 页面结构

#### 品牌画像

* 品牌名
* 品类
* 核心人群
* 品牌调性
* 价格带
* 主打场景
* 核心卖点母题

#### 品牌表达规则

* 推荐语气
* 禁用词
* 敏感表达
* 夸张程度限制
* 标题风格边界
* 正文风格边界

#### 品牌视觉规则

* 主色
* 辅色
* 视觉风格
* 字体/排版偏好
* 产品露出原则
* 禁用视觉元素

#### 品牌模板

* 标题模板
* 正文模板
* 主图模板
* 前3秒模板
* 话题模板

### 核心动作

* 编辑品牌规则
* 导入品牌资料
* 生成初版品牌模板
* 审批模板
* 绑定到工作流

---

# 6. 多品牌多组织设计

---

## 6.1 组织模型

```text
Tenant
 └── Workspace（品牌工作区）
      ├── BrandProfile
      ├── Users / Roles
      ├── XHS Accounts
      ├── Projects
      ├── Assets
      ├── Templates
      └── WorkflowRuns
```

---

## 6.2 权限模型

### 角色

* super_admin
* workspace_admin
* brand_manager
* operator_director
* visual_director
* editor
* analyst
* viewer

### 权限粒度

* 查看热点
* 推进项目
* 编译卖点
* 生成素材
* 审稿
* 发布
* 绑定账号
* 回采数据
* 管理品牌规则
* 管理模板
* 查看审计日志

---

## 6.3 多品牌隔离原则

每个品牌必须隔离：

* 品牌规则
* 资产
* 模板
* 小红书账号
* 项目
* 审计日志
* 调用记录

允许平台共享的只有：

* 公共热点源
* 公共行业模板
* 公共生成服务
* 公共基础模型

---

# 7. 技术升级方案

---

## 7.1 现状与问题

你现在的实现已经验证了业务链路，但商用化会遇到这些瓶颈：

### 1）SQLite 不适合多品牌并发

* 无法承载更高并发
* 不利于事务和隔离
* 不利于后续多租户

### 2）页面与业务逻辑继续膨胀

* 原生 JS 页面已 1000+ 行
* 后续多品牌治理会进一步复杂

### 3）任务执行缺少统一调度

* 生图
* 生视频
* 发布
* 回采
  都需要稳定队列和重试机制

### 4）没有真正的平台控制面

* 无权限体系
* 无审计
* 无配置中心
* 无品牌治理中心

---

## 7.2 升级原则

### 原则一：不推倒重来

先从现有 FastAPI + service 层演进，避免重构成本过高。

### 原则二：先模块化单体，再服务化

不要一上来拆微服务。
先把结构拆干净。

### 原则三：先把小红书闭环做稳

多品牌也只围绕小红书做。

### 原则四：品牌治理必须前置

否则品牌用一轮就会说“不像我”。

---

## 7.3 建议架构

## 7.3.1 前端架构升级

### 当前

* Jinja2 + 原生 JS

### 建议

升级到：

* Vue3
* TypeScript
* Pinia
* Vue Router
* Naive UI / Element Plus

### 原因

* 更适合工作台型复杂页面
* 更适合表单、审批流、任务流、配置中心
* 更适合后续多品牌、多角色 UI 状态管理

### 前端模块建议

* `apps/web-console`

  * `pages/dashboard`
  * `pages/radar`
  * `pages/compiler`
  * `pages/main-image-lab`
  * `pages/first3s-lab`
  * `pages/publish-center`
  * `pages/test-board`
  * `pages/assets`
  * `pages/brand-governance`
  * `pages/admin`

---

## 7.3.2 后端架构升级

### 当前

FastAPI + routes + services + SQLite store

### 建议演进

仍保留 FastAPI，但拆成模块化单体：

```text
apps/growth_lab/
  api/
    radar_routes.py
    compiler_routes.py
    variant_routes.py
    publish_routes.py
    metrics_routes.py
    asset_routes.py
    governance_routes.py
    admin_routes.py
  domain/
    opportunity/
    selling_point/
    variant/
    publish/
    metrics/
    asset/
    governance/
    workspace/
  services/
  repositories/
  workers/
  adapters/
  models/
  schemas/
```

### 新增核心模块

* workspace_service
* auth_service
* brand_governance_service
* publish_job_service
* scheduler_service
* audit_service
* template_service
* metrics_baseline_service

---

## 7.3.3 数据层升级

### 数据库

从 SQLite 升级到 PostgreSQL

### 对象存储

新增：

* MinIO / OSS / S3

存：

* 图片
* 视频
* 封面
* 参考素材
* 导出文件

### 缓存与任务状态

新增：

* Redis

### 后续可选

* pgvector：做相似资产/相似机会召回

---

## 7.3.4 任务调度与队列

### 需要调度的任务

* 热点同步
* 卖点编译
* 批量生图
* 视频生成
* 发布任务
* 定时回采
* 高表现资产晋升
* 模式模板提取

### 技术建议

* Redis + Arq / Celery
* worker 独立进程
* 支持：

  * retry
  * timeout
  * dead letter
  * status tracking

### 最关键两类后台任务

#### A. PublishJob Worker

* 上传
* 发布
* 状态更新
* 创建 TestTask

#### B. MetricsSync Worker

* 根据调度周期自动回采
* 写入 ResultSnapshot
* 触发建议生成

---

## 7.3.5 品牌治理引擎

新增一个统一治理服务：

### `brand_governance_service`

职责：

* 管 BrandProfile
* 管 BrandPolicy
* 管 BrandTemplate
* 在编译前注入品牌上下文
* 在生成后校验品牌一致性
* 在发布前做风险检查

### 治理链路

```text
输入机会/卖点
→ 注入品牌画像
→ 注入品牌模板
→ 生成内容
→ 规则校验
→ 输出检查报告
→ 允许发布 / 待修改
```

### 规则类型

* tone policy
* banned phrase policy
* visual constraint policy
* exaggeration policy
* product claim policy
* xhs safety policy

---

## 7.3.6 小红书适配层升级

你现在已有 `xhs_publisher.py` 和 `note_metrics_syncer.py`，建议抽象成：

### `channel_adapter_xhs`

模块职责：

* account auth
* publish
* draft preview
* metrics sync
* audit status sync

### 好处

后续虽然不做多平台，但架构先不把业务写死。

---

## 7.3.7 审计与日志

商用必须补：

### 审计日志

记录：

* 谁创建了项目
* 谁改了品牌规则
* 谁审了稿
* 谁发布了内容
* 谁手动修改了测试结论

### 任务日志

记录：

* 编译过程
* 生图参数
* 视频生成参数
* 发布过程
* 回采结果
* 失败原因

---

# 8. 核心数据模型升级

---

## 8.1 新增组织与品牌对象

### Workspace

* workspace_id
* tenant_id
* brand_id
* name
* status

### BrandProfile

* brand_id
* workspace_id
* brand_name
* category
* target_people
* tone_of_voice
* core_claims
* banned_terms
* visual_style
* xhs_style_profile

### BrandPolicy

* policy_id
* brand_id
* policy_type
* rules_json
* severity
* enabled

### BrandTemplate

* template_id
* brand_id
* template_type
* template_name
* content_spec
* approved
* reusable

### XHSAccount

* account_id
* workspace_id
* nickname
* storage_state_path
* status
* last_login_at

---

## 8.2 升级现有核心对象

### TrendOpportunity

新增：

* workspace_scope
* brand_fit_score
* matched_categories
* matched_templates
* lifecycle_status

### SellingPointSpec

新增：

* brand_id
* workspace_id
* project_id
* policy_check_result
* xhs_expression_pack
* reusable_candidate

### MainImageVariant

新增：

* brand_template_id
* policy_check_result
* brand_consistency_score
* xhs_cover_score

### First3sVariant

新增：

* brand_template_id
* title_candidate
* caption_candidate
* hashtag_candidate
* policy_check_result
* xhs_hook_score

### TestTask

新增：

* workspace_id
* project_id
* publish_job_id
* sync_schedule
* baseline_group
* decision_status

### AssetPerformanceCard

新增：

* brand_id
* source_project_id
* promoted_reason
* recommended_scenarios
* reusable_score

---

# 9. 推荐实施节奏

---

## Phase 1：两周内让品牌先能用

### 核心目标

能接一个品牌，稳定跑通闭环。

### 必做

* PostgreSQL 替换 SQLite
* BrandProfile / BrandPolicy / BrandTemplate
* Workspace 基础模型
* XHSAccount 绑定
* 自动回采调度
* 首页总览
* 品牌治理中心（基础版）
* 发布前品牌检查

---

## Phase 2：四到六周可支撑多个品牌

### 核心目标

3–5 个品牌并行。

### 必做

* 用户角色权限
* 审计日志
* 发布中心
* 测试放大板升级
* 资产中心轻量版
* 历史高表现资产推荐

---

## Phase 3：六到十周做出平台感

### 核心目标

从“项目 Demo”升级为“工作台平台”。

### 必做

* Vue3 前端化
* 任务队列与后台 worker
* 品牌模板复用
* 自动晋升资产
* 热点分群与品牌匹配
* 多品牌工作区切换

---

# 10. 最小可用商业版本定义

如果你的目标是“快速让品牌先用起来”，那 MVP 不该做太重。
我建议定义一个 **Commercial Pilot MVP**：

### 必须有

* 一个品牌一个工作区
* 品牌画像/规则配置
* 热点雷达
* 卖点编译
* 主图/前3秒生成
* 小红书发布
* 自动数据回采
* 测试结果判断
* 高表现资产归档

### 不必须有

* 复杂实验设计
* 多平台
* 高级 BI
* 广告联动
* 太重的审批系统

---

