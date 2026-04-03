import type { LifecycleStage } from "@/domain/types";

export type NavItem = {
  href: string;
  label: string;
};

export type NavSection = {
  id: string;
  label?: string;
  items: NavItem[];
};

/** 经营界面展示用（底层 stage 枚举与路由不变） */
export const LIFECYCLE_STAGE_LABELS: Record<LifecycleStage, string> = {
  opportunity_pool: "商机池",
  new_product_incubation: "新品孵化",
  launch_validation: "首发验证",
  growth_optimization: "增长优化",
  legacy_upgrade: "老品升级",
  review_capture: "复盘沉淀",
};

const LIFECYCLE_ROUTES: { stage: LifecycleStage; href: string }[] = [
  { stage: "opportunity_pool", href: "/lifecycle/opportunity-pool" },
  { stage: "new_product_incubation", href: "/lifecycle/new-product-incubation" },
  { stage: "launch_validation", href: "/lifecycle/launch-validation" },
  { stage: "growth_optimization", href: "/lifecycle/growth-optimization" },
  { stage: "legacy_upgrade", href: "/lifecycle/legacy-upgrade" },
];

/** Workspace routes under lifecycle (AGENTS.md mapping) */
export const LIFECYCLE_STAGE_NAV: {
  stage: LifecycleStage;
  href: string;
  label: string;
}[] = LIFECYCLE_ROUTES.map(({ stage, href }) => ({
  stage,
  href,
  label: LIFECYCLE_STAGE_LABELS[stage],
}));

/** IA_AND_PAGES.md §1 global hubs + lifecycle grouping */
export function getMainNavSections(): NavSection[] {
  return [
    {
      id: "hubs",
      items: [
        { href: "/command-center", label: "经营指挥台" },
        { href: "/projects", label: "商品项目" },
        { href: "/action-hub", label: "动作中心" },
        { href: "/governance", label: "风险与审批" },
        { href: "/assets", label: "经验资产库" },
      ],
    },
    {
      id: "lifecycle",
      label: "商品经营主线",
      items: [
        { href: "/lifecycle", label: "主线总览" },
        ...LIFECYCLE_STAGE_NAV.map(({ href, label }) => ({ href, label })),
        {
          href: "/lifecycle/review-capture",
          label: LIFECYCLE_STAGE_LABELS.review_capture,
        },
      ],
    },
  ];
}
