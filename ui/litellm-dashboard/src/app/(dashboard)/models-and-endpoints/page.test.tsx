/* @vitest-environment jsdom */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ModelsAndEndpointsPage, { TAB_LABELS } from "./page";

vi.mock("./panels/AllModelsPanel", () => ({ default: () => <div data-testid="panel-all-models" /> }));
vi.mock("./panels/AddModelPanel", () => ({ default: () => <div data-testid="panel-add" /> }));
vi.mock("./panels/PassThroughPanel", () => ({ default: () => <div data-testid="panel-pass-through" /> }));
vi.mock("./panels/HealthStatusPanel", () => ({ default: () => <div data-testid="panel-health" /> }));
vi.mock("./panels/ModelRetrySettingsPanel", () => ({ default: () => <div data-testid="panel-retry" /> }));
vi.mock("./panels/ModelGroupAliasPanel", () => ({ default: () => <div data-testid="panel-alias" /> }));
vi.mock("./panels/PriceDataPanel", () => ({ default: () => <div data-testid="panel-price" /> }));
vi.mock("./components/ModelLimitsTab", () => ({ default: () => <div data-testid="panel-model-limits" /> }));
vi.mock("./components/ModelPricingTab", () => ({ default: () => <div data-testid="panel-model-pricing" /> }));

const detailState = { modelId: null as string | null, teamId: null as string | null };
vi.mock("./detailNavigation", () => ({
  useModelDetailRouting: () => ({ ...detailState, close: vi.fn(), openModel: vi.fn(), openTeam: vi.fn() }),
}));

vi.mock("@/components/molecules/cost_optimization_feedback_banner", () => ({ default: () => null }));
vi.mock("@/components/model_info_view", () => ({
  default: ({ modelId }: { modelId: string }) => <div data-testid="model-info">model:{modelId}</div>,
}));
vi.mock("@/components/team/TeamInfo", () => ({
  default: ({ teamId }: { teamId: string }) => <div data-testid="team-info">team:{teamId}</div>,
}));

const mockUseAuthorized = vi.fn();
vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({ default: () => mockUseAuthorized() }));
vi.mock("@/app/(dashboard)/hooks/teams/useTeams", () => ({ useTeams: () => ({ data: [] }) }));
vi.mock("@/app/(dashboard)/hooks/uiSettings/useUISettings", () => ({
  useUISettings: () => ({ data: { values: {} } }),
}));
vi.mock("./useModelDashboardData", () => ({
  useModelDashboardData: () => ({ availableModelAccessGroups: [], allModelsOnProxy: [], availableModelGroups: [] }),
}));

const ADMIN = { accessToken: "at", token: "t", userRole: "Admin", userId: "u1", premiumUser: false, isViewOnly: false };
const NON_ADMIN = {
  accessToken: "at",
  token: "t",
  userRole: "Internal User",
  userId: "u1",
  premiumUser: false,
  isViewOnly: false,
};
// A proxy_admin_viewer session: effectiveSessionRole masquerades the role as "Admin".
const VIEW_ONLY_ADMIN = { ...ADMIN, isViewOnly: true };

const renderPage = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ModelsAndEndpointsPage />
    </QueryClientProvider>,
  );
};

describe("ModelsAndEndpointsPage", () => {
  beforeEach(() => {
    detailState.modelId = null;
    detailState.teamId = null;
    mockUseAuthorized.mockReturnValue(ADMIN);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (global as any).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  });

  it("renders the admin tab bar and the All Models panel by default", () => {
    renderPage();
    expect(screen.getByRole("tab", { name: "All Models" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "LLM Credentials" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Health Status" })).toBeInTheDocument();
    expect(screen.getByTestId("panel-all-models")).toBeInTheDocument();
  });

  // The heading must match the sidebar label and breadcrumb ("Models + Endpoints"),
  // not the pre-rename "Model Management".
  it("titles the page Models + Endpoints, matching the sidebar label", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Models + Endpoints" })).toBeInTheDocument();
    expect(screen.queryByText("Model Management")).not.toBeInTheDocument();
  });

  it("switches tabs in-memory, mounting only the active panel", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Health Status" }));
    expect(screen.getByTestId("panel-health")).toBeInTheDocument();
    expect(screen.queryByTestId("panel-all-models")).not.toBeInTheDocument();
  });

  it("renders the model detail overlay from the ?model drill-in and hides the tabs", () => {
    detailState.modelId = "abc-123";
    renderPage();
    expect(screen.getByTestId("model-info")).toHaveTextContent("model:abc-123");
    expect(screen.queryByRole("tab", { name: "All Models" })).not.toBeInTheDocument();
  });

  it("renders the team detail overlay from the ?team drill-in", () => {
    detailState.teamId = "team-9";
    renderPage();
    expect(screen.getByTestId("team-info")).toHaveTextContent("team:team-9");
  });

  it("offers every declared tab to an admin, so none is unreachable", () => {
    renderPage();

    // A tab can be declared in the label map and the panel switch yet never listed in
    // visibleSlugs, in which case it simply does not exist. That is how Model Limits
    // shipped invisible: three of the four places agreed and the fourth did not.
    //
    // The labels come from the declaration itself rather than a list written out here,
    // because a hardcoded list is a fifth place that has to be kept in agreement, and it
    // silently covers nothing for any tab added after it was written.
    const declared = ["All Models", ...Object.values(TAB_LABELS)];

    for (const label of declared) {
      expect(screen.getByRole("tab", { name: new RegExp(label, "i") })).toBeInTheDocument();
    }
  });

  it("hides admin-only tabs for a non-admin user", () => {
    mockUseAuthorized.mockReturnValue(NON_ADMIN);
    renderPage();
    expect(screen.queryByRole("tab", { name: "Health Status" })).not.toBeInTheDocument();
  });

  // POST /model/new 403s a proxy_admin_viewer, so the form's tab must not render for one.
  it("hides the Add Model tab for a view-only admin session", () => {
    mockUseAuthorized.mockReturnValue(VIEW_ONLY_ADMIN);
    renderPage();
    expect(screen.queryByRole("tab", { name: "Add Model" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "All Models" })).toBeInTheDocument();
  });

  // The Auto-Routers tab was removed: semantic model selection picks a model the caller
  // did not ask for, which this gateway must never do.
  it("does not offer an Auto-Routers tab to an admin who can create models", () => {
    renderPage();

    expect(screen.queryByRole("tab", { name: /Auto-Routers/ })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "All Models" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Add Model" })).toBeInTheDocument();
  });
});
