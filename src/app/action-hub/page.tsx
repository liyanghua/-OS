import { Suspense } from "react";
import { ActionHubView } from "@/components/governance/action-hub-view";

export default function ActionHubPage() {
  return (
    <Suspense
      fallback={
        <p className="p-4 text-sm text-[var(--muted)]">加载动作中心…</p>
      }
    >
      <ActionHubView />
    </Suspense>
  );
}
