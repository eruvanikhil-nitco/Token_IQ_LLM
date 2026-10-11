import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OverviewTab from "./OverviewTab";
import type { DataQualityResponse, ProviderConnection } from "@/components/networking";

/**
 * Proves the wiring the unit tests on `overviewRows` cannot reach: that each figure the rule
 * produces actually arrives on screen, and that a Fix link points at the page the backend named.
 *
 * The shaping itself is asserted in `overviewRows.test.ts`, which runs in milliseconds. What is
 * here is only what needs a real tree.
 */

const CONNECTIONS: ProviderConnection[] = [
  {
    provider: "openrouter",
    display_name: "OpenRouter",
    state: "needs_attention",
    accounts: [
      {
        credential_name: "openrouter-main",
        state: "needs_attention",
        detail: "The last sync failed",
        last_sync_at: "2026-10-11T09:12:00Z",
        last_outcome: "failed",
        facts_stored: 50,
      },
    ],
    fetches: {
      endpoint: "activity",
      endpoint_url: "https://openrouter.ai/api/v1/activity",
      grain: "daily",
      refresh_seconds: 3600,
      window_hours: 24,
      delay_note: "",
      history_note: "",
    },
    verified_against_real_account: true,
  },
  {
    provider: "anthropic",
    display_name: "Anthropic",
    state: "not_connected",
    accounts: [],
    fetches: {
      endpoint: "usage_report",
      endpoint_url: "https://api.anthropic.com/v1/organizations/usage_report/messages",
      grain: "daily",
      refresh_seconds: 3600,
      window_hours: 24,
      delay_note: "",
      history_note: "",
    },
    verified_against_real_account: false,
  },
];

const QUALITY: DataQualityResponse = {
  period_start: "2026-09-11T00:00:00+00:00",
  period_end: "2026-10-11T00:00:00+00:00",
  invoice_coverage: { kind: "covered", providers_billed: 1, providers_invoiced: 0 },
  issues: [
    {
      kind: "measured",
      key: "failing_connections",
      title: "Connections needing attention",
      fix_on: "data-sources",
      count: 1,
    },
    { kind: "measured", key: "missing_invoices", title: "Periods with no invoice", fix_on: "ledger", count: 1 },
    {
      kind: "unmeasurable",
      key: "unmatched_people",
      title: "People not matched across accounts",
      fix_on: "access-control",
      reason: "Needs directory sync, which is not built yet",
    },
    {
      kind: "measured",
      key: "keys_without_project",
      title: "Virtual keys with no project",
      fix_on: "api-keys",
      count: 0,
    },
  ],
  issues_to_fix: 2,
};

const providerConnectionsCall = vi.fn();
const toolConnectionsCall = vi.fn();
const dataQualityCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  providerConnectionsCall: (...args: unknown[]) => providerConnectionsCall(...args),
  toolConnectionsCall: (...args: unknown[]) => toolConnectionsCall(...args),
  dataQualityCall: (...args: unknown[]) => dataQualityCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderTab = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OverviewTab />
    </QueryClientProvider>,
  );
};

describe("the Overview tab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    providerConnectionsCall.mockResolvedValue({ providers: CONNECTIONS });
    toolConnectionsCall.mockResolvedValue({ tools: [] });
    dataQualityCall.mockResolvedValue(QUALITY);
  });

  it("shows how many connected sources are healthy, with the unconnected ones beside it", async () => {
    renderTab();

    // Scoped to the card: this installation has one connected provider that is failing and one
    // uninvoiced provider, so "0 of 1" is genuinely the right answer in two different cards.
    const card = await screen.findByRole("group", { name: "Sources healthy" });

    expect(within(card).getByText("0 of 1")).toBeInTheDocument();
    expect(within(card).getByText(/1 needing attention, 1 not connected/)).toBeInTheDocument();
  });

  it("shows invoice coverage as a fraction of the providers that billed", async () => {
    renderTab();

    const card = await screen.findByRole("group", { name: "Invoice coverage" });

    expect(within(card).getByText("0 of 1")).toBeInTheDocument();
    expect(within(card).getByText(/1 provider billed with no invoice/)).toBeInTheDocument();
  });

  it("lists every check, including the ones with nothing to fix", async () => {
    renderTab();

    expect(await screen.findByText("Connections needing attention")).toBeInTheDocument();
    expect(screen.getByText("Periods with no invoice")).toBeInTheDocument();
    expect(screen.getByText("People not matched across accounts")).toBeInTheDocument();
    expect(screen.getByText("Virtual keys with no project")).toBeInTheDocument();
  });

  it("gives a check that needs action a Fix link to the page the backend named", async () => {
    renderTab();

    const links = await screen.findAllByRole("link", { name: "Fix" });

    expect(links.map((link) => link.getAttribute("href"))).toEqual(["/ui/data-sources", "/ui/ledger"]);
  });

  it("offers no Fix link on a check nobody can answer yet", async () => {
    // The page the backend names is where it will be fixed once directory sync exists. Offering it
    // today sends somebody to a page where the fix is not there.
    renderTab();

    const links = await screen.findAllByRole("link", { name: "Fix" });

    expect(links.map((link) => link.getAttribute("href"))).not.toContain("/ui/access-control");
  });

  it("states why a check nobody can answer cannot be answered", async () => {
    // "Unknown" on the tab asking whether the data can be trusted is only useful with the reason,
    // because the reason is the thing somebody has to go and build.
    renderTab();

    expect(await screen.findByText(/Needs directory sync/)).toBeInTheDocument();
  });

  it("tells a check that came back clear apart from one nobody can answer", async () => {
    renderTab();

    expect(await screen.findByText("None found")).toBeInTheDocument();
    expect(screen.getByText("Clear")).toBeInTheDocument();
    expect(screen.getByText("Not known")).toBeInTheDocument();
  });

  it("counts the clear and the unanswerable checks separately from the ones to fix", async () => {
    renderTab();

    expect(await screen.findByText(/2 to fix, 1 clear, 1 that nobody can answer yet/)).toBeInTheDocument();
  });

  it("offers no Fix link on a check that came back clear", async () => {
    renderTab();

    await screen.findByText("Virtual keys with no project");
    const links = screen.getAllByRole("link", { name: "Fix" });

    expect(links.map((link) => link.getAttribute("href"))).not.toContain("/ui/api-keys");
  });

  it("rolls the sources up by kind and links to the full list", async () => {
    renderTab();

    expect(await screen.findByRole("link", { name: "All accounts" })).toHaveAttribute(
      "href",
      "/ui/data-sources/accounts",
    );
    expect(screen.getByText("AI provider")).toBeInTheDocument();
  });

  it("says the data quality checks could not be read rather than showing them as clear", async () => {
    // The failure that matters most on this tab. An unread check list must never render as a page
    // with nothing wrong on it.
    dataQualityCall.mockRejectedValue(new Error("no"));
    renderTab();

    expect(await screen.findByText(/Could not read data quality checks/)).toBeInTheDocument();
    expect(screen.queryByText("Clear")).not.toBeInTheDocument();
  });
});
