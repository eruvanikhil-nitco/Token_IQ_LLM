import { describe, it, expect, vi, beforeEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "../../../../../tests/test-utils";
import { ProjectDetail } from "./ProjectDetailsPage";
import { ProjectResponse } from "@/app/(dashboard)/hooks/projects/useProjects";

const mockUseProjectDetails = vi.fn();
vi.mock("@/app/(dashboard)/hooks/projects/useProjectDetails", () => ({
  useProjectDetails: (id: string) => mockUseProjectDetails(id),
}));

const mockUseAuthorized = vi.fn();
vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => mockUseAuthorized(),
}));

const mockUseTeam = vi.fn();
vi.mock("@/app/(dashboard)/hooks/teams/useTeams", () => ({
  useTeam: (id?: string) => mockUseTeam(id),
}));

const mockUseProjectSpendByModel = vi.fn();
vi.mock("@/app/(dashboard)/hooks/projects/useProjectSpendByModel", () => ({
  PROJECT_SPEND_WINDOW_DAYS: 30,
  useProjectSpendByModel: (id: string) => mockUseProjectSpendByModel(id),
}));

vi.mock("./ProjectModals/EditProjectModal", () => ({
  EditProjectModal: ({ isOpen }: { isOpen: boolean }) => (isOpen ? <div data-testid="edit-modal" /> : null),
}));

vi.mock("@/components/common_components/DefaultProxyAdminTag", () => ({
  default: ({ userId }: { userId: string }) => <span>{userId}</span>,
}));

vi.mock("./ProjectKeysSection", () => ({
  ProjectKeysSection: ({ projectId }: { projectId: string }) => (
    <div data-testid="project-keys-section">{projectId}</div>
  ),
}));

const mockProject: ProjectResponse = {
  project_id: "proj-1",
  project_alias: "My Project",
  description: "A sample project",
  team_id: "team-1",
  budget_id: null,
  metadata: null,
  models: ["gpt-4"],
  spend: 12.5,
  model_spend: { "gpt-4": 12.5 },
  model_rpm_limit: null,
  model_tpm_limit: null,
  blocked: false,
  object_permission_id: null,
  created_at: "2024-01-15T08:00:00Z",
  created_by: "user-1",
  updated_at: "2024-02-01T12:00:00Z",
  updated_by: "user-2",
  litellm_budget_table: null,
};

const rectangleFills = (container: HTMLElement) =>
  new Set(Array.from(container.querySelectorAll("path.recharts-rectangle")).map((rect) => rect.getAttribute("fill")));

const yAxisTickLabels = (container: HTMLElement) =>
  Array.from(container.querySelectorAll(".recharts-yAxis-tick-labels .recharts-cartesian-axis-tick-value")).map(
    (tick) => tick.textContent,
  );

