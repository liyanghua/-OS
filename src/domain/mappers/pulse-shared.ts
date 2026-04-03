import type {
  ActionItem,
  ExceptionItem,
  ProjectObject,
  PulseBundle,
  PulseItem,
  RoleView,
} from "@/domain/types";

export const RISK_ORDER: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

export function ts(): string {
  return new Date().toISOString();
}

export function pulseItem(
  id: string,
  category: PulseItem["category"],
  summary: string,
  audience: RoleView,
  opts: {
    severity?: PulseItem["severity"];
    relatedProjectId?: string;
    freshness?: PulseItem["freshness"];
  } = {},
): PulseItem {
  const now = ts();
  return {
    id,
    createdAt: now,
    updatedAt: now,
    audience,
    category,
    summary,
    severity: opts.severity,
    relatedProjectId: opts.relatedProjectId,
    freshness: opts.freshness ?? "near_real_time",
  };
}

/** 全量脉冲项（未截断）；顺序与 CEO 默认一致：例外 → 项目 pulse/blocker → 待批聚合 → 兜底 */
export function collectAllPulseItems(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
  audience: RoleView,
  approvalSummary?: (pendingCount: number) => string,
): PulseItem[] {
  const items: PulseItem[] = [];
  let seq = 0;
  const push = (p: PulseItem) => {
    items.push(p);
  };

  for (const ex of [...exceptions].sort(
    (a, b) =>
      (RISK_ORDER[b.severity] ?? 0) - (RISK_ORDER[a.severity] ?? 0),
  )) {
    push(
      pulseItem(`pulse_exc_${seq++}`, "blocker", ex.summary, audience, {
        severity: ex.severity,
        relatedProjectId: ex.projectId,
        freshness:
          ex.source === "data_anomaly" ? "real_time" : "near_real_time",
      }),
    );
  }

  for (const p of projects) {
    if (p.latestPulse) {
      const cat: PulseItem["category"] =
        p.stage === "opportunity_pool" ? "opportunity" : "risk";
      push(
        pulseItem(`pulse_lp_${seq++}`, cat, `${p.name}：${p.latestPulse}`, audience, {
          relatedProjectId: p.id,
          severity: p.riskLevel,
        }),
      );
    } else if (p.keyBlocker) {
      push(
        pulseItem(
          `pulse_kb_${seq++}`,
          "blocker",
          `${p.name} 阻塞：${p.keyBlocker}`,
          audience,
          {
            relatedProjectId: p.id,
            severity: p.riskLevel,
          },
        ),
      );
    }
  }

  const pending = projects.flatMap((p) =>
    p.actions
      .filter((a) => a.approvalStatus === "pending")
      .map((a) => ({ p, a })),
  );
  if (pending.length > 0) {
    const line =
      approvalSummary?.(pending.length) ??
      `全盘待审批动作 ${pending.length} 条，优先处理高风险项`;
    push(
      pulseItem(`pulse_apr_${seq++}`, "approval", line, audience, {
        freshness: "real_time",
      }),
    );
  }

  if (items.length === 0) {
    push(
      pulseItem(
        "pulse_default_0",
        "review",
        "当前无强脉冲项，可下钻商品经营主线查看分布。",
        audience,
        { freshness: "batch" },
      ),
    );
  }

  return items;
}

function stageOfProject(
  projectId: string | undefined,
  projects: ProjectObject[],
): ProjectObject["stage"] | undefined {
  if (!projectId) return undefined;
  return projects.find((p) => p.id === projectId)?.stage;
}

function pulseSortScore(
  item: PulseItem,
  audience: RoleView,
  projects: ProjectObject[],
): number {
  const st = stageOfProject(item.relatedProjectId, projects);
  switch (audience) {
    case "ceo":
      return 0;
    case "product_rd_director": {
      if (st === "opportunity_pool") return 0;
      if (st === "new_product_incubation") return 1;
      if (st === "legacy_upgrade") return 2;
      if (item.category === "approval") return 3;
      return 8;
    }
    case "growth_director": {
      if (st === "launch_validation" || st === "growth_optimization") return 0;
      if (item.category === "approval") return 1;
      if (item.category === "blocker") return 2;
      return 8;
    }
    case "visual_director": {
      if (!item.relatedProjectId) return 8;
      const p = projects.find((x) => x.id === item.relatedProjectId);
      if (!p?.expression) return 6;
      const rs = p.expression.readinessStatus;
      if (rs === "not_started" || rs === "in_progress") return 0;
      if (p.expression.creativeVersions.length >= 2) return 1;
      if (st === "legacy_upgrade") return 2;
      return 5;
    }
    default:
      return 8;
  }
}

/** CEO 保持生成序；其它角色按视角加权后截断至 maxItems */
export function orderAndSlicePulseItems(
  items: PulseItem[],
  audience: RoleView,
  projects: ProjectObject[],
  maxItems = 12,
): PulseItem[] {
  if (audience === "ceo") {
    return items.slice(0, maxItems);
  }
  const scored = items.map((item, idx) => ({
    item,
    s: pulseSortScore(item, audience, projects),
    idx,
  }));
  scored.sort((a, b) => {
    if (a.s !== b.s) return a.s - b.s;
    return a.idx - b.idx;
  });
  return scored.map((x) => x.item).slice(0, maxItems);
}

const PULSE_SUMMARY: Record<RoleView, (n: number) => string> = {
  ceo: (n) =>
    n > 0
      ? `今日经营脉冲：${n} 条信号，例外与待审批已按优先级前置（原型数据）。`
      : "今日经营脉冲：暂无（原型）",
  product_rd_director: (n) =>
    n > 0
      ? `商机与孵化脉冲：${n} 条，优先展示商机池与新品孵化相关信号（原型）。`
      : "商机与孵化脉冲：暂无（原型）",
  growth_director: (n) =>
    n > 0
      ? `增长与首发脉冲：${n} 条，侧重首发验证与增长优化战线（原型）。`
      : "增长与首发脉冲：暂无（原型）",
  visual_director: (n) =>
    n > 0
      ? `表达与视觉脉冲：${n} 条，侧重表达规划与版本迭代（原型）。`
      : "表达与视觉脉冲：暂无（原型）",
};

export function buildPulseBundleForRole(
  audience: RoleView,
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
): PulseBundle {
  const all = collectAllPulseItems(projects, exceptions, audience);
  const items = orderAndSlicePulseItems(all, audience, projects);
  const now = ts();
  return {
    audience,
    summary: PULSE_SUMMARY[audience](items.length),
    items,
    generatedAt: now,
  };
}

export function sortPendingActions(a: ActionItem, b: ActionItem): number {
  const rd = (RISK_ORDER[b.risk] ?? 0) - (RISK_ORDER[a.risk] ?? 0);
  if (rd !== 0) return rd;
  return (b.requiresHumanApproval ? 1 : 0) - (a.requiresHumanApproval ? 1 : 0);
}
