"use client";

import { useTeamProjects } from "@/app/(dashboard)/hooks/projects/useProjects";
import { formatProjectSpend, projectBudgetLabel } from "@/app/(dashboard)/projects/_components/projectBudget";
import { StatusBadge } from "@/components/shared/table_cells";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { migratedHref } from "@/utils/migratedPages";

interface TeamProjectsTabProps {
  teamId: string;
}

export default function TeamProjectsTab({ teamId }: TeamProjectsTabProps) {
  const { data: projects, isLoading } = useTeamProjects(teamId);

  if (isLoading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading projects…</p>;
  }
  if (!projects || projects.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">This team has no projects yet.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Spend</TableHead>
          <TableHead>Budget</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {projects.map((project) => (
          <TableRow key={project.project_id}>
            <TableCell>
              <a
                className="font-medium text-primary hover:underline"
                href={`${migratedHref("projects")}?project=${encodeURIComponent(project.project_id)}`}
              >
                {project.project_alias ?? project.project_id}
              </a>
            </TableCell>
            <TableCell className="tabular-nums">{formatProjectSpend(project.spend)}</TableCell>
            <TableCell className="tabular-nums">{projectBudgetLabel(project)}</TableCell>
            <TableCell>
              <StatusBadge
                tone={project.blocked ? "error" : "success"}
                label={project.blocked ? "Blocked" : "Active"}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
