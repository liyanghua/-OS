下面直接给你一版可用于 **产品设计 / 后端接口 / 前端实现 / AI-coding** 的：

# 《Council 升级后的返回 schema + SSE 事件协议 + 前端状态机 spec》

目标是把现在的 Council 从：

* 一次请求
* 主要依赖 `proposal.diff`
* 主区域整轮结束后才渲染

升级成：

## **一个可观察、可判断、可继续流转的 AI-native 咨询会话对象**

---

# 一、设计目标

Council 升级后必须同时满足 4 件事：

## 1. 可见

用户能看到：

* 哪些 Agent 参与
* 现在在做什么
* 谁说了什么
* 为什么形成这个结论

## 2. 可判

用户能判断：

* 这是可直接 apply 的
* 还是 advisory
* 还是存在分歧
* 还是上下文不足

## 3. 可操作

用户能继续做：

* Apply
* Apply as Draft
* Turn into Variant
* Escalate to Rewrite
* Ask follow-up

## 4. 可观测

系统能记录：

* 每个 Agent 的耗时
* 是否使用 LLM / 是否降级
* 哪个阶段失败
* 最终 proposal 是否可应用

---

# 二、Council 对象模型

建议正式引入一个顶层对象：

## `CouncilSession`

```json id="0qvffq"
{
  "session_id": "council_brief_20260410_001",
  "stage_type": "brief",
  "target_object_type": "OpportunityBrief",
  "target_object_id": "brief_123",
  "target_object_version": "v7",
  "opportunity_id": "opp_456",
  "question": "当前 Brief 更适合偏种草还是偏转化？",
  "run_mode": "standard",
  "participants": [
    {
      "agent_id": "trend_analyst",
      "display_name": "趋势分析师",
      "role_type": "specialist"
    },
    {
      "agent_id": "brief_synthesizer",
      "display_name": "Brief 编译师",
      "role_type": "specialist"
    },
    {
      "agent_id": "strategy_director",
      "display_name": "策略总监",
      "role_type": "specialist"
    }
  ],
  "status": "completed",
  "decision_type": "advisory",
  "applyability": "partial",
  "started_at": "2026-04-10T10:00:00Z",
  "finished_at": "2026-04-10T10:00:12Z",
  "timing_ms": 12340,
  "timing_breakdown": {
    "context_ms": 320,
    "specialists_ms": 6120,
    "synthesis_ms": 5100,
    "persist_ms": 800
  }
}
```

---

# 三、HTTP 返回 schema

建议 `POST /content-planning/stages/{stage_type}/{opportunity_id}/discussions` 返回以下结构。

## 顶层返回对象

```json id="5qwhnn"
{
  "session": { "...CouncilSession..." },
  "discussion": { "...DiscussionPayload..." },
  "proposal": { "...StageProposal..." },
  "observability": { "...CouncilObservability..." }
}
```

---

## 3.1 `discussion` schema

