import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, testQueryClient } from "../../../../../tests/test-utils";
import ProvidersOverview from "./ProvidersOverview";
import type { ProviderOverviewResponse } from "./types";

const mockProviderOverviewCall = vi.hoisted(() => vi.fn());

vi.mock("@/components/networking", () => ({
  providerOverviewCall: mockProviderOverviewCall,
}));

const response = (overrides: Partial<ProviderOverviewResponse> = {}): ProviderOverviewResponse => ({
  total_providers: 2,
  total_models: 3,
  total_requests: 27,
  total_spend: 0.006135,
  rollup_days: 2,
  providers: [
    {
      provider: "openrouter",
      models_configured: 2,
      models_in_catalogue: 260,
      has_credentials: true,
      is_configured: true,
      requests: 27,
      spend: 0.006135,
      last_used: "2026-09-08",
    },
    {
      provider: "anthropic",
      models_configured: 1,
      models_in_catalogue: 40,
      has_credentials: false,
      is_configured: true,
      requests: 0,
      spend: 0,
      last_used: null,
    },
  ],
  ...overrides,
});

describe("ProvidersOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // testQueryClient is a module-level singleton with staleTime Infinity, so without
    // this a later test reads the first test's cached response and never refetches.
    testQueryClient.clear();
    mockProviderOverviewCall.mockResolvedValue(response());
  });

  it("shows the four totals from the response, not recomputed from the rows", async () => {
    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    expect(await screen.findByText("Total Providers")).toBeInTheDocument();
    expect(screen.getByText("Total Models")).toBeInTheDocument();
    // 27 and the cost appear on the openrouter row too, so assert the blocks themselves.
    expect(screen.getByTestId("stat-requests")).toHaveTextContent("27");
    expect(screen.getByTestId("stat-cost")).toHaveTextContent("$0.006135");
    expect(screen.getByTestId("stat-total-providers")).toHaveTextContent("2");
  });

  it("never labels the window as 24 hours, which the daily rollup cannot answer", async () => {
    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    await screen.findByText("Total Providers");
    expect(screen.queryByText(/24h|24 hours/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Last 2 UTC days").length).toBeGreaterThan(0);
  });

  it("renders one row per provider with its catalogue count", async () => {
    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    expect(await screen.findByText("openrouter")).toBeInTheDocument();
    expect(screen.getByText("anthropic")).toBeInTheDocument();
    expect(screen.getByText("260")).toBeInTheDocument();
  });

  it("distinguishes a provider with credentials from one without", async () => {
    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    expect(await screen.findByText("Present")).toBeInTheDocument();
    expect(screen.getByText("Missing")).toBeInTheDocument();
  });

  it("narrows the table to the selected provider while leaving the totals alone", async () => {
    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider="anthropic" />);

    expect(await screen.findByText("anthropic")).toBeInTheDocument();
    expect(screen.queryByText("openrouter")).not.toBeInTheDocument();
    // The blocks describe the whole gateway, so filtering a row must not change them.
    expect(screen.getByText("Total Providers")).toBeInTheDocument();
  });

  it("flags a provider that served traffic but has no deployment left", async () => {
    mockProviderOverviewCall.mockResolvedValue(
      response({
        providers: [
          {
            provider: "openrouter",
            models_configured: 0,
            models_in_catalogue: 260,
            has_credentials: false,
            is_configured: false,
            requests: 24,
            spend: 0.00642,
            last_used: "2026-09-08",
          },
        ],
      }),
    );

    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    // Hiding it would drop real spend out of the totals above the table.
    expect(await screen.findByText("openrouter")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
  });

  it("does not label a still-configured provider as removed", async () => {
    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    await screen.findByText("openrouter");
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
  });

  it("says so when nothing is configured rather than rendering an empty table", async () => {
    mockProviderOverviewCall.mockResolvedValue(
      response({ providers: [], total_providers: 0, total_models: 0, total_requests: 0, total_spend: 0 }),
    );

    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    expect(await screen.findByText("No providers configured, and none recorded any traffic.")).toBeInTheDocument();
  });

  it("reports a failed fetch instead of showing zeros that look like real data", async () => {
    mockProviderOverviewCall.mockRejectedValue(new Error("boom"));

    renderWithProviders(<ProvidersOverview accessToken="tok" selectedProvider={null} />);

    expect(await screen.findByText("Could not load provider overview.")).toBeInTheDocument();
  });
});
