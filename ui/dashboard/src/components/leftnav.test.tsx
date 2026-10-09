import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../../tests/test-utils";
import Sidebar, { menuGroups, getBreadcrumb } from "./leftnav";
import { MIGRATED_PAGES } from "@/utils/migratedPages";

vi.mock("../utils/roles", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../utils/roles")>();
  return {
    ...actual,
    all_admin_roles: ["admin", "admin_viewer"],
    old_admin_roles: ["admin", "admin_viewer"],
    internalUserRoles: ["internal"],
    rolesWithWriteAccess: ["admin", "internal"],
    rolesAllowedToViewWriteScopedPages: ["admin", "internal", "admin_viewer"],
    isAdminRole: (role: string) => role === "admin" || role === "admin_viewer",
    isUserTeamAdminForAnyTeam: () => mockIsTeamAdmin(),
  };
});

const { mockUseAuthorized, mockUseOrganizations, mockIsTeamAdmin } = vi.hoisted(() => {
  const mockUseAuthorized = vi.fn(() => ({
    userId: "test-user-id",
    accessToken: "test-access-token",
    userRole: "admin",
    isViewOnly: false,
    token: "test-token",
    userEmail: "test@example.com",
    premiumUser: false,
    disabledPersonalKeyCreation: false,
    showSSOBanner: false,
  }));

  const mockUseOrganizations = vi.fn(() => ({
    data: [],
    isLoading: false,
    error: null,
  }));

  const mockIsTeamAdmin = vi.fn(() => false);

  return { mockUseAuthorized, mockUseOrganizations, mockIsTeamAdmin };
});

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: mockUseAuthorized,
}));

vi.mock("@/app/(dashboard)/hooks/organizations/useOrganizations", () => ({
  useOrganizations: mockUseOrganizations,
}));

vi.mock("@/app/(dashboard)/hooks/teams/useTeams", () => ({
  useTeams: () => ({ data: [], isLoading: false, error: null }),
}));

vi.mock("@/app/(dashboard)/hooks/uiConfig/useUIConfig", () => {
  return {
    useUIConfig: () => ({
      data: { admin_ui_disabled: false },
      isLoading: false,
    }),
  };
});

// The redesigned sidebar reads the custom logo from ThemeContext; the test tree
// has no ThemeProvider, so stub the hook.
const unbrandedTheme = () => ({
  logoUrl: null as string | null,
  logoUrlDark: null as string | null,
  faviconUrl: null as string | null,
  setLogoUrl: vi.fn(),
  setLogoUrlDark: vi.fn(),
  setFaviconUrl: vi.fn(),
});
let mockUseThemeImpl = unbrandedTheme;
vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => mockUseThemeImpl(),
}));

// Version tag + logout target come from network hooks; keep them inert in unit tests.
vi.mock("@/app/(dashboard)/hooks/healthReadiness/useHealthReadinessDetails", () => ({
  useHealthReadinessDetails: () => ({ data: undefined }),
}));
vi.mock("@/app/(dashboard)/hooks/useLogout", () => ({
  useLogout: () => vi.fn(),
}));

const collectNavKeys = (): string[] => menuGroups.flatMap((group) => group.items.map((item) => item.key));

// Every group a page id appears in.
const placementsOf = (page: string): string[] =>
  menuGroups.flatMap((group) => group.items.filter((item) => item.page === page).map(() => group.groupLabel));

