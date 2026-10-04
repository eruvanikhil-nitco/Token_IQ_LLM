# Sidebar Reorganisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rearrange the dashboard sidebar into the agreed Analytics, Organisation, Gateway, Safety, Build and Settings groups. Rename Internal Users to Users and Old Usage to Classic Usage, and move the Model Access Group Budgets and Assign Budget tabs into Budgets. No page or tab is lost.

**Architecture:** The sidebar, the breadcrumbs and the page visibility settings all read `menuGroups` in `leftnav.tsx`, so the reorganisation is almost entirely an edit of that one array. Page ids and route segments do not change, so every existing address keeps working without a redirect, and a new test pins that every sidebar page has a route. Two tab moves touch the Budgets and Models pages.

**Tech Stack:** Next.js dashboard, shadcn / Base UI tabs, lucide icons, vitest with Testing Library

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "Navigation", "Tab rules", "Full sidebar" and "Phases" (Phase 1)

**Depends on:** `docs/superpowers/plans/2026-09-15-projects-and-teams.md` Task 4, which gives the Projects entry its team admin rule. Run that plan first

## Global Constraints

- All work goes on the branch `litellm_token_iq`. Never touch `main`, never create another branch
- No existing page or tab is removed or merged. Pages and tabs may only move or be renamed
- The eight pages without a sidebar entry stay hidden: Organizations, Agents, Workflows, Memory, Caching, Vector Stores, Search Tools, Tool Policies
- Use the words teams, projects and users. Never "employees"
- No customer-visible LiteLLM text
- Never run the full vitest suite. Run `npx vitest run <paths>` from `ui/litellm-dashboard` with explicit paths
- Never put tokens in `localStorage`
- Commit messages follow conventional commits and carry no Claude attribution (the project CLAUDE.md forbids it)
- Commit after each task. Push `litellm_token_iq` at the end

## Scope

Phase 1 creates only groups whose pages already exist. HOME, DATA SOURCES, Ledger, Recommendations, Reports, Attribution Rules and User Directory arrive in later phases. Until then Cost Tracking stays under Settings (it moves into Ledger in Phase 3), LLM Credentials stays a Models tab (Phase 2) and SCIM stays in Admin Settings (Phase 4)

The spec shows no nested entries, so the Model Management, Experimental and Settings parents go away. They are containers with no page of their own, and every child becomes a top-level entry in its new group

## Addresses

No address changes in this plan. Sidebar entries keep their page ids and `MIGRATED_PAGES` keeps every route, including `usage` for Classic Usage, which still opens `/old-usage`. The Models page keeps its active tab in component state rather than in the URL, so moving a tab off it changes no address either

## File Map

- Modify `ui/litellm-dashboard/src/components/leftnav.tsx`: the new `menuGroups`, section names, unused icon import
- Modify `ui/litellm-dashboard/src/components/leftnav.test.tsx`: placement, route and label tests
- Modify `ui/litellm-dashboard/src/components/page_metadata.ts`: drop the Model Management description, reword the users description
- Modify `ui/litellm-dashboard/src/app/(dashboard)/admin-panel/_components/AdminPanel.tsx`: the Users page wording
- Modify `ui/litellm-dashboard/src/app/(dashboard)/budgets/_components/budget_panel.tsx`: Assign Budget and Model Access Group Budgets tabs
- Modify `ui/litellm-dashboard/src/app/(dashboard)/budgets/_components/budget_panel.test.tsx`
- Modify `ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx`: remove the moved tab

---

### Task 1: New sidebar groups

**Files:**
- Modify: `ui/litellm-dashboard/src/components/leftnav.tsx:23-54` (icon import), `:108-298` (`menuGroups`), `:320-326` (`SECTION_DISPLAY`)
- Modify: `ui/litellm-dashboard/src/components/page_metadata.ts:8`
- Test: `ui/litellm-dashboard/src/components/leftnav.test.tsx`

