import type { ExceptionItem } from "@/domain/types";

function iso(d: Date): string {
  return d.toISOString();
}

const now = new Date();

/** 与主线总览 mock 配套的例外项（无 projectId 的条目录入复盘沉淀阶段展示，见 IMPLEMENT 说明） */
export function createMockExceptions(): ExceptionItem[] {
  return [
    {
      id: "exc_growth_metric",
      createdAt: iso(now),
      updatedAt: iso(now),
      projectId: "proj_demo_growth",
      source: "data_anomaly",
      severity: "high",
      summary: "退款率 24h 内跳升，需运营与营销总监关注",
      requiresHumanIntervention: true,
    },
    {
      id: "exc_launch_agent",
      createdAt: iso(now),
      updatedAt: iso(now),
      projectId: "proj_launch_val",
      source: "agent_failure",
      severity: "medium",
      summary: "首发诊断智能体超时重试中",
      requiresHumanIntervention: false,
    },
    {
      id: "exc_global_policy",
      createdAt: iso(now),
      updatedAt: iso(now),
      source: "policy_violation",
      severity: "critical",
      summary: "全站规则：促销叠券配置疑似越界，待风险与审批台兜底",
      requiresHumanIntervention: true,
    },
  ];
}
