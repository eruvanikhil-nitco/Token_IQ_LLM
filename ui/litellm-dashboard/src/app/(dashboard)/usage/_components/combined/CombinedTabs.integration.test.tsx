import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CombinedTabs from "./CombinedTabs";
import type { ComparisonResponse } from "@/components/networking";

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

const renderTabs = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CombinedTabs />
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

  it("keeps the chosen date range when moving between the views", async () => {
    const user = userEvent.setup();
    renderTabs();
    await screen.findByText("Providers billed");

    await choose(user, "Date range", "Last 7 days");
    await user.click(screen.getByRole("tab", { name: "Unallocated" }));
    await user.click(screen.getByRole("tab", { name: "Source Comparison" }));

    expect(screen.getByRole("combobox", { name: "Date range" })).toHaveTextContent("Last 7 days");
  });

  it("asks the server for the range the reader chose", async () => {
    const user = userEvent.setup();
    renderTabs();
    await screen.findByText("Providers billed");
    await choose(user, "Date range", "Last 7 days");
    await screen.findByText("Providers billed");
    expect(comparisonCall).toHaveBeenLastCalledWith("sk-test", 7);
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
