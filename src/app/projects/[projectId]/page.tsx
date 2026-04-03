import { notFound } from "next/navigation";
import { toProjectPageVm } from "@/domain/mappers/to-project-page-vm";
import { ProjectDetailView } from "@/components/project/project-detail-view";
import { getProjectById } from "@/state/mock-projects";

type Props = {
  params: Promise<{ projectId: string }>;
};

export default async function ProjectDetailPage({ params }: Props) {
  const { projectId } = await params;
  const project = getProjectById(projectId);
  if (!project) {
    notFound();
  }
  const vm = toProjectPageVm(project);
  return <ProjectDetailView vm={vm} />;
}
