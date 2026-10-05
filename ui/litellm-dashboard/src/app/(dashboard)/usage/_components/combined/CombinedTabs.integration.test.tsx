import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CombinedTabs from "./CombinedTabs";
import type { ComparisonResponse } from "@/components/networking";

const PERIOD = {
  from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
  to: new Date(),
};

const COMPARISON: ComparisonResponse = {
  days: 30,
  total_gateway: "0.00005815",
  total_provider: "0.00780515",
  total_gap: "0.00774700",
  rows: [
    {
      day: "2026-09-16",
      provider: "openrouter",
      display_name: "OpenRouter",
      credential_name: "openrouter-billing",
      gateway_cost: "0.00005815",
      provider_cost: "0.00005815",
      gap: "0",
      status: "matched",
      owner_type: null,
      owner_id: null,
    },
    {
      day: "2026-09-15",
      provider: "openrouter",
      display_name: "OpenRouter",
      credential_name: "openrouter-billing",
      gateway_cost: "0",
      provider_cost: "0.00774700",
      gap: "0.00774700",
      status: "gap",
      owner_type: null,
      owner_id: null,
    },
    {
      day: "2026-09-14",
      provider: "openai",
      display_name: "OpenAI",
      credential_name: "openai-billing",
      gateway_cost: "0.5",
      provider_cost: null,
      gap: "0",
      status: "no_provider_data",
      owner_type: null,
      owner_id: null,
    },
  ],
};

const comparisonCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  combinedComparisonCall: (...args: unknown[]) => comparisonCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderTabs = (period: { from: Date; to: Date } = PERIOD) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CombinedTabs period={period} />
    </QueryClientProvider>,
  );
};

/** The date range is a Base UI select: it answers to real clicks, not to a raw change event. */
const choose = async (user: ReturnType<typeof userEvent.setup>, control: string, option: string) => {
  await user.click(screen.getByRole("combobox", { name: control }));
  await user.click(await screen.findByRole("option", { name: option }));
};

describe("CombinedTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    comparisonCall.mockResolvedValue(COMPARISON);
  });

  it("shows the two sources and their difference as three separate figures", async () => {
    renderTabs();
    await screen.findByText("Providers billed");

    // Three distinct totals, never one combined number: the provider figure, the gateway
    // figure, and what the provider charged beyond it.
    expect(screen.getByText("$0.00780515")).toBeInTheDocument();
    expect(screen.getAllByText("$0.00005815").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$0.00774700").length).toBeGreaterThan(0);
    expect(screen.queryByText("$0.00786330")).not.toBeInTheDocument();
  });

  it("shows a real difference as money, with the account that produced it", async () => {
    renderTabs();
    expect(await screen.findAllByText("$0.00774700")).not.toHaveLength(0);
    expect(screen.getAllByText("Gap").length).toBeGreaterThan(0);
  });

  it("does not claim the sources agree on a day the provider reported nothing", async () => {
    renderTabs();
    expect(await screen.findByText("Provider reported nothing")).toBeInTheDocument();
  });

  it("has no date control of its own, because the page owns the period", async () => {
    // It used to hold a 7/30/90 dropdown while Gateway held a separate picker, and both panels
    // stay mounted, so switching tab moved the window with nothing on screen saying so.
    renderTabs();
    await screen.findByText("Providers billed");

    expect(screen.queryByRole("combobox", { name: "Date range" })).not.toBeInTheDocument();
  });

  it("asks the server for the period the page gave it", async () => {
    renderTabs();
    await screen.findByText("Providers billed");

    expect(comparisonCall).toHaveBeenLastCalledWith("sk-test", 30);
  });

  it("keeps the period when moving between the views", async () => {
    const user = userEvent.setup();
    renderTabs();
    await screen.findByText("Providers billed");

    await user.click(screen.getByRole("tab", { name: "Unallocated" }));
    await user.click(screen.getByRole("tab", { name: "Source Comparison" }));
    await screen.findByText("Providers billed");

    expect(comparisonCall).toHaveBeenLastCalledWith("sk-test", 30);
  });

  it("says so rather than silently showing a different window it can serve", async () => {
    // These endpoints take a number of days capped at 90 and always mean "the last N days", so a
    // year to date cannot be served. Reporting that silently is the failure this replaced.
    renderTabs({
      from: new Date("2026-01-01T12:00:00.000Z"),
      to: new Date("2026-10-08T12:00:00.000Z"),
    });

    expect(await screen.findByRole("status")).toHaveTextContent("90 days");
  });

  it("links an unclaimed difference to the page that would assign it", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Unallocated" }));

    const link = await screen.findByRole("link", { name: /assign this account, openrouter-billing/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("attribution"));
  });

  it("lists only differences nobody has claimed on the Unallocated view", async () => {
    const user = userEvent.setup();
    renderTabs();
    await user.click(screen.getByRole("tab", { name: "Unallocated" }));

    expect(await screen.findAllByRole("link", { name: /assign this account/i })).toHaveLength(1);
  });
});