**Interfaces:**
- Consumes: the Projects entry and filter from the projects-and-teams plan Task 4 (`roles: [...all_admin_roles, ...internalUserRoles]`, hidden from non-admins who administer no team)
- Produces: `menuGroups` with group labels `ANALYTICS`, `ORGANISATION`, `GATEWAY`, `SAFETY`, `BUILD`, `SETTINGS` and no `children`; `getBreadcrumb` sections `Analytics`, `Organisation`, `Gateway`, `Safety`, `Build`, `Settings`

- [ ] **Step 1: Write the failing tests**

In `leftnav.test.tsx` add the import below the existing `./leftnav` import:

```tsx
import { MIGRATED_PAGES } from "@/utils/migratedPages";
```

Replace the test `renders all top-level (non-nested) tabs for admin` with these three tests:

```tsx
  it("places every page in its agreed sidebar group, with nothing lost and nothing nested", () => {
    const placements = Object.fromEntries(
      menuGroups.map((group) => [group.groupLabel, group.items.map((item) => item.page)]),
    );

    expect(placements).toEqual({
      ANALYTICS: ["new_usage", "usage", "cost-optimization", "logs"],
      ORGANISATION: ["teams", "projects", "users", "access-groups", "budgets"],
      GATEWAY: ["api-keys", "providers", "models", "llm-playground", "transform-request"],
      SAFETY: ["guardrails", "guardrails-monitor", "policies"],
      BUILD: ["mcp-servers", "skills", "prompts", "tag-management", "model-hub-table", "api_ref"],
      SETTINGS: ["admin-panel", "router-settings", "logging-and-alerts", "cost-tracking", "ui-theme"],
    });
    expect(menuGroups.flatMap((group) => group.items).filter((item) => item.children !== undefined)).toEqual([]);
  });

  it("gives every sidebar page a route, so moving an entry never breaks its address", () => {
    const pages = menuGroups.flatMap((group) => group.items.map((item) => item.page));

    expect(pages.filter((page) => MIGRATED_PAGES[page] === undefined)).toEqual([]);
  });

  it("renders the agreed group labels and page names for an admin", () => {
    renderWithProviders(<Sidebar {...defaultProps} enableProjectsUI />);

    ["ANALYTICS", "ORGANISATION", "GATEWAY", "SAFETY", "BUILD", "SETTINGS"].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
    [
      "Usage",
      "Classic Usage",
      "Cost Optimization",
      "Logs",
      "Teams",
      "Projects",
      "Users",
      "Access Groups",
      "Budgets",
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
      "Admin Settings",
      "Router Settings",
      "Logging & Alerts",
      "Cost Tracking",
      "UI Theme",
    ].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
    expect(screen.queryByText("Internal Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Old Usage")).not.toBeInTheDocument();
    expect(screen.queryByText("Experimental")).not.toBeInTheDocument();
    expect(screen.queryByText("Model Management")).not.toBeInTheDocument();
  });
```

Delete the two tests that only exercised nesting, `expands a nested tab to reveal its children (Experimental > API Playground)` and `reports whether a nested tab is expanded`. No parent entries remain for them to test

Replace `keeps Router Settings as a single Settings child` with:

```tsx
  it("keeps Router Settings as a single Settings entry", () => {
    // Router Settings is admin-only, so getAvailablePages() filters it out entirely and the
    // page_utils duplicate-key guard cannot see it. Walk menuGroups directly.
    expect(placementsOf("router-settings")).toEqual(["SETTINGS"]);
  });
```

In `describe("Admin Viewer parity")`, replace `shows Models + Endpoints to Admin Viewer, nested under Model Management` with:

```tsx
    it("shows Models + Endpoints and Providers to Admin Viewer", () => {
      mockUseAuthorized.mockReturnValue(adminViewerAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Models + Endpoints")).toBeInTheDocument();
      expect(screen.getByText("Providers")).toBeInTheDocument();
    });
```

In `describe("capability-gated nav entries")`:

In `no longer offers the Tools group or any of its children`, replace the last two lines (the comment and `expect(screen.getByText("Experimental"))...`) with:

```tsx
      // A sibling entry still renders, so absence is not a dead sidebar.
      expect(screen.getByText("API Playground")).toBeInTheDocument();
```