```json id="r9sxjt"
{
  "discussion_id": "disc_001",
  "session_id": "council_brief_20260410_001",
  "status": "completed",
  "summary": "委员会认为当前 Brief 更适合偏种草，但需补强价格价值表达后再进入转化模板。",
  "consensus": "优先保留场景种草方向，并补充低成本改造价值，不建议直接改成强转化口径。",
  "decision_type": "advisory",
  "applyability": "partial",
  "confidence": 0.82,

  "agreements": [
    "当前 Brief 的场景与风格表达适合种草内容",
    "互动信号显示该机会更偏收藏价值而非即时成交"
  ],
  "disagreements": [
    {
      "topic": "是否直接切换为转化模板",
      "agents_for": ["strategy_director"],
      "agents_against": ["trend_analyst", "brief_synthesizer"],
      "reason_summary": "支持方认为当前卖点具备转化潜力，反对方认为价格价值表达不足"
    }
  ],
  "open_questions": [
    "是否有更明确的价格带信息可支持转化表达"
  ],
  "recommended_next_steps": [
    {
      "action_type": "apply_as_draft",
      "label": "将“低成本改造价值”写入 planning_direction",
      "target_field": "planning_direction"
    },
    {
      "action_type": "turn_into_variant",
      "label": "基于“平价改造”方向生成一个新 Variant"
    }
  ],

  "messages": [
    {
      "message_id": "msg_1",
      "agent_id": "trend_analyst",
      "agent_name": "趋势分析师",
      "role_type": "specialist",
      "stance": "support_seed",
      "claim": "当前内容更适合种草而非直接转化",
      "full_text": "基于互动和场景信号，这条 Brief 更偏种草收藏型内容。",
      "references": ["interaction_insight", "target_scene"],
      "used_llm": true,
      "degraded": false,
      "started_at": "2026-04-10T10:00:01Z",
      "finished_at": "2026-04-10T10:00:03Z",
      "timing_ms": 1800
    },
    {
      "message_id": "msg_2",
      "agent_id": "brief_synthesizer",
      "agent_name": "Brief 编译师",
      "role_type": "specialist",
      "stance": "support_seed",
      "claim": "应强化 why_it_works 中的收藏价值逻辑",
      "full_text": "当前 Brief 已有较强场景与风格支撑，但 why_it_works 还未明确收藏型价值。",
      "references": ["why_it_works", "proof_blocks"],
      "used_llm": true,
      "degraded": false,
      "started_at": "2026-04-10T10:00:01Z",
      "finished_at": "2026-04-10T10:00:04Z",
      "timing_ms": 2400
    },
    {
      "message_id": "msg_3",
      "agent_id": "strategy_director",
      "agent_name": "策略总监",
      "role_type": "specialist",
      "stance": "support_convert",
      "claim": "可以探索一个平价改造的轻转化变体",
      "full_text": "如果补足价格价值表达，可以探索平价改造型转化方案。",
      "references": ["planning_direction", "core_selling_points"],
      "used_llm": true,
      "degraded": false,
      "started_at": "2026-04-10T10:00:01Z",
      "finished_at": "2026-04-10T10:00:05Z",
      "timing_ms": 3000
    }
  ]
}
```

---

## 3.2 `proposal` schema

注意：`proposal` 不应再只靠 `diff.changes` 决定有无价值。

```json id="t331b8"
{
  "proposal_id": "prop_001",
  "session_id": "council_brief_20260410_001",
  "status": "completed",
  "summary": "建议保留种草方向，并补充低成本改造价值表达。",
  "decision_type": "advisory",
  "applyability": "partial",

  "diff": {
    "changes": [
      {
        "field": "planning_direction",
        "before": "法式氛围感桌布种草",
        "after": "法式氛围感桌布种草 + 低成本改造价值表达",
        "change_type": "modify",
        "confidence": 0.84,
        "reason": "委员会一致认为需补充价格价值逻辑"
      }
    ]
  },

  "proposed_updates": {
    "planning_direction": "法式氛围感桌布种草 + 低成本改造价值表达"
  },

  "alternatives": [
    {
      "alternative_id": "alt_1",
      "label": "保守版：继续种草",
      "description": "保留场景与风格，不进入强转化",
      "proposed_updates": {
        "planning_direction": "继续强化场景种草与收藏价值"
      }
    },
    {
      "alternative_id": "alt_2",
      "label": "平衡版：种草 + 平价改造",
      "description": "加入低成本改造价值表达",
      "proposed_updates": {
        "planning_direction": "场景种草 + 平价改造价值"
      }
    },
    {
      "alternative_id": "alt_3",
      "label": "激进版：转化变体",
      "description": "生成一个偏转化的 Variant，不直接覆盖当前 Brief",
      "proposed_updates": {}
    }
  ],

  "fallback_action": {
    "type": "apply_as_draft",
    "target_field": "planning_direction",
    "content": "建议在现有 Brief 中增加低成本改造价值表达"
  }
}
```

---

## 3.3 `observability` schema