describe("Sidebar (leftnav)", () => {
  const defaultProps = {
    setPage: vi.fn(),
    defaultSelectedKey: "api-keys",
    collapsed: false,
  };

  afterEach(() => {
    mockUseAuthorized.mockReset();
    mockUseOrganizations.mockReset();
    mockUseThemeImpl = unbrandedTheme;
  });

  it("should link the logo to the UI home route rather than the proxy origin", () => {
    renderWithProviders(<Sidebar {...defaultProps} />);

    expect(screen.getByRole("link", { name: /token iq home/i })).toHaveAttribute("href", "/ui");
  });

  it("renders the Token IQ wordmark, not a fetched image, when no custom logo is configured", () => {
    renderWithProviders(<Sidebar {...defaultProps} />);

    const home = screen.getByRole("link", { name: /token iq home/i });

    // The default brand is drawn inline so it needs no asset fetch and inherits
    // the theme through currentColor, so there must be no <img> on this path.
    expect(home.querySelectorAll("img")).toHaveLength(0);
    expect(home.querySelector("svg")).not.toBeNull();
    expect(home).toHaveTextContent("Token IQ");
    expect(home).not.toHaveTextContent("LiteLLM");
  });

  it("prefers a configured dark logo over the light one in dark mode", () => {
    mockUseThemeImpl = () => ({
      ...unbrandedTheme(),
      logoUrl: "https://cdn.example.com/logo.png",
      logoUrlDark: "https://cdn.example.com/logo-dark.png",
    });
    renderWithProviders(<Sidebar {...defaultProps} />);

    const [light, dark] = Array.from(screen.getByRole("link", { name: /token iq home/i }).querySelectorAll("img"));

    expect(light).toHaveAttribute("src", "https://cdn.example.com/logo.png");
    expect(dark).toHaveAttribute("src", "https://cdn.example.com/logo-dark.png");
  });

  it("reuses the light custom logo in dark mode when no dark one is configured", () => {
    mockUseThemeImpl = () => ({ ...unbrandedTheme(), logoUrl: "https://cdn.example.com/logo.png" });
    renderWithProviders(<Sidebar {...defaultProps} />);

    const [light, dark] = Array.from(screen.getByRole("link", { name: /token iq home/i }).querySelectorAll("img"));

    expect(light).toHaveAttribute("src", "https://cdn.example.com/logo.png");
    expect(dark).toHaveAttribute("src", "https://cdn.example.com/logo.png");
  });

  it("falls back to the light logo when a configured dark logo fails to load", () => {
    mockUseThemeImpl = () => ({
      ...unbrandedTheme(),
      logoUrl: "https://cdn.example.com/logo.png",
      logoUrlDark: "https://cdn.example.com/gone.png",
    });
    renderWithProviders(<Sidebar {...defaultProps} />);

    const [, dark] = Array.from(screen.getByRole("link", { name: /token iq home/i }).querySelectorAll("img"));
    expect(dark).toHaveAttribute("src", "https://cdn.example.com/gone.png");

    fireEvent.error(dark);

    expect(dark).toHaveAttribute("src", "https://cdn.example.com/logo.png");
  });

  it("places every page in its agreed sidebar group, with nothing lost and nothing nested", () => {
    const placements = Object.fromEntries(
      menuGroups.map((group) => [group.groupLabel, group.items.map((item) => item.page)]),
    );

    expect(placements).toEqual({
      HOME: ["overview"],
      ANALYTICS: ["new_usage", "ledger", "usage", "logs"],
      OPTIMIZATION: ["recommendations", "cost-optimization"],
      GOVERNANCE: ["budgets"],
      ADMINISTRATION: ["organization", "access-control", "attribution", "cost-tracking", "settings"],
      "DATA SOURCES": ["provider-apis", "user-tools", "llm-provider-credentials"],
      GATEWAY: ["api-keys", "providers", "models", "llm-playground", "transform-request"],
      SAFETY: ["guardrails", "guardrails-monitor", "policies"],
      BUILD: ["mcp-servers", "skills", "prompts", "tag-management", "model-hub-table", "api_ref"],
      SETTINGS: ["router-settings"],
    });
  });

  it("gives every sidebar page a route, so moving an entry never breaks its address", () => {
    const pages = menuGroups.flatMap((group) => group.items.map((item) => item.page));

    expect(pages.filter((page) => MIGRATED_PAGES[page] === undefined)).toEqual([]);
  });

  it("renders the agreed group labels and page names for an admin", () => {
    renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

    [
      "HOME",
      "ANALYTICS",
      "OPTIMIZATION",
      "GOVERNANCE",
      "ADMINISTRATION",
      "DATA SOURCES",
      "GATEWAY",
      "SAFETY",
      "BUILD",
      "SETTINGS",
    ].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
    [
      "Cost Explorer",
      "Invoice Reconciliation",
      "Classic Usage",
      "Cost Optimization",
      "Logs",
      "Organization",
      "Access Control",
      "Budgets & Forecasts",
      "Cost Allocation",
      "LLM Provider Credentials",
      "Virtual Keys",
      "Providers",
      "Models + Endpoints",
      "Playground",
      "API Playground",
      "Guardrails",
      "Guardrails Monitor",
      "Policies",
      "MCP Servers",
      "Skills",
      "Prompts",
      "Tag Management",
      "AI Hub",
      "API Reference",
      "Router Settings",
      "Pricing & Rates",
    ].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
    expect(screen.queryByText("Internal Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Old Usage")).not.toBeInTheDocument();
    expect(screen.queryByText("Experimental")).not.toBeInTheDocument();
    expect(screen.queryByText("Model Management")).not.toBeInTheDocument();
  });

  it("keeps Router Settings as a single Settings entry", () => {
    // Router Settings is admin-only, so getAvailablePages() filters it out entirely and the
    // page_utils duplicate-key guard cannot see it. Walk menuGroups directly.
    expect(placementsOf("router-settings")).toEqual(["SETTINGS"]);
  });

  it("has no duplicate keys among all menu items and their children", () => {
    // React keys must be unique across the whole nav config, otherwise the
    // active-item highlight and group expansion collide.
    const keys = collectNavKeys();
    const duplicates = keys.filter((key, i) => keys.indexOf(key) !== i);
    expect(duplicates).toEqual([]);
  });

  describe("Admin Viewer parity", () => {
    // Admin Viewer follows a "read parity with Proxy Admin, no writes, no
    // cost-incurring actions" rule. The session hook presents the viewer as
    // an admin (`userRole: "admin"`) with `isViewOnly: true`; Playground
    // stays hidden (incurs LLM cost) via the isViewOnly flag, while every
    // admin page (Models + Endpoints, Agents, Logs, ...) is visible read-only.
    const adminViewerAuth = {
      userId: "admin-viewer-user-id",
      accessToken: "test-access-token",
      userRole: "admin",
      isViewOnly: true,
      token: "test-token",
      userEmail: "viewer@example.com",
      premiumUser: false,
      disabledPersonalKeyCreation: false,
      showSSOBanner: false,
    };

    it("hides Playground from Admin Viewer (cost-incurring action)", () => {
      mockUseAuthorized.mockReturnValue(adminViewerAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);
      expect(screen.queryByText("Playground")).not.toBeInTheDocument();
    });

    it("shows Models + Endpoints and Providers to Admin Viewer", () => {
      mockUseAuthorized.mockReturnValue(adminViewerAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Models + Endpoints")).toBeInTheDocument();
      expect(screen.getByText("Providers")).toBeInTheDocument();
    });

    it("no longer offers the Agentic group to Admin Viewer", () => {
      mockUseAuthorized.mockReturnValue(adminViewerAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);
      expect(screen.queryByText("Agentic")).not.toBeInTheDocument();
      expect(screen.queryByText("Agents")).not.toBeInTheDocument();
    });

    it("shows Logs to Admin Viewer", () => {
      mockUseAuthorized.mockReturnValue(adminViewerAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);
      expect(screen.getByText("Logs")).toBeInTheDocument();
    });
  });

  describe("capability-gated nav entries", () => {
    const internalAuth = {
      userId: "internal-user-id",
      accessToken: "test-access-token",
      userRole: "internal",
      isViewOnly: false,
      token: "test-token",
      userEmail: "internal@example.com",
      premiumUser: false,
      disabledPersonalKeyCreation: false,
      showSSOBanner: false,
    };

    afterEach(() => {
      mockUseAuthorized.mockReset();
    });

    it("no longer offers the Tools group or any of its children", () => {
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.queryByText("Tools")).not.toBeInTheDocument();
      expect(screen.queryByText("Search Tools")).not.toBeInTheDocument();
      expect(screen.queryByText("Vector Stores")).not.toBeInTheDocument();
      expect(screen.queryByText("Tool Policies")).not.toBeInTheDocument();
      // A sibling entry still renders, so absence is not a dead sidebar.
      expect(screen.getByText("API Playground")).toBeInTheDocument();
    });

    it("should hide the Policies entry from internal users while keeping Guardrails", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Guardrails")).toBeInTheDocument();
      expect(screen.queryByText("Policies")).not.toBeInTheDocument();
    });

    it("hides Prompts from internal users while keeping API Playground", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("API Playground")).toBeInTheDocument();
      expect(screen.queryByText("Prompts")).not.toBeInTheDocument();
    });

    it("hides Classic Usage from internal users while keeping Usage", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Cost Explorer")).toBeInTheDocument();
      expect(screen.queryByText("Classic Usage")).not.toBeInTheDocument();
    });

    it("shows Classic Usage to admins", () => {
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Classic Usage")).toBeInTheDocument();
    });

    it("hides LLM Provider Credentials from internal users", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Cost Explorer")).toBeInTheDocument();
      expect(screen.queryByText("LLM Provider Credentials")).not.toBeInTheDocument();
    });
  });

  // Workflow Runs, Memory and Guardrails Monitor render a shell and then 401
  // for every non-proxy-admin role, because their page-load routes sit outside
  // internal_user_routes / self_managed_routes. Cost Optimization does not:
  // its primary call is /user/daily/activity, which every role may make, so
  // the entry stays and only its proxy-wide tabs are gated inside the page.
  describe("capability-gated pages whose data is proxy-admin-only", () => {
    const authFor = (userRole: string) => ({
      userId: "some-user-id",
      accessToken: "test-access-token",
      userRole,
      isViewOnly: false,
      token: "test-token",
      userEmail: "someone@example.com",
      premiumUser: false,
      disabledPersonalKeyCreation: false,
      showSSOBanner: false,
    });

    afterEach(() => {
      mockUseAuthorized.mockReset();
    });

    it("offers no Agentic entries at all to an internal user", () => {
      mockUseAuthorized.mockReturnValue(authFor("internal"));
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.queryByText("Agentic")).not.toBeInTheDocument();
      expect(screen.queryByText("Workflow Runs")).not.toBeInTheDocument();
      expect(screen.queryByText("Memory")).not.toBeInTheDocument();
    });

    // An org admin's session role is "Org Admin", which no capability list
    // carries, and the proxy denies these routes to org admins too because
    // `_user_is_org_admin` needs an organization_id the page-load GET never sends.
    // Agents is already out of reach for this role, so gating the other two
    // empties the Agentic group entirely and the parent must go with it rather
    // than degrade into a leaf link to the non-route `?page=agentic`.
    it("drops the whole Agentic group for an org admin once its last child is gated", () => {
      mockUseAuthorized.mockReturnValue(authFor("org_admin"));
      renderWithProviders(<Sidebar {...defaultProps} />);

      // Liveness gate: Logs carries no role list, so it proves the sidebar rendered.
      expect(screen.getByText("Logs")).toBeInTheDocument();
      expect(screen.queryByText("Agentic")).not.toBeInTheDocument();
      expect(screen.queryByText("Workflow Runs")).not.toBeInTheDocument();
      expect(screen.queryByText("Memory")).not.toBeInTheDocument();
    });

    it("offers no Agentic entries to an admin either", () => {
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.queryByText("Agentic")).not.toBeInTheDocument();
      expect(screen.queryByText("Workflow Runs")).not.toBeInTheDocument();
      expect(screen.queryByText("Memory")).not.toBeInTheDocument();
      // The sibling capability-gated entry still renders, so this is not a
      // whole-sidebar failure masquerading as absence.
      expect(screen.getByText("Guardrails Monitor")).toBeInTheDocument();
    });

    it("hides Guardrails Monitor from an internal user while keeping Usage and Cost Optimization", () => {
      mockUseAuthorized.mockReturnValue(authFor("internal"));
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.queryByText("Guardrails Monitor")).not.toBeInTheDocument();
      expect(screen.getByText("Cost Explorer")).toBeInTheDocument();
      expect(screen.getByText("Cost Optimization")).toBeInTheDocument();
    });

    it("shows Guardrails Monitor to admins", () => {
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Guardrails Monitor")).toBeInTheDocument();
    });
  });

  it("no longer shows the Organizations tab, even to organization admins", () => {
    mockUseAuthorized.mockReturnValue({
      userId: "org-admin-user-id",
      accessToken: "test-access-token",
      userRole: "viewer",
      isViewOnly: false,
      token: "test-token",
      userEmail: "orgadmin@example.com",
      premiumUser: false,
      disabledPersonalKeyCreation: false,
      showSSOBanner: false,
    });

    mockUseOrganizations.mockReturnValue({
      data: [
        {
          organization_id: "org-1",
          organization_name: "Test Organization",
          spend: 0,
          max_budget: null,
          models: [],
          tpm_limit: null,
          rpm_limit: null,
          members: [
            {
              user_id: "org-admin-user-id",
              user_role: "org_admin",
            },
          ],
        },
      ],
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<Sidebar {...defaultProps} />);

    expect(screen.queryByText("Organizations")).not.toBeInTheDocument();
  });

  it("marks the selected page's nav item active", () => {
    renderWithProviders(<Sidebar {...defaultProps} defaultSelectedKey="logs" />);
    const logs = screen.getByText("Logs").closest("a");
    expect(logs).toHaveAttribute("data-active", "true");
    // A different item must not be active.
    expect(screen.getByText("Virtual Keys").closest("a")).not.toHaveAttribute("data-active");
  });

  it("hides labels but keeps items reachable (icon + link) when collapsed to the rail", () => {
    const { container } = renderWithProviders(<Sidebar {...defaultProps} collapsed />);
    expect(container.querySelector('[data-slot="sidebar"]')).toHaveAttribute("data-collapsed", "true");
    // The item stays navigable in the icon-only rail: its link still renders with
    // an icon (asserting the <a> + svg, not the text, so a removed icon would
    // fail here), while the label is present but CSS-hidden.
    const label = screen.getByText("Virtual Keys");
    const link = label.closest("a");
    expect(link).not.toBeNull();
    expect(link!.querySelector("svg")).not.toBeNull();
    expect(label).toHaveClass("group-data-[collapsed=true]/sidebar:hidden");
  });

  it("shows Cost Optimization with a Beta badge and no feature-flag gate", () => {
    const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI={false} />);

    const costOptimization = container.querySelector('a[href*="cost-optimization"]');
    expect(costOptimization).not.toBeNull();
    expect(costOptimization!).toHaveTextContent(/Cost Optimization/);
    expect(costOptimization!).toHaveTextContent(/Beta/);

    expect(container.querySelector('a[href*="organization"]')).not.toBeNull();
  });

  it("keeps a readable collapsed-rail tooltip for items whose label carries a badge", () => {
    const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI collapsed />);

    expect(container.querySelector('a[href*="cost-optimization"]')).toHaveAttribute("title", "Cost Optimization");
  });

  describe("Settings entry", () => {
    it("shows one Settings entry under Administration rather than three under their own group", () => {
      const { container } = renderWithProviders(<Sidebar {...defaultProps} />);

      expect(container.querySelector('a[href$="/settings"]')).toHaveTextContent("Settings");
      expect(screen.queryByText("Admin Settings")).toBeNull();
      expect(screen.queryByText("UI Theme")).toBeNull();
    });

    it("leaves Router Settings where it was, being in neither the label table nor the blueprint", () => {
      const { container } = renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Router Settings")).toBeInTheDocument();
      expect(container.querySelector('a[href*="router-settings"]')).not.toBeNull();
    });
  });

  describe("Access Control entry", () => {
    const orgAdminAuth = {
      userId: "org-admin-id",
      accessToken: "test-access-token",
      userRole: "Internal User",
      isViewOnly: false,
      token: "test-token",
      userEmail: "org-admin@example.com",
      premiumUser: false,
      disabledPersonalKeyCreation: false,
      showSSOBanner: false,
    };

    it("shows one Access Control entry rather than separate Users and Access Groups", () => {
      const { container } = renderWithProviders(<Sidebar {...defaultProps} />);

      expect(container.querySelector('a[href*="access-control"]')).toHaveTextContent("Access Control");
      expect(screen.queryByText("Access Groups")).toBeNull();
    });

    it("hides it from a viewer who is neither an admin nor an organization admin", () => {
      mockUseAuthorized.mockReturnValue(orgAdminAuth);
      mockUseOrganizations.mockReturnValue({ data: [], isLoading: false, error: null });
      const { container } = renderWithProviders(<Sidebar {...defaultProps} />);

      expect(container.querySelector('a[href*="access-control"]')).toBeNull();
    });

    it("shows it to an organization admin, who was allowed Users and nothing else", () => {
      // The one asymmetry the merge had to carry: Users admitted an org admin by membership,
      // Access Groups and the audit log did not.
      mockUseAuthorized.mockReturnValue(orgAdminAuth);
      mockUseOrganizations.mockReturnValue({
        data: [{ members: [{ user_id: "org-admin-id", user_role: "org_admin" }] }] as never,
        isLoading: false,
        error: null,
      });
      const { container } = renderWithProviders(<Sidebar {...defaultProps} />);

      expect(container.querySelector('a[href*="access-control"]')).not.toBeNull();
    });
  });

  describe("Organization entry", () => {
    const internalAuth = {
      userId: "lead-user-id",
      accessToken: "test-access-token",
      userRole: "internal",
      isViewOnly: false,
      token: "test-token",
      userEmail: "lead@example.com",
      premiumUser: false,
      disabledPersonalKeyCreation: false,
      showSSOBanner: false,
    };

    afterEach(() => {
      mockIsTeamAdmin.mockReset();
    });

    it("shows one Organization entry rather than separate Teams and Projects entries", () => {
      const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

      expect(container.querySelector('a[href*="organization"]')).toHaveTextContent("Organization");
      expect(screen.queryByText("Projects")).toBeNull();
      expect(screen.queryByText("Teams")).toBeNull();
    });

    it("still shows it to a user who administers no team, because Teams is inside it", () => {
      // The visibility rule moved into the page, so the entry is shown whenever any tab is
      // reachable. The old test asserted a Projects link was absent, which an entry that no longer
      // exists satisfies for the wrong reason.
      mockUseAuthorized.mockReturnValue(internalAuth);
      mockIsTeamAdmin.mockReturnValue(false);
      const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

      expect(container.querySelector('a[href*="organization"]')).not.toBeNull();
      expect(screen.getByText("Logs")).toBeInTheDocument();
    });

    it("shows it to a user who administers a team", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      mockIsTeamAdmin.mockReturnValue(true);
      const { container } = renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

      expect(container.querySelector('a[href*="organization"]')).not.toBeNull();
    });

    it("highlights Organization when standing on one of its tabs", () => {
      // findMenuItemKey falls through to Virtual Keys for a page no entry declares, so a merged
      // tab's own URL lit up the wrong entry entirely.
      const { container } = renderWithProviders(
        <Sidebar {...defaultProps} defaultSelectedKey="projects" enableProjectsUI />,
      );
      const organization = container.querySelector('a[href*="organization"]');

      expect(organization).toHaveAttribute("data-active", "true");
    });

    it("hides it when the installation allows the viewer neither tab", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      mockIsTeamAdmin.mockReturnValue(false);
      const { container } = renderWithProviders(
        <Sidebar {...defaultProps} enableProjectsUI enabledPagesInternalUsers={["logs"]} />,
      );

      expect(container.querySelector('a[href*="organization"]')).toBeNull();
      expect(screen.getByText("Logs")).toBeInTheDocument();
    });
  });
});