Replace the three tests `should hide the Prompts entry from internal users while keeping other Experimental children`, `should hide Old Usage from internal users while keeping other Experimental children` and `should show Old Usage to admins` with:

```tsx
    it("hides Prompts from internal users while keeping API Playground", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("API Playground")).toBeInTheDocument();
      expect(screen.queryByText("Prompts")).not.toBeInTheDocument();
    });

    it("hides Classic Usage from internal users while keeping Usage", () => {
      mockUseAuthorized.mockReturnValue(internalAuth);
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Usage")).toBeInTheDocument();
      expect(screen.queryByText("Classic Usage")).not.toBeInTheDocument();
    });

    it("shows Classic Usage to admins", () => {
      renderWithProviders(<Sidebar {...defaultProps} />);

      expect(screen.getByText("Classic Usage")).toBeInTheDocument();
    });
```

Replace the whole `describe("getBreadcrumb", ...)` block with:

```tsx
describe("getBreadcrumb", () => {
  it("resolves a page to its new section and title", () => {
    expect(getBreadcrumb("api-keys")).toEqual({ section: "Gateway", title: "Virtual Keys" });
    expect(getBreadcrumb("logs")).toEqual({ section: "Analytics", title: "Logs" });
    expect(getBreadcrumb("users")).toEqual({ section: "Organisation", title: "Users" });
    expect(getBreadcrumb("usage")).toEqual({ section: "Analytics", title: "Classic Usage" });
    expect(getBreadcrumb("prompts")).toEqual({ section: "Build", title: "Prompts" });
    expect(getBreadcrumb("policies")).toEqual({ section: "Safety", title: "Policies" });
  });

  it("falls back to the prettified page id for a page with no sidebar entry", () => {
    expect(getBreadcrumb("search-tools")).toEqual({ section: null, title: "Search Tools" });
  });

  it("resolves router-settings under the Settings section", () => {
    expect(getBreadcrumb("router-settings")).toEqual({ section: "Settings", title: "Router Settings" });
  });

  it("falls back to a prettified title with no section for unknown pages", () => {
    expect(getBreadcrumb("some-unknown-page")).toEqual({ section: null, title: "Some Unknown Page" });
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/leftnav.test.tsx`
Expected: FAIL. The placement test reports the old `AI GATEWAY` groups, the label test cannot find `ANALYTICS`, and the breadcrumb test gets `AI Gateway` for `api-keys`

- [ ] **Step 3: Replace `menuGroups`**

In `leftnav.tsx`, replace the whole `const menuGroups: MenuGroup[] = [ ... ];` array (lines 108-298) with:

```tsx
const menuGroups: MenuGroup[] = [
  {
    groupLabel: "ANALYTICS",
    items: [
      {
        key: "new_usage",
        page: "new_usage",
        icon: <BarChart3 {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
        label: "Usage",
      },
      {
        key: "4",
        page: "usage",
        label: "Classic Usage",
        icon: <BarChart3 {...ICON} />,
        roles: rolesWithCapability("viewGlobalSpend"),
      },
      {
        key: "cost-optimization",
        page: "cost-optimization",
        icon: <PiggyBank {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
        label: (
          <span className="flex items-center gap-2">
            Cost Optimization <BetaBadge />
          </span>
        ),
      },
      { key: "logs", page: "logs", label: "Logs", icon: <Activity {...ICON} /> },
    ],
  },
  {
    groupLabel: "ORGANISATION",
    items: [
      { key: "teams", page: "teams", label: "Teams", icon: <Users {...ICON} /> },
      {
        key: "projects",
        page: "projects",
        label: "Projects",
        icon: <Folder {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
      },
      { key: "users", page: "users", label: "Users", icon: <User {...ICON} />, roles: all_admin_roles },
      {
        key: "access-groups",
        page: "access-groups",
        label: "Access Groups",
        icon: <Boxes {...ICON} />,
        roles: all_admin_roles,
      },
      { key: "budgets", page: "budgets", label: "Budgets", icon: <Wallet {...ICON} />, roles: all_admin_roles },
    ],
  },
  {
    groupLabel: "GATEWAY",
    items: [
      { key: "api-keys", page: "api-keys", label: "Virtual Keys", icon: <KeyRound {...ICON} /> },
      { key: "providers", page: "providers", label: "Providers", icon: <Boxes {...ICON} />, roles: all_admin_roles },
      {
        key: "models",
        page: "models",
        label: "Models + Endpoints",
        icon: <Network {...ICON} />,
        roles: rolesAllowedToViewWriteScopedPages,
      },
      {
        key: "llm-playground",
        page: "llm-playground",
        label: "Playground",
        icon: <PlayCircle {...ICON} />,
        roles: rolesWithWriteAccess,
      },
      {
        key: "transform-request",
        page: "transform-request",
        label: "API Playground",
        icon: <Terminal {...ICON} />,
        roles: [...all_admin_roles, ...internalUserRoles],
      },
    ],
  },
  {
    groupLabel: "SAFETY",
    items: [
      { key: "guardrails", page: "guardrails", label: "Guardrails", icon: <Shield {...ICON} /> },
      {
        key: "guardrails-monitor",
        page: "guardrails-monitor",
        label: "Guardrails Monitor",
        icon: <HeartPulse {...ICON} />,
        roles: rolesWithCapability("viewGuardrailUsage"),
      },
      {
        key: "policies",
        page: "policies",
        label: "Policies",
        icon: <ScrollText {...ICON} />,
        roles: rolesWithCapability("viewPolicies"),
      },
    ],
  },
  {
    groupLabel: "BUILD",
    items: [
      { key: "mcp-servers", page: "mcp-servers", label: "MCP Servers", icon: <Server {...ICON} /> },
      { key: "skills", page: "skills", label: "Skills", icon: <Blocks {...ICON} />, roles: all_admin_roles },
      {
        key: "prompts",
        page: "prompts",
        label: "Prompts",
        icon: <FileText {...ICON} />,
        roles: rolesWithCapability("viewPrompts"),
      },
      {
        key: "tag-management",
        page: "tag-management",
        label: "Tag Management",
        icon: <Tags {...ICON} />,
        roles: all_admin_roles,
      },
      { key: "model-hub-table", page: "model-hub-table", label: "AI Hub", icon: <LayoutGrid {...ICON} /> },
      { key: "api_ref", page: "api_ref", label: "API Reference", icon: <Code2 {...ICON} /> },
    ],
  },
  {
    groupLabel: "SETTINGS",
    roles: all_admin_roles,
    items: [
      {
        key: "admin-panel",
        page: "admin-panel",
        label: "Admin Settings",
        icon: <SettingsIcon {...ICON} />,
        roles: all_admin_roles,
      },
      {
        key: "router-settings",
        page: "router-settings",
        label: "Router Settings",
        icon: <Route {...ICON} />,
        roles: all_admin_roles,
      },
      {
        key: "logging-and-alerts",
        page: "logging-and-alerts",
        label: "Logging & Alerts",
        icon: <Bell {...ICON} />,
        roles: all_admin_roles,
      },
      {
        key: "cost-tracking",
        page: "cost-tracking",
        label: "Cost Tracking",
        icon: <BarChart3 {...ICON} />,
        roles: all_admin_roles,
      },
      { key: "ui-theme", page: "ui-theme", label: "UI Theme", icon: <Palette {...ICON} />, roles: all_admin_roles },
    ],
  },
];
```

Every `roles` value above is copied unchanged from the entry's old position. Keep the child rendering code in `renderItem`, `findParentKey` and `filterItemsByRole` as it is; it stays correct for an entry with children and removing it is not part of this plan

- [ ] **Step 4: Rename the sections and drop the unused icon**

Replace `SECTION_DISPLAY` with:

```tsx
const SECTION_DISPLAY: Record<string, string> = {
  ANALYTICS: "Analytics",
  ORGANISATION: "Organisation",
  GATEWAY: "Gateway",
  SAFETY: "Safety",
  BUILD: "Build",
  SETTINGS: "Settings",
};
```