```json id="ekl2r1"
{
  "trace_id": "trace_council_001",
  "session_id": "council_brief_20260410_001",
  "model_summary": {
    "specialist_model": "qwen-max",
    "synthesis_model": "qwen-max",
    "llm_available": true
  },
  "agents": [
    {
      "agent_id": "trend_analyst",
      "used_llm": true,
      "degraded": false,
      "model": "qwen-max",
      "timing_ms": 1800,
      "output_quality": "ok"
    },
    {
      "agent_id": "brief_synthesizer",
      "used_llm": true,
      "degraded": false,
      "model": "qwen-max",
      "timing_ms": 2400,
      "output_quality": "ok"
    },
    {
      "agent_id": "strategy_director",
      "used_llm": true,
      "degraded": false,
      "model": "qwen-max",
      "timing_ms": 3000,
      "output_quality": "ok"
    }
  ],
  "synthesis": {
    "used_llm": true,
    "degraded": false,
    "timing_ms": 5100,
    "output_quality": "ok"
  }
}
```

---

# 四、SSE 事件协议

现在不要只推 `discussion_message` 和 `council_phase` 两种零散事件。
建议标准化为以下事件集。

---

## 4.1 事件总览

| event                           | 用途               |
| ------------------------------- | ---------------- |
| `council_session_started`       | Council 会话开始     |
| `council_phase_changed`         | 阶段切换             |
| `council_participant_started`   | 某 Agent 开始发言     |
| `council_participant_message`   | 某 Agent 的摘要/增量输出 |
| `council_participant_completed` | 某 Agent 完成       |
| `council_synthesis_started`     | 开始综合共识           |
| `council_synthesis_completed`   | 共识完成             |
| `council_proposal_ready`        | proposal 就绪      |
| `council_session_completed`     | 整场讨论完成           |
| `council_session_failed`        | 会话失败             |

---

## 4.2 事件 payload 设计

### 事件 1：`council_session_started`

```json id="g7svzh"
{
  "session_id": "council_brief_20260410_001",
  "stage_type": "brief",
  "target_object_id": "brief_123",
  "question": "当前 Brief 更适合偏种草还是偏转化？",
  "participants": [
    {"agent_id": "trend_analyst", "agent_name": "趋势分析师"},
    {"agent_id": "brief_synthesizer", "agent_name": "Brief 编译师"},
    {"agent_id": "strategy_director", "agent_name": "策略总监"}
  ],
  "started_at": "2026-04-10T10:00:00Z"
}
```

### 事件 2：`council_phase_changed`

```json id="mh6dr3"
{
  "session_id": "council_brief_20260410_001",
  "phase": "collecting_opinions",
  "label": "正在收集各角色观点",
  "at": "2026-04-10T10:00:01Z"
}
```

可选 phase 值：

* `collecting_opinions`
* `synthesizing_consensus`
* `building_proposal`
* `session_ready`

---

### 事件 3：`council_participant_started`

```json id="1gqcxg"
{
  "session_id": "council_brief_20260410_001",
  "agent_id": "trend_analyst",
  "agent_name": "趋势分析师",
  "status": "running",
  "at": "2026-04-10T10:00:01Z"
}
```

---

### 事件 4：`council_participant_message`

这个事件用于主区域和时间线逐步刷新。

```json id="mv6w31"
{
  "session_id": "council_brief_20260410_001",
  "agent_id": "trend_analyst",
  "agent_name": "趋势分析师",
  "stance": "support_seed",
  "claim": "当前内容更适合种草而非直接转化",
  "snippet": "基于互动和场景信号，这条 Brief 更偏种草收藏型内容。",
  "references": ["interaction_insight", "target_scene"],
  "sequence": 1,
  "at": "2026-04-10T10:00:02Z"
}
```

---

### 事件 5：`council_participant_completed`

```json id="kg9k4k"
{
  "session_id": "council_brief_20260410_001",
  "agent_id": "trend_analyst",
  "status": "completed",
  "used_llm": true,
  "degraded": false,
  "timing_ms": 1800,
  "at": "2026-04-10T10:00:03Z"
}
```

---

### 事件 6：`council_synthesis_started`

```json id="itvtlz"
{
  "session_id": "council_brief_20260410_001",
  "phase": "synthesizing_consensus",
  "label": "正在综合共识与分歧",
  "at": "2026-04-10T10:00:05Z"
}
```

---

### 事件 7：`council_synthesis_completed`