describe("ProjectDetail", () => {
  const onBack = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseTeam.mockReturnValue({ data: undefined, isLoading: false });
    mockUseProjectSpendByModel.mockReturnValue({ data: [] });
    mockUseAuthorized.mockReturnValue({ isViewOnly: false });
  });

  describe("when loading", () => {
    it("should show a busy indicator and neither the project nor the not-found state", () => {
      mockUseProjectDetails.mockReturnValue({ data: undefined, isLoading: true });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(document.querySelector('[aria-busy="true"]')).toBeInTheDocument();
      expect(screen.queryByText("Project not found")).not.toBeInTheDocument();
      expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    });
  });

  describe("when the project is not found", () => {
    it("should display 'Project not found'", () => {
      mockUseProjectDetails.mockReturnValue({ data: undefined, isLoading: false });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("Project not found")).toBeInTheDocument();
    });

    it("should call onBack when the back button is clicked in the not-found state", async () => {
      const user = userEvent.setup();
      mockUseProjectDetails.mockReturnValue({ data: undefined, isLoading: false });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      await user.click(screen.getByRole("button"));
      expect(onBack).toHaveBeenCalledOnce();
    });
  });

  describe("when the project loads successfully", () => {
    beforeEach(() => {
      mockUseProjectDetails.mockReturnValue({ data: mockProject, isLoading: false });
    });

    it("should render", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });

    it("should display the project alias as the page title", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });

    it("should render the project keys section for the project", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByTestId("project-keys-section")).toHaveTextContent("proj-1");
    });

    it("should display 'Active' for a non-blocked project", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("Active")).toBeInTheDocument();
    });

    it("should display 'Blocked' for a blocked project", () => {
      mockUseProjectDetails.mockReturnValue({
        data: { ...mockProject, blocked: true },
        isLoading: false,
      });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("Blocked")).toBeInTheDocument();
    });

    it("should call onBack when the back button is clicked", async () => {
      const user = userEvent.setup();
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      await user.click(screen.getAllByRole("button")[0]);
      expect(onBack).toHaveBeenCalledOnce();
    });

    it("should show the current spend amount", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("$12.50")).toBeInTheDocument();
    });

    it("should show 'No budget limit' when no max budget is set", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("No budget limit")).toBeInTheDocument();
    });

    it("should show the budget limit when one is set", () => {
      mockUseProjectDetails.mockReturnValue({
        data: {
          ...mockProject,
          litellm_budget_table: { max_budget: 100 },
        },
        isLoading: false,
      });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("of $100.00 budget")).toBeInTheDocument();
    });

    it("should show the project description", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("A sample project")).toBeInTheDocument();
    });

    it("should show an 'Edit Project' button", () => {
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByRole("button", { name: /edit project/i })).toBeInTheDocument();
    });

    it("should hide 'Edit Project' from an admin viewer, who cannot change projects", () => {
      mockUseAuthorized.mockReturnValue({ isViewOnly: true });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /edit project/i })).not.toBeInTheDocument();
    });

    it("should open the edit modal when 'Edit Project' is clicked", async () => {
      const user = userEvent.setup();
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      await user.click(screen.getByRole("button", { name: /edit project/i }));
      expect(screen.getByTestId("edit-modal")).toBeInTheDocument();
    });

    it("should show 'No team assigned' when the project has no team", () => {
      mockUseProjectDetails.mockReturnValue({
        data: { ...mockProject, team_id: null },
        isLoading: false,
      });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("No team assigned")).toBeInTheDocument();
    });

    describe("Spend by Model chart", () => {
      const multiModelSpend = [
        { model: "gpt-5.2", spend: 10 },
        { model: "gpt-5.2-codex", spend: 5.5 },
        { model: "claude-opus-4-8", spend: 2.75 },
        { model: "claude-sonnet-5", spend: 0.5 },
      ];

      beforeEach(() => {
        mockUseProjectDetails.mockReturnValue({ data: mockProject, isLoading: false });
      });

      it("should read spend by model from the daily report rather than the project's stored model_spend", () => {
        mockUseProjectDetails.mockReturnValue({
          data: { ...mockProject, model_spend: { "stale-model": 99 } },
          isLoading: false,
        });
        mockUseProjectSpendByModel.mockReturnValue({ data: [{ model: "gpt-5.2", spend: 1 }] });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(mockUseProjectSpendByModel).toHaveBeenCalledWith("proj-1");
        expect(yAxisTickLabels(container)).toEqual(["gpt-5.2"]);
        expect(screen.getByText("Spend by Model, last 30 days")).toBeInTheDocument();
      });

      it("should render one cyan bar per model without a legend", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(container.querySelectorAll(".recharts-bar")).toHaveLength(1);
        expect(container.querySelectorAll("path.recharts-rectangle")).toHaveLength(4);
        expect(rectangleFills(container)).toEqual(new Set(["var(--color-cyan-500, #06b6d4)"]));
        expect(container.querySelector(".recharts-legend-wrapper")).toBeNull();
      });

      it("should list models on the category axis in the order the report ranks them", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(yAxisTickLabels(container)).toEqual(["gpt-5.2", "gpt-5.2-codex", "claude-opus-4-8", "claude-sonnet-5"]);
      });

      it("should format value axis ticks as dollars with four decimals", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(container.querySelector(".recharts-xAxis-tick-labels")?.textContent).toMatch(/\$\d+\.\d{4}/);
      });

      it("should scale the chart height at 40px per model with a 120px floor", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: multiModelSpend });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
        expect(container.querySelector<HTMLElement>('[data-slot="chart"]')?.style.height).toBe("160px");

        mockUseProjectSpendByModel.mockReturnValue({ data: [{ model: "gpt-4", spend: 12.5 }] });
        const { container: singleModelContainer } = renderWithProviders(
          <ProjectDetail projectId="proj-1" onBack={onBack} />,
        );
        expect(singleModelContainer.querySelector<HTMLElement>('[data-slot="chart"]')?.style.height).toBe("120px");
      });

      it("should show the empty state when the report has no model spend", () => {
        mockUseProjectSpendByModel.mockReturnValue({ data: [] });
        const { container } = renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);

        expect(screen.getByText("No model spend in the last 30 days")).toBeInTheDocument();
        expect(container.querySelector('[data-slot="chart"]')).toBeNull();
      });
    });

    it("should show team information when team data is available", () => {
      mockUseTeam.mockReturnValue({
        data: {
          team_info: {
            team_id: "team-1",
            team_alias: "Engineering",
            models: ["gpt-4"],
            spend: 50,
            members_with_roles: [],
          },
        },
        isLoading: false,
      });
      renderWithProviders(<ProjectDetail projectId="proj-1" onBack={onBack} />);
      expect(screen.getByText("Engineering")).toBeInTheDocument();
    });
  });
});
