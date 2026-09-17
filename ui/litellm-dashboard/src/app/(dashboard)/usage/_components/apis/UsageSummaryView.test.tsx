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

  it("shows the evidence split as three separate levels, each with its own cost including zeros", () => {
    useProviderUsageSummary.mockReturnValue({ data: summary(), isLoading: false, error: null });

    render(<UsageSummaryView provider="openrouter" days={30} />);

    expect(screen.getByText("Reconciled")).toBeInTheDocument();
    expect(screen.getByText("Priced")).toBeInTheDocument();
    expect(screen.getByText("Allocated")).toBeInTheDocument();
    expect(screen.getAllByText("$0")).toHaveLength(2);
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

    expect(
      screen.getByText("No usage has synced yet for OpenRouter in the last 30 days.", { exact: false }),
    ).toBeInTheDocument();
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
