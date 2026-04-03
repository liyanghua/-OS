# AI-native 经营操盘系统 - 整体交互设计原则与技巧

> 一套围绕商品生命周期运转的AI协同经营平台  
> 风格定位：Enterprise SaaS + AI-native + Palantir/Shopify Admin/Linear/Notion Enterprise

---

## 目录

1. [架构设计哲学](#一架构设计哲学)
2. [四层协同可视化](#二四层协同可视化)
3. [角色视图系统](#三角色视图系统)
4. [核心交互原则](#四核心交互原则)
5. [视觉设计系统](#五视觉设计系统)
6. [组件化策略](#六组件化策略)
7. [状态管理与数据流](#七状态管理与数据流)
8. [动画与微交互](#八动画与微交互)
9. [导航与路由](#九导航与路由)
10. [信息架构](#十信息架构)
11. [响应式与适配](#十一响应式与适配)
12. [技术栈与工具链](#十二技术栈与工具链)

---

## 一、架构设计哲学

### 1.1 四层协同架构可视化

系统围绕**四层协同架构**构建，每层都有明确的视觉表达：

```
┌─────────────────────────────────────────────────────────┐
│  👤 人类决策层 (Human Decision Layer)                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  • 视觉标识：按钮组、琥珀色高亮、"需决策"Badge              │
│  • 交互：点击批准/拒绝、手动选择方案                        │
│  • 场景：商品定义方案选择、高风险项目审批                    │
└─────────────────────────────────────────────────────────┘
         ↓ 下达指令
┌─────────────────────────────────────────────────────────┐
│  🧠 经营大脑层 (Decision Brain Layer)                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  • 视觉标识：Brain图标 + 蓝色渐变背景 + 置信度%             │
│  • 交互：只读展示、参考建议                                │
│  • 场景：每日脉冲摘要、AI推荐方案、风险预警                 │
└─────────────────────────────────────────────────────────┘
         ↓ 生成策略
┌─────────────────────────────────────────────────────────┐
│  🤖 场景Agent层 (Agent Orchestration Layer)               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  • 视觉标识：AgentStatusIndicator（脉冲动画）              │
│  • 交互：实时状态观察、Agent日志查看                        │
│  • 场景：打样跟踪Agent、供应商对接Agent、数据分析Agent      │
└─────────────────────────────────────────────────────────┘
         ↓ 执行动作
┌─────────────────────────────────────────────────────────┐
│  ⚙️ 执行自动化层 (Automation Execution Layer)            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  • 视觉标识：实时更新时间戳、自动刷新标识                    │
│  • 交互：无需人工干预、后台自动运行                         │
│  • 场景：数据采集、报告生成、通知推送                       │
└─────────────────────────────────────────────────────────┘
```

**设计要点：**
- 每层用不同的**颜色温度**区分（人类=暖色、AI=冷色）
- 决策流向从上至下，信息流向从下至上
- 层级切换通过**渐进式展开**实现（不是页面跳转）

---

### 1.2 三大核心特性

#### **1.2.1 Pulse-Driven UI（脉冲驱动界面）**

**原理：** 系统主动推送最重要的信息，而非等待用户查找

**实现技巧：**
```tsx
// 顶部脉冲区始终占据视觉焦点
<div className="grid grid-cols-12 gap-4">
  {/* 左侧：AI摘要（col-span-7） - 最大信息密度 */}
  <div className="col-span-7 bg-gradient-to-br from-blue-500/10 ...">
    <Brain icon /> {summary}
  </div>
  
  {/* 右侧：Top 3关键指标（col-span-5） - 快速扫描 */}
  <div className="col-span-5 grid grid-cols-3 gap-3">
    <KPI value={topOpportunities} status="success" />
    <KPI value={pendingDecisions} status="warning" />
    <KPI value={riskProjects} status="error" />
  </div>
</div>
```

**视觉特征：**
- ✅ 渐变背景突出（`from-blue-500/10 via-purple-500/5`）
- ✅ PulseIndicator动画（`animate-pulse` + `animate-ping`）
- ✅ 实时更新时间戳（"3分钟前更新"）
- ✅ 数字用`text-2xl`放大（87 → 87分）

---

#### **1.2.2 Exception-First Management（异常优先管理）**

**原理：** 没有问题的项目不需要关注，只看风险和阻塞

**视觉编码规则：**

| 状态 | 背景色 | 边框 | 排序 | 示例 |
|------|--------|------|------|------|
| **严重风险** | `bg-red-500/5` | `border-red-500/30` | 最前 | 质量问题导致延期 |
| **高风险** | `bg-amber-500/5` | `border-amber-500/30` | 第二 | 成本超预算20% |
| **阻塞中** | `bg-amber-500/5` | `border-amber-500/30` | 第三 | 等待供应商确认 |
| **待决策** | `bg-blue-500/5` | `border-blue-500/30` | 第四 | 需要人工选择方案 |
| **正常运行** | `bg-zinc-900/30` | `border-zinc-800` | 最后 | 按计划推进中 |

**交互技巧：**
```tsx
// 异常项自动置顶
const sortedItems = items.sort((a, b) => {
  const priorityMap = { critical: 4, high: 3, medium: 2, low: 1 };
  return priorityMap[b.severity] - priorityMap[a.severity];
});

// 异常项带脉冲提示
{item.severity === 'critical' && (
  <PulseIndicator status="error" />
)}
```

---

#### **1.2.3 Decision Object-Oriented（决策对象化）**

**原理：** 一切围绕"决策对象"而非"任务列表"

**对象类型体系：**

```
决策对象类型
├─ 商业机会对象
│  ├─ 属性：评分、潜力、信号源、AI置信度
│  ├─ 行为：立项、转入机会池、标记观察
│  └─ 决策点：是否启动孵化？
│
├─ 新品项目对象
│  ├─ 属性：进度、预算、负责人、Agent状态
│  ├─ 行为：推进阶段、更新定义、风险预警
│  └─ 决策点：方案A/B/C选哪个？
│
├─ 打样任务对象
│  ├─ 属性：供应商、轮次、质量问题、预计交付
│  ├─ 行为：质检、修改、备选方案切换
│  └─ 决策点：继续优化还是换供应商？
│
└─ 升级机会对象
   ├─ 属性：当前状态、用户反馈、预期影响
   ├─ 行为：重新定义、容量升级、停产
   └─ 决策点：升级方向是什么？
```

**视觉表达：**
- 每个对象是一个**完整的卡片**（而非表格一行）
- 对象内部包含**完整的上下文信息**（不需要跳转查看）
- 决策点用**视觉锚点**标识（按钮组、高亮区域）

---

## 二、四层协同可视化

### 2.1 人类决策层

**设计目标：** 让决策者清晰看到"这是需要我决策的"

#### **视觉标识体系**

| 决策类型 | 视觉特征 | 交互元素 | 示例场景 |
|----------|----------|----------|----------|
| **方案选择** | 按钮组 + 对比表格 | 单选/多选 | 商品定义A/B/C方案 |
| **批准/否决** | 双按钮 + 琥珀色背景 | 批准/需修改 | 立项审批、打样验收 |
| **风险确认** | 确认对话框 + 影响说明 | 确认继续/暂停 | 成本超预算决策 |
| **优先级排序** | 拖拽排序 | Drag & Drop | 项目优先级调整 |

#### **决策信息完整性**

每个决策点必须包含：
```tsx
<DecisionCard>
  {/* 1. 决策问题 */}
  <Question>商品定义需要选择方案</Question>
  
  {/* 2. 背景上下文 */}
  <Context>
    市场机会：高端办公场景空位
    目标用户：25-35岁白领
  </Context>
  
  {/* 3. 备选项对比 */}
  <Options>
    <Option score={92}>方案A：高性价比路线</Option>
    <Option score={88}>方案B：高端精品路线</Option>
    <Option score={75}>方案C：细分场景路线</Option>
  </Options>
  
  {/* 4. AI建议（可选） */}
  <AIRecommendation confidence={95}>
    强烈推荐方案A，性价比+用户画像匹配度最高
  </AIRecommendation>
  
  {/* 5. 决策按钮 */}
  <Actions>
    <Button variant="secondary">需要修改</Button>
    <Button variant="primary">批准立项</Button>
  </Actions>
</DecisionCard>
```

---

### 2.2 经营大脑层

**设计目标：** 展示AI的"思考过程"而非只给结果

#### **AI内容标识规范**

**强制规则：**
1. ✅ 所有AI生成内容必须带`<Brain />`图标
2. ✅ 必须显示置信度百分比（AI Confidence: 92%）
3. ✅ 必须标注数据来源（Market Intelligence / Competitor Analysis）
4. ✅ 必须有生成时间（"2小时前生成"）

**视觉模板：**
```tsx
<AIContentBlock>
  {/* 标题栏 */}
  <Header>
    <Brain className="w-4 h-4 text-blue-400" />
    <Title>AI 生成的商机摘要</Title>
    <Badge>AI 置信度 95%</Badge>
  </Header>
  
  {/* 内容区 - 蓝色渐变背景 */}
  <Content className="bg-gradient-to-br from-blue-500/10 via-purple-500/5 to-transparent">
    {aiGeneratedText}
  </Content>
  
  {/* 数据溯源 */}
  <Source>
    基于：市场趋势分析 + 竞品监测 + 用户反馈
  </Source>
  
  {/* 人工反馈（可选） */}
  <Feedback>
    <CheckCircle2 /> 已采纳
  </Feedback>
</AIContentBlock>
```

#### **置信度可视化**

不同置信度等级的视觉表达：

| 置信度 | 颜色 | 推荐强度 | 行动建议 |
|--------|------|----------|----------|
| **95%+** | `text-blue-400` | 强烈推荐 ⭐⭐⭐ | 可直接采纳 |
| **85-94%** | `text-cyan-400` | 推荐 ⭐⭐ | 建议采纳 |
| **75-84%** | `text-zinc-400` | 中立 ⭐ | 谨慎参考 |
| **<75%** | `text-amber-400` | 存疑 ⚠️ | 需人工复核 |

---

### 2.3 场景Agent层

**设计目标：** 让用户知道"有个Agent在帮我做这件事"

#### **AgentStatusIndicator 状态机**

```tsx
export type AgentStatus = 
  | 'idle'              // 待命中 - 灰色
  | 'thinking'          // 思考中 - 蓝色 + Brain图标旋转
  | 'executing'         // 执行中 - 绿色 + Loader2旋转
  | 'waiting-approval'  // 等待审批 - 琥珀色 + 脉冲动画
  | 'error';            // 异常 - 红色
```

**视觉实现：**
```tsx
<AgentStatusIndicator 
  status="executing" 
  label="正在对接供应商" 
  size="md" 
/>
// 渲染结果：
// [旋转的Loader图标] 执行中
// 带绿色背景、绿色边框、旋转动画
```

#### **Agent工作日志可视化**

```tsx
<AgentLog>
  <LogEntry timestamp="14:23:47">
    <Brain className="animate-spin" />
    正在分析供应商A的报价...
  </LogEntry>
  <LogEntry timestamp="14:24:12">
    <CheckCircle2 className="text-green-400" />
    已完成对比分析（供应商A vs B）
  </LogEntry>
  <LogEntry timestamp="14:24:35">
    <AlertCircle className="text-amber-400" />
    发现风险：供应商A交期延长3天
  </LogEntry>
</AgentLog>
```

---

### 2.4 执行自动化层

**设计目标：** 让用户感知到"系统在自动运行"

#### **实时更新标识**

```tsx
<RealtimeIndicator>
  <PulseIndicator status="active" size="sm" />
  <span className="text-xs text-zinc-400">实时更新</span>
  <span className="text-xs text-zinc-600">2026-03-31 14:23:47</span>
</RealtimeIndicator>
```

#### **自动刷新策略**

| 数据类型 | 刷新频率 | 视觉反馈 |
|----------|----------|----------|
| **关键指标** | 5秒 | PulseIndicator常亮 |
| **Agent状态** | 10秒 | 状态badge更新 |
| **项目进度** | 30秒 | Progress bar动画 |
| **历史数据** | 不刷新 | 无实时标识 |

---

## 三、角色视图系统

### 3.1 四种角色架构

系统支持**4种角色**，每种角色有**专属视图**：

```tsx
// 角色切换器 - 顶部导航栏
<RoleSwitcher>
  <Role id="ceo" label="老板视图" icon={User} color="purple-pink" />
  <Role id="product" label="产品研发总监" icon={Rocket} color="blue-cyan" />
  <Role id="operations" label="运营与营销总监" icon={TrendingUp} color="green-emerald" />
  <Role id="design" label="视觉总监" icon={Palette} color="orange-red" />
</RoleSwitcher>
```

**设计原则：**
- 角色切换**不刷新页面**（使用Context状态管理）
- 每个角色有**独立的首页Dashboard**
- 共享的页面（如生命周期页）根据角色**动态调整信息密度**

---

### 3.2 角色视图差异对比表

| 维度 | 老板视图 | 产品研发总监 | 运营营销总监 | 视觉总监 |
|------|----------|--------------|--------------|----------|
| **关注重点** | 整体经营健康度 | 新品孵化进度 | 增长引擎效率 | 视觉资产质量 |
| **脉冲内容** | 营收/利润/风险 | 商机/立项/打样 | 流量/转化/ROI | 创意产出/视觉规范 |
| **数据粒度** | 汇总指标 | 单品详情 | 渠道细分 | 设计评审 |
| **决策频次** | 低频高影响 | 高频中影响 | 中频中影响 | 低频低影响 |
| **Agent类型** | 战略Agent | 产品Agent | 增长Agent | 创意Agent |

---

### 3.3 角色视图实现技巧

#### **3.3.1 路由分发策略**

```tsx
// HomePage.tsx - 基于角色动态渲染
export function HomePage() {
  const { currentRole } = useApp();

  if (currentRole === 'ceo') return <CEODashboard />;
  if (currentRole === 'product') return <ProductDirectorDashboard />;
  if (currentRole === 'operations') return <OperationsDashboard />;
  if (currentRole === 'design') return <DesignDashboard />;
}
```

#### **3.3.2 共享数据源 + 差异化视图**

```tsx
// 同一份数据，不同角色看到不同维度
import { mockProductPipeline } from '@/data/mockData';

// 产品研发总监：关注阶段分布
<PipelineKanban data={mockProductPipeline} groupBy="stage" />

// 老板视图：关注健康度分布
<PipelineOverview data={mockProductPipeline} groupBy="health" />

// 运营总监：关注转化漏斗
<ConversionFunnel data={mockProductPipeline} groupBy="conversion" />
```

---

## 四、核心交互原则

### 4.1 信息渐进式呈现

**原则：** 3秒看清概览，30秒看清细节，3分钟看清全貌

#### **三级信息架构**

```
Level 1: 脉冲摘要（顶部）
  ↓ 3秒快速扫描
  • Top 3 商机：92分、89分、87分
  • Top 3 风险：质量问题、成本超预算、延期
  • Top 3 待决策：方案选择、立项审批、升级方向
  
Level 2: 卡片概览（中部）
  ↓ 30秒浏览关键信息
  • 机会池：4个机会 x (评分+信号+AI建议)
  • 孵化看板：5列 x 2-3个项目
  • 风险列表：3个风险项 x (描述+影响+备选方案)
  
Level 3: 详情展开（底部/弹窗）
  ↓ 3分钟深入研究
  • 商品定义：A/B/C方案完整对比
  • AI大脑状态：正在分析的任务 + 历史案例
  • 升级机会：用户反馈 + 预期影响 + 投入预算
```

**交互技巧：**
- 不使用"点击查看更多"（破坏扫描流）
- 使用**可展开卡片**（`<Collapsible>`）
- 使用**悬浮提示**（`<Tooltip>`）展示次要信息

---

### 4.2 零学习成本设计

**原则：** 不需要培训，直接上手使用

#### **自解释界面**

每个UI元素都必须回答3个问题：
1. **这是什么？** → 图标 + 标签
2. **状态如何？** → 颜色 + Badge
3. **下一步做什么？** → 按钮/行动提示

**实例：**
```tsx
<OpportunityCard>
  {/* 1. 这是什么 */}
  <Title>
    <Lightbulb /> 高端办公场景空位
    <Badge>趋势机会</Badge>
  </Title>
  
  {/* 2. 状态如何 */}
  <Score>92分</Score>
  <Status>
    <Badge variant="default">待审批立项</Badge>
  </Status>
  
  {/* 3. 下一步做什么 */}
  <AIRecommendation>
    建议：立即启动商品定义
  </AIRecommendation>
  <Actions>
    <Button>批准立项</Button>
  </Actions>
</OpportunityCard>
```

---

### 4.3 一致性交互语言

#### **全局交互模式统一**

| 交互 | 触发方式 | 视觉反馈 | 应用场景 |
|------|----------|----------|----------|
| **查看详情** | 点击卡片 | 卡片展开/跳转 | 项目详情、机会详情 |
| **快速操作** | 悬停显示按钮 | 按钮淡入 | 删除、编辑、分享 |
| **批量操作** | 多选复选框 | 底部工具栏出现 | 批量审批、批量导出 |
| **拖拽排序** | 长按拖动 | 卡片半透明 + 虚线框 | 优先级调整、看板移动 |
| **搜索过滤** | 输入框 + 筛选器 | 实时高亮匹配 | 机会池搜索、项目筛选 |

---

### 4.4 减少确认弹窗

**原则：** 可逆操作不需要确认，不可逆操作才弹窗

#### **操作分级策略**

```tsx
// 低风险操作：直接执行 + Toast提示
<button onClick={() => {
  markAsWatched(opportunityId);
  toast.success('已标记为观察中');
}}>
  标记观察
</button>

// 中风险操作：Inline确认
<button onClick={() => setShowInlineConfirm(true)}>
  删除草稿
</button>
{showInlineConfirm && (
  <InlineConfirm onConfirm={handleDelete} />
)}

// 高风险操作：模态对话框
<AlertDialog>
  <AlertDialogTrigger>删除项目</AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogTitle>确认删除项目？</AlertDialogTitle>
    <AlertDialogDescription>
      此操作不可撤销，将删除所有关联数据
    </AlertDialogDescription>
    <AlertDialogActions>
      <AlertDialogCancel>取消</AlertDialogCancel>
      <AlertDialogAction>确认删除</AlertDialogAction>
    </AlertDialogActions>
  </AlertDialogContent>
</AlertDialog>
```

---

## 五、视觉设计系统

### 5.1 颜色系统（语义化）

#### **主色板（9色）**

```css
/* AI & 系统色 */
--color-ai: #3b82f6;          /* 蓝色 - AI生成内容 */
--color-brain: #8b5cf6;       /* 紫色 - 经营大脑 */

/* 状态色 */
--color-success: #10b981;     /* 绿色 - 成功/机会/增长 */
--color-warning: #f59e0b;     /* 琥珀色 - 警告/待决策 */
--color-error: #ef4444;       /* 红色 - 错误/严重风险 */

/* 功能色 */
--color-info: #06b6d4;        /* 青色 - 信息提示 */
--color-neutral: #71717a;     /* 锌色 - 辅助文本 */

/* 角色色 */
--color-ceo: #a855f7;         /* 紫粉渐变 */
--color-product: #3b82f6;     /* 蓝青渐变 */
--color-operations: #10b981;  /* 绿翠渐变 */
--color-design: #f97316;      /* 橙红渐变 */
```

#### **透明度规范**

| 透明度 | 用途 | 示例 |
|--------|------|------|
| `/5` | 最轻微背景 | 风险警告背景 |
| `/10` | 提示框背景 | AI建议框 |
| `/20` | 边框强调 | 高优先级边框 |
| `/30` | 卡片背景 | 标准卡片 |
| `/50` | 内嵌卡片 | 嵌套信息块 |
| `/80` | 遮罩层 | 对话框遮罩 |

---

### 5.2 文字系统（8级）

| 级别 | Class | 大小 | 用途 | 字重 |
|------|-------|------|------|------|
| **超大** | `text-3xl` | 30px | 页面标题 | `font-semibold` |
| **特大** | `text-2xl` | 24px | 关键数字 | `font-semibold` |
| **大号** | `text-xl` | 20px | 区块标题 | `font-semibold` |
| **中号** | `text-lg` | 18px | 卡片标题 | `font-semibold` |
| **标准** | `text-sm` | 14px | 正文内容 | `font-normal` |
| **小号** | `text-xs` | 12px | 辅助信息 | `font-normal` |
| **极小** | `text-[10px]` | 10px | Badge文字 | `font-normal` |
| **微小** | `text-[8px]` | 8px | 极次要信息 | `font-normal` |

**注意：** 不使用`font-bold`，保持enterprise克制感

---

### 5.3 间距系统（节奏）

```css
/* Tailwind Spacing Scale（4px基准） */
space-y-1   /* 4px   - 最小间距（内联元素） */
space-y-2   /* 8px   - 列表项间距 */
space-y-3   /* 12px  - 小卡片间距 */
space-y-4   /* 16px  - 标准卡片间距 */
space-y-6   /* 24px  - 区块间距 */
space-y-8   /* 32px  - 大区块间距 */

/* 内边距规范 */
p-2         /* 8px   - 小信息块 */
p-3         /* 12px  - 次级卡片 */
p-4         /* 16px  - 标准卡片 */
p-5         /* 20px  - 重要卡片 */
p-6         /* 24px  - 页面容器 */
```

**节奏公式：** 元素重要性 ∝ 间距大小

---

### 5.4 圆角系统

```css
rounded-full  /* 完全圆形 - 头像、指示器 */
rounded-xl    /* 12px - 主区块、特殊强调 */
rounded-lg    /* 10px - 标准卡片 */
rounded-md    /* 6px  - 按钮、输入框 */
rounded       /* 4px  - 小组件、Badge */
```

**设计理念：** 圆角大小 = 视觉层级

---

### 5.5 阴影系统

```css
/* 不使用传统阴影，改用边框+背景模拟深度 */

/* Level 1: 平面卡片 */
border border-zinc-800 bg-zinc-900/30

/* Level 2: 悬浮卡片 */
border border-zinc-700 bg-zinc-900/50

/* Level 3: 聚焦卡片 */
border border-blue-500/30 bg-blue-500/5

/* Level 4: 模态对话框 */
border border-zinc-800 bg-zinc-950 backdrop-blur-xl
```

**为什么不用阴影？**  
→ 深色主题下阴影不明显，边框+半透明背景更清晰

---

## 六、组件化策略

### 6.1 核心UI组件库

系统基于**Radix UI + shadcn/ui**构建，自定义了以下核心组件：

#### **6.1.1 状态指示器**

| 组件 | 用途 | Props | 状态类型 |
|------|------|-------|----------|
| **PulseIndicator** | 系统运行状态 | `status`, `size` | active, warning, error, idle |
| **AgentStatusIndicator** | Agent工作状态 | `status`, `label`, `size` | idle, thinking, executing, waiting-approval, error |
| **Badge** | 标签/分类 | `variant`, `children` | default, outline, destructive, secondary |
| **Progress** | 进度条 | `value`, `className` | 0-100数值 |

**使用示例：**
```tsx
// 实时脉冲
<PulseIndicator status="active" size="md" />

// Agent状态
<AgentStatusIndicator 
  status="executing" 
  label="正在分析供应商报价" 
  size="md" 
/>

// 标签
<Badge variant="outline" className="text-xs">
  <Sparkles className="w-3 h-3 mr-1" />
  AI 生成
</Badge>

// 进度
<Progress value={72} className="h-1" />
```

---

#### **6.1.2 卡片布局组件**

```tsx
// 标准卡片模板
<Card className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4">
  <CardHeader>
    <CardTitle>商品定义</CardTitle>
    <CardDescription>AI生成3个方案</CardDescription>
  </CardHeader>
  <CardContent>
    {/* 主要内容 */}
  </CardContent>
  <CardFooter>
    <Button>批准立项</Button>
  </CardFooter>
</Card>
```

---

#### **6.1.3 数据展示组件**

| 组件 | 用途 | 适用场景 |
|------|------|----------|
| **Table** | 结构化数据 | 项目列表、历史记录 |
| **Accordion** | 可折叠内容 | FAQ、详细配置 |
| **Tabs** | 视图切换 | 多维度数据（日/周/月） |
| **Collapsible** | 可展开区块 | 详细描述、完整日志 |

---

### 6.2 自定义业务组件

#### **6.2.1 RoleSwitcher（角色切换器）**

```tsx
// 位置：顶部导航栏中央
<RoleSwitcher>
  {roles.map(role => (
    <RoleButton 
      key={role.id}
      active={currentRole === role.id}
      onClick={() => setCurrentRole(role.id)}
    >
      <role.icon />
      {role.label}
    </RoleButton>
  ))}
</RoleSwitcher>
```

**交互特性：**
- 激活角色有**渐变背景高亮**（`bg-gradient-to-r opacity-20`）
- 切换时**不刷新页面**（Context状态管理）
- 有**颜色区分**（CEO紫粉、产品蓝青、运营绿翠、设计橙红）

---

#### **6.2.2 MainLayout（主布局）**

```tsx
<MainLayout>
  {/* 顶部导航栏 - fixed */}
  <Header>
    <Logo />
    <RoleSwitcher />
    <UserActions />
  </Header>
  
  {/* 侧边栏 - fixed */}
  <Sidebar>
    <Navigation />
    <SystemStatus />
  </Sidebar>
  
  {/* 主内容区 - 滚动 */}
  <Main>
    <Outlet /> {/* React Router 6+ */}
  </Main>
</MainLayout>
```

**布局特性：**
- 顶部栏高度：`h-16`（64px）
- 侧边栏宽度：`w-64`（256px）
- 主内容区：`ml-64 mt-16`（留出侧边栏和顶栏空间）
- 背景：`bg-black`（纯黑） + `backdrop-blur-xl`（毛玻璃）

---

#### **6.2.3 ProjectCard（项目卡片）**

```tsx
<ProjectCard project={project}>
  <ProjectHeader>
    <ProjectName>{project.name}</ProjectName>
    <ProjectStatus status={project.status} />
  </ProjectHeader>
  
  <ProjectMetrics>
    <Metric label="进度" value={project.progress} unit="%" />
    <Metric label="健康度" value={project.health} />
  </ProjectMetrics>
  
  <ProjectAgent>
    <AgentStatusIndicator status={project.agentStatus} />
  </ProjectAgent>
  
  <ProjectActions>
    <Button variant="ghost" size="sm">详情</Button>
  </ProjectActions>
</ProjectCard>
```

---

### 6.3 组件命名规范

```
组件类型前缀
├─ UI组件（无前缀）: Button, Badge, Card
├─ 业务组件（领域名）: ProjectCard, OpportunityPool
├─ 布局组件（Layout后缀）: MainLayout, SidebarLayout
├─ 页面组件（Page后缀）: HomePage, ProjectDetailPage
└─ 工具组件（Helper/Util后缀）: DateFormatter, CurrencyFormatter
```

---

## 七、状态管理与数据流

### 7.1 Context状态管理

#### **AppContext（全局状态）**

```tsx
// 管理角色切换状态
interface AppContextType {
  currentRole: Role;
  setCurrentRole: (role: Role) => void;
}

// 使用示例
const { currentRole, setCurrentRole } = useApp();
```

**为什么不用Redux/Zustand？**  
→ 系统状态简单（只有角色切换），Context足够

---

### 7.2 数据层架构

#### **Mock Data分层**

```
/src/app/data/mockData.ts
├─ 基础数据类型
│  ├─ mockProjects: Project[]
│  ├─ mockSignals: Signal[]
│  ├─ mockActionItems: ActionItem[]
│  └─ mockAgents: Agent[]
│
├─ CEO视图数据
│  ├─ mockDailySummary
│  ├─ mockCampaigns
│  ├─ mockGrowthEngines
│  ├─ mockResourceAllocation
│  ├─ mockHighRiskApprovals
│  └─ mockEfficiencyMetrics
│
└─ 产品研发总监数据
   ├─ mockProductOpportunityPulse
   ├─ mockOpportunityPool
   ├─ mockProductPipeline
   ├─ mockProductDefinitions
   ├─ mockSamplingRisks
   ├─ mockUpgradeOpportunities
   └─ mockProductAIBrain
```

**数据复用原则：**
- 基础数据（Projects, Agents）所有角色共用
- 视图特定数据（DailySummary, OpportunityPulse）按角色划分
- 通过**数据筛选**和**视图映射**实现差异化展示

---

### 7.3 数据流向图

```
                    ┌──────────────────┐
                    │   Mock Data      │
                    │   (mockData.ts)  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Page Component  │
                    │  (HomePage.tsx)  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
      │ CEODashboard│ │   Product   │ │ Operations  │
      │             │ │  Dashboard  │ │  Dashboard  │
      └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
             │               │               │
      ┌──────▼───────────────▼───────────────▼──────┐
      │          Shared UI Components               │
      │  (AgentStatusIndicator, PulseIndicator...)  │
      └─────────────────────────────────────────────┘
```

---

## 八、动画与微交互

### 8.1 Tailwind动画类

```css
/* 系统内置动画 */
animate-pulse     /* 呼吸效果 - PulseIndicator */
animate-ping      /* 涟漪扩散 - 实时状态提示 */
animate-spin      /* 旋转 - Loading状态 */
animate-bounce    /* 弹跳 - 提示引导 */

/* 自定义过渡 */
transition-all
transition-colors
transition-opacity
transition-transform
```

---

### 8.2 微交互设计

#### **8.2.1 悬停反馈（Hover）**

```tsx
// 按钮悬停
<button className="hover:bg-zinc-700 transition-colors">
  批准立项
</button>

// 卡片悬停
<div className="hover:border-blue-500/30 hover:bg-blue-500/5 transition-all">
  机会卡片
</div>

// 链接悬停
<Link className="hover:text-blue-300 transition-colors">
  查看详情
</Link>
```

**时长规范：** 所有`transition-*`默认`duration-200`（200ms）

---

#### **8.2.2 状态切换动画**

```tsx
// Agent状态切换
<AgentStatusIndicator 
  status="executing" 
  className="transition-all duration-500"
/>
// 从 thinking → executing 时，颜色从蓝色渐变到绿色

// 进度条更新
<Progress 
  value={progress} 
  className="transition-all duration-1000 ease-out"
/>
// 进度从45% → 72% 时，平滑增长动画
```

---

#### **8.2.3 列表项入场动画（未来扩展）**

```tsx
// 使用Motion（原Framer Motion）
import { motion } from 'motion/react';

<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3 }}
>
  <OpportunityCard />
</motion.div>
```

---

### 8.3 性能优化原则

**避免过度动画：**
- ❌ 不要给大列表的所有项加入场动画（卡顿）
- ❌ 不要在滚动时触发动画（性能差）
- ✅ 只给关键操作加反馈动画（按钮点击、状态切换）
- ✅ 使用CSS动画而非JS动画（硬件加速）

---

## 九、导航与路由

### 9.1 路由架构

```tsx
// /src/app/routes.tsx
export const router = createBrowserRouter([
  {
    path: "/",
    Component: MainLayout,
    children: [
      // 首页 - 基于角色动态渲染
      { index: true, Component: HomePage },
      
      // 生命周期管理
      { path: "lifecycle", Component: LifecycleOverview },
      { path: "lifecycle/opportunity-pool", Component: OpportunityPool },
      { path: "lifecycle/new-product-incubation", Component: NewProductIncubation },
      { path: "lifecycle/launch-validation", Component: LaunchValidation },
      { path: "lifecycle/growth-optimization", Component: GrowthOptimization },
      { path: "lifecycle/upgrade-iteration", Component: UpgradeIteration },
      { path: "lifecycle/review-deposit", Component: ReviewDeposit },
      
      // 项目详情
      { path: "project/:id", Component: ProjectDetail },
      
      // 功能中台
      { path: "action-hub", Component: ActionHub },
      { path: "governance", Component: GovernanceHub },
      { path: "review-hub", Component: ReviewHub },
      { path: "assets", Component: AssetHub },
    ],
  },
]);
```

---

### 9.2 侧边栏导航

```tsx
const navigation = [
  { name: '智能首页', href: '/', icon: LayoutDashboard },
  { name: '生命周期', href: '/lifecycle', icon: GitBranch },
  { name: '动作中台', href: '/action-hub', icon: Zap, badge: 12 },
  { name: '治理台', href: '/governance', icon: Shield },
  { name: '复盘沉淀', href: '/review-hub', icon: Brain },
  { name: '资产中台', href: '/assets', icon: Database },
];
```

**激活状态判断：**
```tsx
const isActive = 
  location.pathname === item.href || 
  (item.href !== '/' && location.pathname.startsWith(item.href));
```

**视觉效果：**
- 激活项：`bg-zinc-800` + `text-white` + 蓝色渐变背景
- 未激活：`text-zinc-400` + `hover:text-white`
- 图标：激活时`text-blue-400`，否则继承文字颜色

---

### 9.3 面包屑导航（未来扩展）

```tsx
// 项目详情页面包屑
<Breadcrumb>
  <BreadcrumbItem>
    <Link to="/">首页</Link>
  </BreadcrumbItem>
  <BreadcrumbSeparator />
  <BreadcrumbItem>
    <Link to="/lifecycle/new-product-incubation">新品孵化</Link>
  </BreadcrumbItem>
  <BreadcrumbSeparator />
  <BreadcrumbItem active>
    智能穿戴-运动手环 Pro
  </BreadcrumbItem>
</Breadcrumb>
```

---

## 十、信息架构

### 10.1 页面层级结构

```
系统信息架构
│
├─ Level 0: 全局导航（永久可见）
│  ├─ 顶部栏：Logo + RoleSwitcher + UserActions
│  └─ 侧边栏：主导航 + 系统状态
│
├─ Level 1: 智能首页（基于角色）
│  ├─ CEO视图：经营指挥台
│  ├─ 产品研发总监：产品研发指挥台
│  ├─ 运营营销总监：增长指挥台
│  └─ 视觉总监：创意指挥台
│
├─ Level 2: 生命周期管理
│  ├─ 机会池
│  ├─ 新品孵化
│  ├─ 首发验证
│  ├─ 增长优化
│  ├─ 升级迭代
│  └─ 复盘沉淀
│
├─ Level 3: 功能中台
│  ├─ 动作中台（待办事项）
│  ├─ 治理台（权限&流程）
│  ├─ 复盘沉淀（知识库）
│  └─ 资产中台（设计资产）
│
└─ Level 4: 详情页
   ├─ 项目详情
   ├─ 商品详情
   ├─ Agent详情
   └─ 复盘报告
```

---

### 10.2 信息密度分级

| 页面类型 | 信息密度 | 卡片密度 | 滚动方式 |
|----------|----------|----------|----------|
| **首页Dashboard** | 高 | 15-20个卡片 | 纵向滚动 |
| **生命周期看板** | 中 | 5-10列 | 横向+纵向 |
| **详情页** | 低 | 3-5个区块 | 纵向滚动 |
| **列表页** | 中高 | 表格形式 | 虚拟滚动 |

**密度控制技巧：**
- 高密度页面用`gap-4`（16px间距）
- 中密度页面用`gap-6`（24px间距）
- 低密度页面用`gap-8`（32px间距）

---

## 十一、响应式与适配

### 11.1 断点策略

```css
/* Tailwind默认断点 */
sm: 640px   /* 手机横屏 */
md: 768px   /* 平板竖屏 */
lg: 1024px  /* 平板横屏/小笔记本 */
xl: 1280px  /* 桌面显示器 */
2xl: 1536px /* 大屏显示器 */
```

**当前实现：**
- 主要针对**桌面端**（1280px+）
- 最大宽度限制：`max-w-[1800px]`（避免超宽屏信息过分散）

**未来扩展：**
```tsx
// 移动端适配示例
<div className="grid grid-cols-12 lg:grid-cols-12 md:grid-cols-6 sm:grid-cols-1 gap-4">
  {/* 桌面：12列，平板：6列，手机：1列 */}
</div>
```

---

### 11.2 信息优先级（移动端规划）

**移动端必保留：**
1. 顶部脉冲摘要（AI Summary）
2. Top 3 关键指标（商机/待决策/风险）
3. 待决策项列表（人工拍板点）
4. Agent状态监控

**移动端可折叠：**
- 机会池详细信号
- AI大脑历史案例
- 完整的统计图表

---

## 十二、技术栈与工具链

### 12.1 核心依赖

```json
{
  "核心框架": {
    "react": "18.3.1",
    "react-router": "7.13.0",
    "vite": "6.3.5"
  },
  
  "UI组件库": {
    "@radix-ui/react-*": "最新版",
    "lucide-react": "0.487.0",
    "recharts": "2.15.2"
  },
  
  "样式方案": {
    "tailwindcss": "4.1.12",
    "@tailwindcss/vite": "4.1.12"
  },
  
  "动画库": {
    "motion": "12.23.24"
  },
  
  "工具库": {
    "clsx": "2.1.1",
    "tailwind-merge": "3.2.0",
    "date-fns": "3.6.0"
  }
}
```

---

### 12.2 工具函数

#### **12.2.1 cn() - 条件类名合并**

```tsx
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 使用示例
<div className={cn(
  "base-class",
  isActive && "active-class",
  "hover:bg-zinc-700"
)}>
```

---

#### **12.2.2 格式化工具**

```tsx
// 货币格式化
export const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(value);
};

// 相对时间
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';

export const formatRelativeTime = (date: Date) => {
  return formatDistanceToNow(date, { 
    addSuffix: true, 
    locale: zhCN 
  });
};
```

---

### 12.3 构建配置

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': '/src/app',
    },
  },
});
```

---

## 十三、设计原则总结

### 13.1 十大核心原则

| 原则 | 说明 | 实现方式 |
|------|------|----------|
| **1. AI可见性** | AI生成的内容必须标识 | Brain图标 + 置信度 + 数据来源 |
| **2. 异常优先** | 风险和阻塞优先展示 | 红色/琥珀色背景 + 置顶排序 |
| **3. 决策导向** | 围绕决策对象而非任务 | 卡片式布局 + 完整上下文 |
| **4. 渐进式呈现** | 3秒看概览，3分钟看全貌 | 脉冲→卡片→详情 三级架构 |
| **5. 零学习成本** | 不需要培训直接使用 | 自解释界面 + 图标标签 |
| **6. 一致性语言** | 全局交互模式统一 | 统一的组件库 + 交互规范 |
| **7. 克制的美学** | Enterprise SaaS气质 | 深色主题 + 低饱和度 + font-semibold |
| **8. 实时反馈** | 系统状态透明可感知 | PulseIndicator + 实时时间戳 |
| **9. 可逆操作** | 减少确认弹窗 | 低风险直接执行 + Toast提示 |
| **10. 角色视图** | 每个角色看到不同信息 | RoleSwitcher + 动态路由 |

---

### 13.2 设计检查清单

在设计新功能时，问自己这些问题：

#### **信息呈现**
- [ ] 是否有AI生成的内容？→ 加Brain图标 + 置信度
- [ ] 是否有风险/阻塞？→ 用红色/琥珀色标识
- [ ] 用户能在3秒内看懂这是什么吗？→ 加图标 + 标签
- [ ] 数字是否足够突出？→ 用`text-2xl` + `font-semibold`

#### **交互设计**
- [ ] 这是决策点吗？→ 加按钮组 + 完整上下文
- [ ] 是否需要确认弹窗？→ 只有高风险操作才弹
- [ ] 是否有悬停反馈？→ 加`hover:`状态 + `transition-colors`
- [ ] 是否有实时更新？→ 加PulseIndicator + 时间戳

#### **视觉层次**
- [ ] 颜色是否符合语义？→ 蓝=AI，绿=机会，红=风险
- [ ] 间距是否符合重要性？→ 重要元素用更大��距
- [ ] 圆角是否符合层级？→ 主区块用`rounded-xl`
- [ ] 是否有Agent状态？→ 加AgentStatusIndicator

#### **角色适配**
- [ ] 不同角色看到的信息是否合理？→ 检查数据筛选逻辑
- [ ] 是否有角色专属颜色？→ CEO紫、产品蓝、运营绿、设计橙

---

## 十四、未来扩展方向

### 14.1 短期优化（1-2个月）

1. **移动端适配** - 响应式布局 + 优先级信息筛选
2. **暗黑/浅色主题切换** - 增加浅色模式
3. **快捷键系统** - 键盘操作提效（Cmd+K 全局搜索）
4. **数据导出功能** - CSV/Excel/PDF报告导出
5. **通知中心** - 聚合所有提醒和待办

### 14.2 中期扩展（3-6个月）

1. **实时协作** - WebSocket实时同步
2. **高级筛选器** - 多维度组合筛选
3. **自定义仪表盘** - 用户可配置首页布局
4. **Agent对话界面** - 与Agent直接对话
5. **数据可视化增强** - 更多图表类型（Sankey、雷达图）

### 14.3 长期规划（6-12个月）

1. **多语言支持** - i18n国际化
2. **权限管理系统** - RBAC角色权限
3. **AI训练反馈** - 用户反馈改进AI模型
4. **第三方集成** - Slack/钉钉/飞书通知
5. **离线模式** - PWA支持

---

## 附录：快速参考表

### A. 颜色速查表

| 场景 | Tailwind Class | 示例 |
|------|----------------|------|
| AI内容背景 | `bg-blue-500/10` | AI建议框 |
| AI内容边框 | `border-blue-500/20` | AI边框 |
| 成功/机会 | `text-green-400` | Top商机、已完成 |
| 警告/待决策 | `text-amber-400` | 阻塞项目、待审批 |
| 错误/风险 | `text-red-400` | 严重风险、失败 |
| 辅助文本 | `text-zinc-500` | 时间戳、来源 |
| 卡片背景 | `bg-zinc-900/30` | 标准卡片 |
| 卡片边框 | `border-zinc-800` | 标准边框 |

### B. 文字大小速查表

| 用途 | Class | 大小 |
|------|-------|------|
| 页面标题 | `text-3xl` | 30px |
| 关键数字 | `text-2xl` | 24px |
| 区块标题 | `text-xl` | 20px |
| 正文 | `text-sm` | 14px |
| 辅助信息 | `text-xs` | 12px |
| Badge | `text-[10px]` | 10px |

### C. 间距速查表

| 用途 | Class | 大小 |
|------|-------|------|
| 区块间距 | `space-y-6` | 24px |
| 卡片间距 | `gap-4` | 16px |
| 列表项 | `space-y-2` | 8px |
| 卡片内边距 | `p-4` | 16px |

---

## 结语

这个AI-native经营操盘系统的交互设计，核心是围绕**四层协同架构**和**三大特性**（Pulse-Driven、Exception-First、Decision-Oriented）展开的。

通过**严谨的视觉层次**、**语义化的颜色系统**、**一致的交互语言**、**自解释的界面设计**，我们创造了一个既有Enterprise SaaS的专业克制感，又充分体现AI-native智能特征的产品。

最重要的是：**让复杂的经营决策变得简单、透明、高效**。
