import type { SignalFreshness, TrendDirection } from "./enums";

export interface KPIMetric {
  key:
    | "gmv"
    | "ctr"
    | "cvr"
    | "roi"
    | "add_to_cart_rate"
    | "launch_score"
    | "profit"
    | "impressions"
    | "clicks"
    | "orders"
    | "conversion_count";
  label: string;
  value: number;
  unit?: "%" | "currency" | "count" | "score";
  trend?: TrendDirection;
  deltaVsTarget?: number;
  deltaVsPrevious?: number;
  freshness?: SignalFreshness;
}

export interface KPISet {
  metrics: KPIMetric[];
  updatedAt: string;
}
