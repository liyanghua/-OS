# System Architecture

## 1. 总体分层

系统采用五层结构：

1. Human Decision Layer
2. Decision Brain Layer
3. Scenario Agent Layer
4. Execution and Automation Layer
5. Real-time Update Layer

---

## 2. Human Decision Layer

这是管理前台层，面向四类角色：

- CEO Command Center
- Product R&D Director Desk
- Growth Director Desk
- Visual Strategy Desk

这一层不负责具体执行，而负责：
- 目标设定
- 资源取舍
- 高风险审批
- 低置信度判断
- 组织学习

---

## 3. Decision Brain Layer

经营大脑是系统核心编译层，不是聊天 UI。

建议在前端原型中体现以下能力模块：

- Goal Interpreter
- Context Compiler
- Decision Generator
- Evidence & Confidence Engine
- Review & Attribution Engine
- Asset Retrieval & Capture Engine

前端需要把这些能力体现为：
- Pulse cards
- Decision cards
- Evidence panels
- Confidence / risk labels
- Review-to-asset panels

---

## 4. Scenario Agent Layer

场景 Agent 按生命周期推进项目。

建议至少抽象以下 Agent：

- Opportunity Agent
- New Product Agent
- Diagnosis Agent
- Content Strategy Agent
- Visual Strategy Agent
- Execution Agent
- Upgrade Agent
- Review Capture Agent
- Governance Agent
- Data Observer Agent

前端需要能展示：
- 当前活跃 Agent
- Agent 状态
- Agent 最近动作
- Agent 是否等待人工接管
- Agent 关联的项目对象

---

## 5. Execution and Automation Layer

这是动作落地层，负责：
- 调用 runtime
- 调用业务系统
- 派发任务
- 自动执行低风险动作
- 执行日志记录
- 状态回写
- 风险告警
- 回滚

前端要体现为：
- Action Hub
- Governance Console
- Approval Queue
- Execution Feed
- Audit Trail

---

## 6. Real-time Update Layer

需要实时更新的对象：

- 项目健康度
- 生命周期状态
- 风险等级
- 待批动作
- Agent 状态
- 关键经营指标
- 阻塞状态

不要求实时更新的对象：

- 商品定义正文
- 视觉策略正文
- 复盘结论正文
- 资产详情页正文

---

## 7. 前端页面架构

前端分为三类页面：

### A. Management Frontend
- CEO Command Center
- Director Desks
- Lifecycle Overview
- Governance Console
- Review to Asset Loop

### B. Lifecycle Workspaces
- Opportunity Pool
- New Product Incubation
- Launch Validation
- Growth Optimization
- Legacy Upgrade
- Review & Capture

### C. Shared Hubs
- Project Object Page：is the primary collaboration and walkthrough surface across lifecycle stages and role views.
- Action Hub
- Asset Hub

---

## 8. 核心前端交互原则

1. Pulse-driven  
   首页和关键页面不是静态 dashboard，而是主动展示今日脉冲。

2. Exception-first  
   管理者优先看到例外、高风险、待批和阻塞，而不是普通任务。

3. Project-object-centered  
   所有重要交互最终落在项目对象上。

4. Lifecycle-driven  
   主结构按生命周期推进，而不是按部门或功能平铺。

5. Human-in-the-loop  
   高风险动作和低置信度建议必须可被人工审核和接管。

6. Review-to-asset-loop  
   复盘不是结束，必须可以沉淀为资产并被后续调用。

---

## 9. 技术实现建议（前端原型阶段）

建议采用：

- App shell + nested routes
- shared card components
- typed mock schemas
- mock state machine for lifecycle
- agent execution feed mock
- live status polling mock or local reactive state
- asset library mock data
- approval queue mock data

本阶段重点是：
- 架构表达清晰
- 状态流与对象模型正确
- 组件可复用
- 页面之间逻辑统一