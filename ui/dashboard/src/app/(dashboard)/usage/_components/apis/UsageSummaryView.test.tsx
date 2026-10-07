import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { useProviderUsageSummary } = vi.hoisted(() => ({ useProviderUsageSummary: vi.fn() }));
vi.mock("@/app/(dashboard)/hooks/providerUsage/useProviderUsageSummary", () => ({ useProviderUsageSummary }));

import UsageSummaryView from "./UsageSummaryView";

const summary = (overrides: Record<string, unknown> = {}) => ({
  provider: "openrouter",
  display_name: "OpenRouter",
  days: 30,
  total_cost: "0.00780515",
  facts: 50,
  by_model: [{ model: "openai/gpt-4o", billed_cost: "0.0064525" }],
  by_account: [
    { credential_name: "openrouter-billing", billed_cost: "0.005" },
    { credential_name: "openrouter-secondary", billed_cost: "0.00280515" },
  ],
  by_evidence: { reconciled: "0.00780515", priced: "0", allocated: "0" },
  tokens: { input_tokens: 3372, output_tokens: 1489, cached_input_tokens: 0, cache_write_tokens: 0 },
  grain: "request",
  delay_note: "OpenRouter reports usage roughly a day after it happens.",
  settling_note: "Figures can still change for up to 3 days after they first appear.",
  ...overrides,
});

describe("UsageSummaryView", () => {
  it("shows the exact total spend string, never a rounded or parsed number", () => {
    useProviderUsageSummary.mockReturnValue({ data: summary(), isLoading: false, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    const totalSpend = screen.getByRole("group", { name: "Total spend, last 30 days" });
    expect(within(totalSpend).getByText("$0.00780515")).toBeInTheDocument();
  });

  it("shows spend by model and by account with their exact cost strings", () => {
    useProviderUsageSummary.mockReturnValue({ data: summary(), isLoading: false, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText("openai/gpt-4o")).toBeInTheDocument();
    expect(screen.getByText("$0.0064525")).toBeInTheDocument();
    expect(screen.getByText("openrouter-billing")).toBeInTheDocument();
    expect(screen.getByText("$0.005")).toBeInTheDocument();
    expect(screen.getByText("openrouter-secondary")).toBeInTheDocument();
    expect(screen.getByText("$0.00280515")).toBeInTheDocument();
  });

  it("shows all four token types with their exact counts", () => {
    useProviderUsageSummary.mockReturnValue({ data: summary(), isLoading: false, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText("Input tokens")).toBeInTheDocument();
    expect(screen.getByText("3,372")).toBeInTheDocument();
    expect(screen.getByText("Output tokens")).toBeInTheDocument();
    expect(screen.getByText("1,489")).toBeInTheDocument();
    expect(screen.getByText("Cached input tokens")).toBeInTheDocument();
    expect(screen.getByText("Cache write tokens")).toBeInTheDocument();
  });

  it("shows only the evidence levels this build actually produces, never a mechanism that reads a permanent zero", () => {
    useProviderUsageSummary.mockReturnValue({ data: summary(), isLoading: false, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText("Reconciled")).toBeInTheDocument();
    expect(screen.getByText("The provider billed this amount. These are their figures, not ours.")).toBeInTheDocument();
    expect(screen.queryByText("Priced")).not.toBeInTheDocument();
    expect(screen.queryByText("Allocated")).not.toBeInTheDocument();
    expect(
      screen.queryByText("The provider reported the usage but not the cost, so we applied their published rates."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "The provider has not reported this at all. It is our own estimate from traffic that passed through the gateway, and it may change.",
      ),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
  });

  it("shows a priced or allocated row once it actually carries a non-zero amount", () => {
    useProviderUsageSummary.mockReturnValue({
      data: summary({
        total_cost: "5.5",
        by_evidence: { reconciled: "0", priced: "3", allocated: "2.5" },
      }),
      isLoading: false,
      error: null,
    });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.queryByText("Reconciled")).not.toBeInTheDocument();
    expect(screen.getByText("Priced")).toBeInTheDocument();
    expect(screen.getByText("$3")).toBeInTheDocument();
    expect(screen.getByText("Allocated")).toBeInTheDocument();
    expect(screen.getByText("$2.5")).toBeInTheDocument();
  });

  it("renders both the delay note and the settling note as distinct, unmerged text", () => {
    useProviderUsageSummary.mockReturnValue({ data: summary(), isLoading: false, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText("OpenRouter reports usage roughly a day after it happens.")).toBeInTheDocument();
    expect(
      screen.getByText("Figures can still change for up to 3 days after they first appear."),
    ).toBeInTheDocument();
  });

  it("shows a meaningful empty-window message instead of a zero-filled table when no facts synced", () => {
    const noTokens = { input_tokens: 0, output_tokens: 0, cached_input_tokens: 0, cache_write_tokens: 0 };
    const emptyOverrides = {
      facts: 0,
      total_cost: "0",
      by_model: [],
      by_account: [],
      by_evidence: { reconciled: "0", priced: "0", allocated: "0" },
      tokens: noTokens,
    };
    const emptyWindow = summary(emptyOverrides);
    useProviderUsageSummary.mockReturnValue({ data: emptyWindow, isLoading: false, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText("There is no usage for OpenRouter in the last 30 days")).toBeInTheDocument();
    expect(screen.queryByText(/synced/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Spend by model")).not.toBeInTheDocument();
    expect(screen.queryByText("Reconciled")).not.toBeInTheDocument();
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
  });

  it("shows a loading state rather than a blank panel while the request is in flight", () => {
    useProviderUsageSummary.mockReturnValue({ data: undefined, isLoading: true, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText(/loading usage/i)).toBeInTheDocument();
  });

  it("shows an error message rather than a blank panel when the request fails", () => {
    useProviderUsageSummary.mockReturnValue({ data: undefined, isLoading: false, error: new Error("network") });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText("Could not read usage for this provider")).toBeInTheDocument();
  });
});