describe("getBreadcrumb", () => {
  it("resolves a page to its new section and title", () => {
    expect(getBreadcrumb("api-keys")).toEqual({ section: "Gateway", title: "Virtual Keys" });
    expect(getBreadcrumb("logs")).toEqual({ section: "Analytics", title: "Logs" });
    expect(getBreadcrumb("users")).toEqual({ section: "Administration", title: "Access Control" });
    expect(getBreadcrumb("usage")).toEqual({ section: "Analytics", title: "Classic Usage" });
    expect(getBreadcrumb("prompts")).toEqual({ section: "Build", title: "Prompts" });
    expect(getBreadcrumb("policies")).toEqual({ section: "Safety", title: "Policies" });
    expect(getBreadcrumb("llm-provider-credentials")).toEqual({
      section: "Data Sources",
      title: "LLM Provider Credentials",
    });
  });

  it("falls back to the prettified page id for a page with no sidebar entry", () => {
    expect(getBreadcrumb("search-tools")).toEqual({ section: null, title: "Search Tools" });
  });

  it("resolves a merged tab to the entry that owns it", () => {
    // Projects and Teams are tabs of Administration > Organization now. Each still has its own
    // page id, and resolving it to a prettified title would read as a section nobody navigates.
    expect(getBreadcrumb("projects")).toEqual({ section: "Administration", title: "Organization" });
    expect(getBreadcrumb("teams")).toEqual({ section: "Administration", title: "Organization" });
    expect(getBreadcrumb("admin-panel")).toEqual({ section: "Administration", title: "Settings" });
    expect(getBreadcrumb("ui-theme")).toEqual({ section: "Administration", title: "Settings" });
    expect(getBreadcrumb("access-groups")).toEqual({
      section: "Administration",
      title: "Access Control",
    });
  });

  it("resolves router-settings under the Settings section", () => {
    expect(getBreadcrumb("router-settings")).toEqual({ section: "Settings", title: "Router Settings" });
  });

  it("falls back to a prettified title with no section for unknown pages", () => {
    expect(getBreadcrumb("some-unknown-page")).toEqual({ section: null, title: "Some Unknown Page" });
  });
});
