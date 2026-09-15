import { describe, expect, it } from "vitest";
import type { ProjectBudget } from "@/app/(dashboard)/hooks/projects/useProjects";
import { formatProjectSpend, projectBudgetLabel } from "./projectBudget";

const budget = (maxBudget: number | null): ProjectBudget => ({
  budget_id: "b1",
  max_budget: maxBudget,
  soft_budget: null,
  max_parallel_requests: null,
  tpm_limit: null,
  rpm_limit: null,
  model_max_budget: null,
  budget_duration: "30d",
});

describe("projectBudgetLabel", () => {
  it("says there is no limit when the project has no budget", () => {
    expect(projectBudgetLabel({ spend: 12, litellm_budget_table: null })).toBe("No limit");
  });

  it("treats a zero budget as no limit rather than dividing by zero", () => {
    expect(projectBudgetLabel({ spend: 12, litellm_budget_table: budget(0) })).toBe("No limit");
  });

  it("shows the budget and how much of it is used", () => {
    expect(projectBudgetLabel({ spend: 42, litellm_budget_table: budget(100) })).toBe("$100.00 (42% used)");
  });

  it("keeps counting past 100% so an overspent project stands out", () => {
    expect(projectBudgetLabel({ spend: 150, litellm_budget_table: budget(100) })).toBe("$100.00 (150% used)");
  });
});

describe("formatProjectSpend", () => {
  it("shows dollars to the cent", () => {
    expect(formatProjectSpend(3.5)).toBe("$3.50");
  });
});