Remove `FlaskConical,` from the `lucide-react` import. It only drew the Experimental parent

In `page_metadata.ts`, delete the line:

```ts
  "model-management": "Providers and the models this gateway serves",
```

- [ ] **Step 5: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run src/components/leftnav.test.tsx src/components/page_utils.test.ts`
Expected: PASS for both files

- [ ] **Step 6: Lint the changed files**

Run from `ui/litellm-dashboard`: `npx eslint src/components/leftnav.tsx src/components/leftnav.test.tsx src/components/page_metadata.ts`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add ui/litellm-dashboard/src/components/leftnav.tsx ui/litellm-dashboard/src/components/leftnav.test.tsx ui/litellm-dashboard/src/components/page_metadata.ts
git commit -m "feat(ui): arrange the sidebar into analytics, organisation, gateway, safety, build and settings"
```

---

### Task 2: Say Users everywhere the page is named

**Files:**
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/admin-panel/_components/AdminPanel.tsx:422`
- Modify: `ui/litellm-dashboard/src/components/page_metadata.ts:27`

**Interfaces:**
- Consumes: the `Users` sidebar label from Task 1
- Produces: nothing new

The role names "Internal User" and "Internal Viewer" are account roles, not the page name, and stay as they are. That includes the "Internal User Page Visibility" setting, which controls what that role can see

- [ ] **Step 1: Confirm what still names the old page**

Run: `grep -rn "Internal Users" ui/litellm-dashboard/src --include=*.ts --include=*.tsx`
Expected: one hit, `AdminPanel.tsx:422`

- [ ] **Step 2: Reword it**

In `AdminPanel.tsx`, replace:

```tsx
      <p className="mb-4 text-sm text-foreground">Go to &apos;Internal Users&apos; page to add other admins.</p>
```

with:

```tsx
      <p className="mb-4 text-sm text-foreground">Go to the Users page to add other admins.</p>
```

In `page_metadata.ts`, replace:

```ts
  users: "Manage internal user accounts and permissions",
```

with:

```ts
  users: "Manage user accounts and permissions",
```

- [ ] **Step 3: Verify nothing names the old page**

Run: `grep -rn "Internal Users\|internal user accounts" ui/litellm-dashboard/src --include=*.ts --include=*.tsx`
Expected: no output

Run from `ui/litellm-dashboard`: `npx vitest run src/components/page_utils.test.ts "src/app/(dashboard)/admin-panel"`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add "ui/litellm-dashboard/src/app/(dashboard)/admin-panel/_components/AdminPanel.tsx" ui/litellm-dashboard/src/components/page_metadata.ts
git commit -m "fix(ui): call the users page Users in admin settings and page descriptions"
```

---

### Task 3: Budgets holds Assign Budget and Model Access Group Budgets

**Files:**
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/budgets/_components/budget_panel.tsx`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/budgets/_components/budget_panel.test.tsx`

**Interfaces:**
- Consumes: `AccessGroupBudgetsPanel`, the default export of `@/app/(dashboard)/models-and-endpoints/panels/AccessGroupBudgetsPanel`, which takes no props. The file stays where it is, following the spec's rule of moving entries rather than page folders
- Produces: Budgets top tabs, in order: `budgets` "Budgets", `assign-budget` "Assign Budget", `examples` "Examples", `access-group-budgets` "Model Access Group Budgets" with its Beta badge

Both pages are admin-only already (the Models tab was shown to `all_admin_roles`, and the Budgets sidebar entry has `roles: all_admin_roles`), so nobody gains or loses access

- [ ] **Step 1: Write the failing tests**

In `budget_panel.test.tsx`, change the Testing Library import to include `within`:

```tsx
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
```

Add this mock below the `useAuthorized` mock:

```tsx
vi.mock("@/app/(dashboard)/models-and-endpoints/panels/AccessGroupBudgetsPanel", () => ({
  default: () => <div data-testid="access-group-budgets-panel" />,
}));
```

Add these tests at the end of `describe("Budget Panel")`:

```tsx
  it("offers the budget tabs in the agreed order", async () => {
    renderPanel();
    await screen.findByRole("heading", { level: 1, name: "Budgets" });

    const topTabs = within(screen.getAllByRole("tablist")[0]).getAllByRole("tab");
    expect(topTabs.map((tab) => tab.textContent)).toEqual([
      "Budgets",
      "Assign Budget",
      "Examples",
      expect.stringContaining("Model Access Group Budgets"),
    ]);
  });

  it("shows Model Access Group Budgets here now that it has moved from Models", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("tab", { name: /Model Access Group Budgets/ }));

    expect(await screen.findByTestId("access-group-budgets-panel")).toBeInTheDocument();
  });

  it("shows how to assign a budget to a customer on its own tab", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("tab", { name: "Assign Budget" }));

    expect(screen.getByText("Assign a budget to a customer")).toBeVisible();
    expect(screen.queryByRole("tab", { name: "Assign Budget to Customer" })).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `ui/litellm-dashboard`: `npx vitest run "src/app/(dashboard)/budgets/_components/budget_panel.test.tsx"`
Expected: FAIL. The tab order test sees `["Budgets", "Examples"]` and the other two cannot find their tabs

- [ ] **Step 3: Add the tabs to Budgets**

In `budget_panel.tsx`, add two imports below the `lucide-react` import block:

```tsx
import AccessGroupBudgetsPanel from "@/app/(dashboard)/models-and-endpoints/panels/AccessGroupBudgetsPanel";
import BetaBadge from "@/components/BetaBadge";
```

Replace the two top-level `TabsTrigger`s inside the `PageHeader` `tabs` render prop with:

```tsx
              <TabsTrigger value="budgets" className="flex-none px-0 py-[7px] data-active:font-semibold">
                Budgets
              </TabsTrigger>
              <TabsTrigger value="assign-budget" className="flex-none px-0 py-[7px] data-active:font-semibold">
                Assign Budget
              </TabsTrigger>
              <TabsTrigger value="examples" className="flex-none px-0 py-[7px] data-active:font-semibold">
                Examples
              </TabsTrigger>
              <TabsTrigger value="access-group-budgets" className="flex-none px-0 py-[7px] data-active:font-semibold">
                <span className="flex items-center gap-2">
                  Model Access Group Budgets <BetaBadge />
                </span>
              </TabsTrigger>
```

Replace the whole `<TabsContent value="examples" ...> ... </TabsContent>` block with:

```tsx
        <TabsContent value="assign-budget" className="min-h-0 flex-1 overflow-y-auto" keepMounted>
          <div className="pt-6">
            <p className="text-base text-muted-foreground">Assign a budget to a customer</p>
            <SyntaxHighlighter language="bash" style={syntaxTheme}>
              {CREATE_END_USER_CURL_COMMAND}
            </SyntaxHighlighter>
          </div>
        </TabsContent>
        <TabsContent value="examples" className="min-h-0 flex-1 overflow-y-auto" keepMounted>
          <div className="pt-6">
            <p className="text-base text-muted-foreground">How to use budget id</p>
            <Tabs defaultValue="curl">
              <TabsList variant="line" className="h-auto w-full justify-start rounded-none border-b p-0">
                <TabsTrigger value="curl" className="flex-none rounded-none px-4 py-2">
                  Test it (Curl)
                </TabsTrigger>
                <TabsTrigger value="openai-sdk" className="flex-none rounded-none px-4 py-2">
                  Test it (OpenAI SDK)
                </TabsTrigger>
              </TabsList>
              <TabsContent value="curl" keepMounted>
                <SyntaxHighlighter language="bash" style={syntaxTheme}>
                  {CHAT_COMPLETIONS_CURL_COMMAND}
                </SyntaxHighlighter>
              </TabsContent>
              <TabsContent value="openai-sdk" keepMounted>
                <SyntaxHighlighter language="python" style={syntaxTheme}>
                  {OPENAI_SDK_PYTHON_CODE}
                </SyntaxHighlighter>
              </TabsContent>
            </Tabs>
          </div>
        </TabsContent>
        <TabsContent value="access-group-budgets" className="min-h-0 flex-1 overflow-y-auto">
          <div className="pt-6">
            <AccessGroupBudgetsPanel />
          </div>
        </TabsContent>
