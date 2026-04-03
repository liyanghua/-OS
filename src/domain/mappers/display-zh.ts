import type {
  ActionItem,
  AgentStatus,
  ApprovalStatus,
  AssetPublishStatus,
  AssetType,
  ConfidenceLevel,
  CreativeVersion,
  ExceptionItem,
  ExecutionMode,
  ExecutionStatus,
  ExpressionPlan,
  ProductDefinition,
  ProjectHealth,
  ProjectType,
  ReviewVerdict,
  RiskLevel,
  SignalFreshness,
  PolicyBoundary,
  PolicyEnforcementMode,
  PulseItem,
} from "@/domain/types";
import type { PersonRef } from "@/domain/types/entity";
import type { AttributionFactor } from "@/domain/types/review-asset";

export function projectTypeLabel(t: ProjectType): string {
  const m: Record<ProjectType, string> = {
    opportunity_project: "商机项目",
    new_product_project: "新品项目",
    growth_optimization_project: "增长优化项目",
    legacy_upgrade_project: "老品升级项目",
  };
  return m[t];
}

export function personRoleLabel(r: PersonRef["role"]): string {
  const m: Record<PersonRef["role"], string> = {
    ceo: "老板",
    product_rd_director: "产品研发总监",
    growth_director: "运营与营销总监",
    visual_director: "视觉总监",
    operator: "运营执行",
    designer: "设计",
    analyst: "分析",
    agent: "智能体",
  };
  return m[r];
}

export function pulseCategoryLabel(c: PulseItem["category"]): string {
  const m: Record<PulseItem["category"], string> = {
    risk: "风险",
    opportunity: "机会",
    approval: "待审批",
    blocker: "阻塞",
    resource: "资源",
    review: "复盘",
  };
  return m[c];
}

export function signalFreshnessLabel(f: SignalFreshness): string {
  const m: Record<SignalFreshness, string> = {
    real_time: "实时",
    near_real_time: "准实时",
    batch: "批次",
  };
  return m[f];
}

export function confidenceLevelLabel(c: ConfidenceLevel): string {
  const m: Record<ConfidenceLevel, string> = {
    low: "低",
    medium: "中",
    high: "高",
  };
  return m[c];
}

/** 展示用代表性置信度（领域仍为 low/medium/high，未改模型） */
export function confidenceLevelPercent(c: ConfidenceLevel): number {
  const m: Record<ConfidenceLevel, number> = {
    low: 58,
    medium: 76,
    high: 91,
  };
  return m[c];
}

/** 用于界面：「91%（高）」 */
export function confidenceLevelPercentLabel(c: ConfidenceLevel): string {
  return `${confidenceLevelPercent(c)}%（${confidenceLevelLabel(c)}）`;
}

export function opportunityRecommendationLabel(
  r: "ignore" | "observe" | "evaluate" | "initiate",
): string {
  const m: Record<typeof r, string> = {
    ignore: "忽略",
    observe: "观察",
    evaluate: "再评估",
    initiate: "建议立项",
  };
  return m[r];
}

export function assetTypeLabel(t: AssetType): string {
  const m: Record<AssetType, string> = {
    case: "案例",
    rule: "规则",
    template: "模板",
    skill: "技能包",
    sop: "SOP 卡",
    evaluation_sample: "评测样本",
  };
  return m[t];
}

export function assetPublishStatusLabel(s: AssetPublishStatus): string {
  const m: Record<AssetPublishStatus, string> = {
    draft: "草稿",
    published: "已发布",
    deprecated: "已下线",
  };
  return m[s];
}

export function attributionCategoryLabel(
  c: AttributionFactor["category"],
): string {
  const m: Record<AttributionFactor["category"], string> = {
    product_definition: "产品定义",
    sampling: "打样与采样",
    content: "内容",
    visual: "视觉",
    campaign: "推广与活动",
    timing: "节奏与时点",
    supply: "供给与产能",
    agent_execution: "智能体执行",
  };
  return m[c];
}

