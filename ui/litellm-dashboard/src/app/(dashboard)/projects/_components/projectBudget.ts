import type { ProjectResponse } from "@/app/(dashboard)/hooks/projects/useProjects";

export const formatProjectSpend = (spend: number): string => `$${spend.toFixed(2)}`;

export const projectBudgetLabel = (project: Pick<ProjectResponse, "spend" | "litellm_budget_table">): string => {
  const maxBudget = project.litellm_budget_table?.max_budget ?? null;
  if (maxBudget === null || maxBudget <= 0) return "No limit";
  const percentUsed = Math.round((project.spend / maxBudget) * 100);
  return `$${maxBudget.toFixed(2)} (${percentUsed}% used)`;
};
