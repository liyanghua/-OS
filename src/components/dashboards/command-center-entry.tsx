"use client";

import type { RoleView } from "@/domain/types";
import { useAppStore } from "@/state/app-store";
import { CeoCommandCenterView } from "@/components/dashboards/ceo-command-center-view";
import { ProductRdDirectorView } from "@/components/dashboards/product-rd-director-view";
import { GrowthDirectorView } from "@/components/dashboards/growth-director-view";
import { VisualDirectorView } from "@/components/dashboards/visual-director-view";

function viewForRole(role: RoleView) {
  switch (role) {
    case "ceo":
      return <CeoCommandCenterView />;
    case "product_rd_director":
      return <ProductRdDirectorView />;
    case "growth_director":
      return <GrowthDirectorView />;
    case "visual_director":
      return <VisualDirectorView />;
    default:
      return <CeoCommandCenterView />;
  }
}

export function CommandCenterEntry() {
  const { roleView } = useAppStore();
  return viewForRole(roleView);
}
