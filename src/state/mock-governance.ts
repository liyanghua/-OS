import type { PolicyBoundary } from "@/domain/types";

function iso(d: Date): string {
  return d.toISOString();
}

const now = new Date();

/** 全局规则边界原型种子（非项目内嵌） */
export function createMockPolicyBoundaries(): PolicyBoundary[] {
  return [
    {
      id: "pb_pricing_floor",
      createdAt: iso(now),
      updatedAt: iso(now),
      label: "定价下限与毛利护栏",
      description: "低于底线折扣需人工审批；自动规则仅允许在护栏内调价。",
      appliesTo: "pricing",
      enforcementMode: "approval_required",
    },
    {
      id: "pb_campaign_stack",
      createdAt: iso(now),
      updatedAt: iso(now),
      label: "促销叠券与渠道互斥",
      description: "多券叠加可能触及合规边界；命中时硬阻断或降级为告警。",
      appliesTo: "campaign",
      enforcementMode: "hard_block",
    },
    {
      id: "pb_visual_claim",
      createdAt: iso(now),
      updatedAt: iso(now),
      label: "视觉宣称与证照一致性",
      description: "主图/详情功效宣称需匹配证照范围；超标进入审批。",
      appliesTo: "visual",
      enforcementMode: "warn_only",
    },
    {
      id: "pb_auto_pricing",
      createdAt: iso(now),
      updatedAt: iso(now),
      label: "自动跟价节拍",
      description: "自动化跟价仅在白名单 SKU 与时段内启用。",
      appliesTo: "automation",
      enforcementMode: "approval_required",
    },
  ];
}