```json id="clqzgh"
{
  "session_id": "council_brief_20260410_001",
  "consensus": "优先保留场景种草方向，并补充低成本改造价值。",
  "decision_type": "advisory",
  "applyability": "partial",
  "agreements": [
    "当前 Brief 更适合种草",
    "需补充价格价值表达"
  ],
  "disagreements": [
    "是否直接切换到转化模板"
  ],
  "open_questions": [
    "是否有更明确价格带"
  ],
  "at": "2026-04-10T10:00:10Z"
}
```

---

### 事件 8：`council_proposal_ready`

```json id="q3cs3o"
{
  "session_id": "council_brief_20260410_001",
  "proposal_id": "prop_001",
  "decision_type": "advisory",
  "applyability": "partial",
  "diff_change_count": 1,
  "alternative_count": 3,
  "at": "2026-04-10T10:00:11Z"
}
```

---

### 事件 9：`council_session_completed`

```json id="x9q3i0"
{
  "session_id": "council_brief_20260410_001",
  "status": "completed",
  "timing_ms": 12340,
  "at": "2026-04-10T10:00:12Z"
}
```

---

### 事件 10：`council_session_failed`

```json id="n97era"
{
  "session_id": "council_brief_20260410_001",
  "status": "failed",
  "failed_phase": "synthesizing_consensus",
  "error_code": "llm_json_parse_error",
  "error_message": "Synthesis returned invalid JSON",
  "at": "2026-04-10T10:00:07Z"
}
```

---

# 五、前端状态机 spec

前端不要再只依赖：

* fetch loading
* fetch done

应把 Council 做成一个显式状态机。

---

## 5.1 顶层状态机

### 状态定义

```text id="rcic2r"
idle
  → submitting
  → running_collecting
  → running_synthesizing
  → proposal_ready
  → completed

idle
  → submitting
  → running_collecting
  → running_synthesizing
  → failed
```

---

## 5.2 每个状态的 UI 表现

### `idle`

* 输入框可编辑
* 发起按钮可点
* 无当前 session

### `submitting`

* 按钮 loading
* 创建占位 Council Session 卡片
* 锁定输入框

### `running_collecting`

* 显示参与 Agent 列表
* 每个 Agent 状态：`idle / running / completed`
* 实时渲染 `participant_message`
* 主区域显示“讨论进行中”

### `running_synthesizing`

* Agent 列表只读
* 显示“正在综合共识”
* 先不展示 proposal
* 可展示已收集的观点摘要

### `proposal_ready`

* 共识区、分歧区、proposal 区、next steps 区全部出现
* CTA 根据 `decision_type` 和 `applyability` 切换

### `completed`

* 可继续 follow-up
* 可 apply / variant / rewrite
* 可折叠查看详情

### `failed`

* 显示失败阶段
* 若有已收集的 messages，仍保留展示
* 提供 retry 按钮

---

## 5.3 子状态：参与 Agent 状态机

每个 participant card 应有独立状态。

```text id="sa76yi"
idle → running → completed
idle → running → failed
```

### UI 表现

* `idle`：灰色待开始
* `running`：高亮 + 动效
* `completed`：绿色完成
* `failed`：红色告警 + degraded 标签

---

# 六、前端模块 spec

建议把 Council UI 拆成以下模块。

---

## 6.1 `CouncilSessionPanel`

负责：

* 显示整个 session 状态
* 阶段切换
* 顶层 CTA

props:

* `session`
* `discussion`
* `proposal`
* `uiState`

---

## 6.2 `CouncilParticipantsBoard`

负责：

* 显示所有参与 Agent
* 状态、耗时、是否降级
* 一句话主张

props:

* `participants`
* `messages`
* `observability`

---

## 6.3 `CouncilConsensusPanel`

负责：

* 共识
* 置信度
* decision_type
* applyability

props:

* `discussion.consensus`
* `discussion.confidence`
* `discussion.decision_type`
* `discussion.applyability`

---

## 6.4 `CouncilDisagreementPanel`

负责：

* 展示 disagreements
* 展示 open_questions

props:

* `discussion.disagreements`
* `discussion.open_questions`

---

## 6.5 `CouncilProposalPanel`

负责：

* diff
* proposed_updates
* alternatives
* fallback_action

props:

* `proposal`