export function triggeredByLabel(t: ActionItem["triggeredBy"]): string {
  const m: Record<ActionItem["triggeredBy"], string> = {
    human: "人为发起",
    decision_brain: "经营建议",
    scenario_agent: "智能体",
    automation_rule: "自动化",
  };
  return m[t];
}

export function projectHealthLabel(h: ProjectHealth): string {
  const m: Record<ProjectHealth, string> = {
    healthy: "健康",
    watch: "关注",
    at_risk: "有风险",
    critical: "高风险",
  };
  return m[h];
}

export function riskLevelLabel(r: RiskLevel): string {
  const m: Record<RiskLevel, string> = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "极高",
  };
  return m[r];
}

export function approvalStatusLabel(s: ApprovalStatus): string {
  const m: Record<ApprovalStatus, string> = {
    not_required: "无需审批",
    pending: "待审批",
    approved: "已通过",
    rejected: "已驳回",
    expired: "已过期",
  };
  return m[s];
}

export function agentStatusLabel(s: AgentStatus): string {
  const m: Record<AgentStatus, string> = {
    idle: "空闲",
    running: "运行中",
    waiting_human: "等待人工处理",
    blocked: "已阻塞",
    failed: "失败",
    completed: "已完成",
  };
  return m[s];
}

export function executionModeLabel(m: ExecutionMode): string {
  const map: Record<ExecutionMode, string> = {
    manual: "人工执行",
    agent: "智能体执行",
    automation: "自动执行",
  };
  return map[m];
}

export function reviewVerdictLabel(v: ReviewVerdict): string {
  const m: Record<ReviewVerdict, string> = {
    success: "成功",
    partial_success: "部分成功",
    failed: "失败",
    observe_more: "继续观察",
  };
  return m[v];
}

export function samplingStatusLabel(
  s: ProductDefinition["samplingStatus"],
): string {
  const m: Record<ProductDefinition["samplingStatus"], string> = {
    not_started: "未开始",
    in_progress: "进行中",
    ready_for_review: "待评审",
    approved: "已通过",
  };
  return m[s];
}

export function expressionReadinessLabel(
  s: ExpressionPlan["readinessStatus"],
): string {
  const m: Record<ExpressionPlan["readinessStatus"], string> = {
    not_started: "未开始",
    in_progress: "进行中",
    ready: "已就绪",
    launched: "已首发",
  };
  return m[s];
}

export function creativeVersionStatusLabel(
  s: CreativeVersion["status"],
): string {
  const m: Record<CreativeVersion["status"], string> = {
    draft: "草稿",
    testing: "测试中",
    selected: "已选用",
    retired: "已退役",
  };
  return m[s];
}

export function executionStatusLabel(s: ExecutionStatus): string {
  const m: Record<ExecutionStatus, string> = {
    suggested: "已建议",
    queued: "已排队",
    in_progress: "执行中",
    completed: "已完成",
    rolled_back: "已回滚",
    failed: "已失败",
    canceled: "已取消",
  };
  return m[s];
}

export function policyAppliesToLabel(
  a: PolicyBoundary["appliesTo"],
): string {
  const m: Record<PolicyBoundary["appliesTo"], string> = {
    pricing: "定价",
    launch: "首发",
    campaign: "促销与推广",
    visual: "视觉与内容",
    approval: "审批链路",
    automation: "自动化",
  };
  return m[a];
}

export function policyEnforcementModeLabel(m: PolicyEnforcementMode): string {
  const map: Record<PolicyEnforcementMode, string> = {
    hard_block: "硬阻断",
    approval_required: "需审批",
    warn_only: "仅告警",
  };
  return map[m];
}

export function exceptionSourceLabel(s: ExceptionItem["source"]): string {
  const m: Record<ExceptionItem["source"], string> = {
    approval_timeout: "审批超时",
    agent_failure: "智能体异常",
    data_anomaly: "数据异常",
    policy_violation: "规则边界",
    low_confidence_decision: "低置信决策",
    rollback_event: "回滚事件",
  };
  return m[s];
}