```

The access group tab is deliberately not `keepMounted`, so its data loads only when someone opens it

- [ ] **Step 4: Remove the tab from Models**

In `models-and-endpoints/page.tsx`:

1. Delete `import BetaBadge from "@/components/BetaBadge";` and `import AccessGroupBudgetsPanel from "@/app/(dashboard)/models-and-endpoints/panels/AccessGroupBudgetsPanel";`
2. Delete `| "access-group-budgets"` from `ModelTabSlug`
3. Delete `"access-group-budgets": "Model Access Group Budgets",` from `TAB_LABELS`
4. Delete these two lines from `renderPanel`:

```tsx
    case "access-group-budgets":
      return <AccessGroupBudgetsPanel />;
```

5. Delete `"access-group-budgets",` from the admin list inside `visibleSlugs`
6. Replace the `tabLabel` function with:

```tsx
  const tabLabel = (slug: "" | ModelTabSlug): React.ReactNode => (slug ? TAB_LABELS[slug] : allModelsLabel);
```

- [ ] **Step 5: Run the tests to verify they pass**

Run from `ui/litellm-dashboard`: `npx vitest run "src/app/(dashboard)/budgets/_components/budget_panel.test.tsx" "src/app/(dashboard)/models-and-endpoints/page.test.tsx" "src/app/(dashboard)/models-and-endpoints/panels/AccessGroupBudgetsPanel.integration.test.tsx"`
Expected: PASS

Run: `grep -rn "access-group-budgets" "ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx"`
Expected: no output

- [ ] **Step 6: Lint the changed files**

Run from `ui/litellm-dashboard`: `npx eslint "src/app/(dashboard)/budgets/_components/budget_panel.tsx" "src/app/(dashboard)/budgets/_components/budget_panel.test.tsx" "src/app/(dashboard)/models-and-endpoints/page.tsx"`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add "ui/litellm-dashboard/src/app/(dashboard)/budgets/_components/budget_panel.tsx" "ui/litellm-dashboard/src/app/(dashboard)/budgets/_components/budget_panel.test.tsx" "ui/litellm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx"
git commit -m "feat(ui): keep assign budget and model access group budgets on the budgets page"
```

---

### Task 4: Check the whole dashboard still builds, then push

**Files:** none changed unless a check fails

- [ ] **Step 1: Type-check**

Run from `ui/litellm-dashboard`: `npx tsc --noEmit`
Expected: exit code 0. If it reports errors, fix only the ones in files this plan touched and commit them with the task they belong to

- [ ] **Step 2: Walk the sidebar in a running dashboard**

Start the proxy with `~/.claude/scripts/litellm-dev-up.sh` (port 4001) and the dashboard with `npm run dev` in `ui/litellm-dashboard` (port 3000). Log in as a proxy admin and check:

1. The sidebar shows ANALYTICS, ORGANISATION, GATEWAY, SAFETY, BUILD and SETTINGS, and no Experimental, Model Management or Settings parent
2. Every entry opens its page: Usage, Classic Usage, Cost Optimization, Logs, Teams, Projects, Users, Access Groups, Budgets, Virtual Keys, Providers, Models + Endpoints, Playground, API Playground, Guardrails, Guardrails Monitor, Policies, MCP Servers, Skills, Prompts, Tag Management, AI Hub, API Reference, Admin Settings, Router Settings, Logging & Alerts, Cost Tracking, UI Theme
3. `http://localhost:3000/?page=usage` still opens Classic Usage, and `http://localhost:3000/?page=users` still opens Users
4. Budgets shows Budgets, Assign Budget, Examples and Model Access Group Budgets, and Models + Endpoints no longer has a Model Access Group Budgets tab
5. The breadcrumb on Logs reads Analytics / Logs

- [ ] **Step 3: Push**

```bash
git push origin litellm_token_iq
```
