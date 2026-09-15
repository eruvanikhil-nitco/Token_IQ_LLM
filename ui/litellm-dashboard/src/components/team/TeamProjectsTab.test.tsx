import { describe, expect, it, vi } from "vitest";
import type { ProjectResponse } from "@/app/(dashboard)/hooks/projects/useProjects";
import { renderWithProviders, screen } from "../../../tests/test-utils";
import TeamProjectsTab from "./TeamProjectsTab";

const mockUseTeamProjects = vi.fn();
vi.mock("@/app/(dashboard)/hooks/projects/useProjects", () => ({
  useTeamProjects: (teamId: string) => mockUseTeamProjects(teamId),
}));

const project = (overrides: Partial<ProjectResponse>): ProjectResponse => ({
  project_id: "proj-1",
  project_alias: "Search",
  description: null,
  team_id: "team-1",
  budget_id: null,
  metadata: null,
  models: [],
  spend: 0,
  model_spend: null,
  model_rpm_limit: null,
  model_tpm_limit: null,
  blocked: false,
  object_permission_id: null,
  created_at: "2026-09-01T00:00:00Z",
  created_by: "admin",
  updated_at: "2026-09-01T00:00:00Z",
  updated_by: "admin",
  litellm_budget_table: null,
  ...overrides,
});

describe("TeamProjectsTab", () => {
  it("lists the team's projects with spend, budget and a link to each one", () => {
    mockUseTeamProjects.mockReturnValue({
      isLoading: false,
      data: [
        project({
          spend: 42,
          litellm_budget_table: {
            budget_id: "b1",
            max_budget: 100,
            soft_budget: null,
            max_parallel_requests: null,
            tpm_limit: null,
            rpm_limit: null,
            model_max_budget: null,
            budget_duration: "30d",
          },
        }),
      ],
    });

    renderWithProviders(<TeamProjectsTab teamId="team-1" />);

    expect(mockUseTeamProjects).toHaveBeenCalledWith("team-1");
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/ui/projects?project=proj-1");
    expect(screen.getByText("$42.00")).toBeInTheDocument();
    expect(screen.getByText("$100.00 (42% used)")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("says so when the team has no projects", () => {
    mockUseTeamProjects.mockReturnValue({ isLoading: false, data: [] });

    renderWithProviders(<TeamProjectsTab teamId="team-1" />);

    expect(screen.getByText("This team has no projects yet.")).toBeInTheDocument();
  });
});
