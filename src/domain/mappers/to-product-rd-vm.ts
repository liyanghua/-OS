import type {
  ExceptionItem,
  ProductRDDirectorVM,
  ProjectObject,
} from "@/domain/types";
import { buildPulseBundleForRole, RISK_ORDER } from "@/domain/mappers/pulse-shared";

function samplingRiskScore(p: ProjectObject): number {
  const d = p.definition;
  if (!d) return -1;
  let s = (RISK_ORDER[d.feasibilityRisk] ?? 0) * 10;
  if (d.samplingStatus === "in_progress") s += 3;
  if (d.samplingStatus === "ready_for_review") s += 2;
  if (d.blockingIssues && d.blockingIssues.length > 0) s += 2;
  return s;
}

export function toProductRdDirectorVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
): ProductRDDirectorVM {
  const pulse = buildPulseBundleForRole(
    "product_rd_director",
    projects,
    exceptions,
  );

  const opportunityProjects = projects.filter(
    (p) => p.stage === "opportunity_pool",
  );
  const incubationProjects = projects.filter(
    (p) => p.stage === "new_product_incubation",
  );
  const upgradeProjects = projects.filter((p) => p.stage === "legacy_upgrade");

  const topSamplingRisks = [...projects]
    .filter((p) => p.definition != null)
    .sort((a, b) => samplingRiskScore(b) - samplingRiskScore(a))
    .slice(0, 5);

  return {
    pulse,
    opportunityProjects,
    incubationProjects,
    upgradeProjects,
    topSamplingRisks,
  };
}