行为：

* `Apply`
* `Apply as Draft`
* `Generate Variant`
* `Escalate to Rewrite`

---

## 6.6 `CouncilTimeline`

负责：

* 显示 phase 事件
* 显示 participant message 流

props:

* `events[]`

---

# 七、decision_type / applyability 规则

前端 CTA 不应再只靠 `proposal.diff.changes.length > 0`。

建议统一按这两个字段驱动：

## `decision_type`

* `applyable`
* `advisory`
* `conflicted`
* `insufficient_context`

## `applyability`

* `direct`
* `partial`
* `none`

---

## CTA 映射表

| decision_type        | applyability | 主 CTA             | 次 CTA             |
| -------------------- | ------------ | ----------------- | ----------------- |
| applyable            | direct       | Apply             | Ask follow-up     |
| advisory             | partial      | Apply as Draft    | Turn into Variant |
| conflicted           | none         | Choose Direction  | Ask follow-up     |
| insufficient_context | none         | Fill Missing Info | Retry Council     |

---

# 八、后端实现要求

为了让这套协议真正可用，后端应补这些约束。

---

## 8.1 synthesis 输出 schema

`_synthesize_consensus` 必须稳定输出：

* `decision_type`
* `applyability`
* `agreements`
* `disagreements`
* `open_questions`
* `recommended_next_steps`
* `proposed_updates`
* `alternatives`

不能只返回自由文本 summary。

---

## 8.2 specialist 输出 schema

每个 specialist 至少返回：

* `stance`
* `claim`
* `full_text`
* `references`
* `used_llm`
* `degraded`

---

## 8.3 degraded 明确可见

所有降级都必须在返回和 SSE 里带：

* `used_llm`
* `degraded`
* `fallback_mode`

这样你后续才能做真正的调优。

---

# 九、推荐实现顺序

## 第一批

* 返回 schema 升级
* `decision_type / applyability`
* `agreements / disagreements / open_questions`
* `renderDiscussion` 拆分成四区块

## 第二批

* SSE 协议标准化
* 主区域流式刷新
* 参与 Agent 状态卡

## 第三批

* `Apply as Draft`
* `Turn into Variant`
* `Escalate to Rewrite`
* `Ask follow-up`

## 第四批

* degraded 可视化
* observability 面板
* 对其他 stage 对象复用 Council

---

# 十、给 AI-coding 的总 Prompt

你可以直接把下面这段发给 Codex / Cursor：

```text id="74100"
请把当前 Brief 页的 Council 机制升级成一个 AI-native 咨询会话对象。

目标：
1. 升级返回 schema，使 Council 不再只依赖 proposal diff
2. 升级 SSE 协议，使讨论过程可被主区域实时感知
3. 升级前端状态机，使 Council 成为一个有生命周期的交互对象
4. 支持四种结果态：
   - applyable
   - advisory
   - conflicted
   - insufficient_context

必须完成：
A. HTTP 返回 schema：
- session
- discussion
- proposal
- observability

B. discussion 必须包含：
- consensus
- agreements
- disagreements
- open_questions
- recommended_next_steps
- messages

C. proposal 必须包含：
- diff
- proposed_updates
- alternatives
- fallback_action
- decision_type
- applyability

D. SSE 事件协议：
- council_session_started
- council_phase_changed
- council_participant_started
- council_participant_message
- council_participant_completed
- council_synthesis_started
- council_synthesis_completed
- council_proposal_ready
- council_session_completed
- council_session_failed

E. 前端状态机：
- idle
- submitting
- running_collecting
- running_synthesizing
- proposal_ready
- completed
- failed

F. 前端模块：
- CouncilSessionPanel
- CouncilParticipantsBoard
- CouncilConsensusPanel
- CouncilDisagreementPanel
- CouncilProposalPanel
- CouncilTimeline

要求：
- 不使用 mock
- 基于现有 Brief 页和现有 Council 代码增量改造
- 保持与当前 SSE/EventBus 兼容
- 对 degraded / used_llm / timing_ms 做显式展示
- 每次改动输出：
  - 修改文件清单
  - 新增字段说明
  - 状态流转说明
  - 验证方式
```

