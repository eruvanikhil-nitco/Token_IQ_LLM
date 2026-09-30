import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OverviewPanel from "./OverviewPanel";
import type { OverviewResponse } from "@/components/networking";

const overviewCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  overviewCall: (...args: unknown[]) => overviewCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const response = (over: Partial<OverviewResponse> = {}): OverviewResponse => ({
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency: "USD",
  total: "0.00780515",
  previous_total: null,
  change: null,
  attributed: "0.00797225",
  unallocated: "0.00774700",
  unallocated_share: "99.3",
  providers: [
    { provider: "openrouter", billed: "0.00780515", recorded: "0.00794405", status: "gateway_saw_more" },
  ],
  recommendations: [
    {
      rule_id: "escaped_spend",
      title: "Spend is reaching providers without going through the gateway",
      kind: "business",
      figure: "0.00774700",
      figure_kind: "already_spent_unwatched",
      currency: "USD",
    },
  ],
  freshness: [{ source: "openrouter", last_sync_at: "2026-09-18T11:11:46+00:00" }],
  ...over,
});

const renderPanel = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OverviewPanel />
    </QueryClientProvider>,
  );
};

describe("OverviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    overviewCall.mockResolvedValue(response());
  });

  it("shows the headline total the server computed, digits intact", async () => {
    renderPanel();
    const tile = (await screen.findByText(/total spend/i)).closest("div[data-slot='card']");

    expect(tile).toHaveTextContent("$0.00780515");
  });

  it("never presents the gateway figure as part of what was spent", async () => {
    /* The product's oldest rule. The gateway number belongs on this page as attribution, and
       a label calling it spend would invite a reader to add the two together. */
    renderPanel();
    const tile = (await screen.findByText(/attributed through the gateway/i)).closest("div[data-slot='card']");

    expect(tile).not.toBeNull();
    expect(tile).toHaveTextContent(/never added to the total/i);
  });

  it("says there is no earlier period rather than leaving a blank beside the total", async () => {
    renderPanel();

    expect(await screen.findByText(/no earlier period to compare/i)).toBeInTheDocument();
  });

  it("tells a rise from a fall in words", async () => {
    overviewCall.mockResolvedValue(response({ previous_total: "0.004", change: "0.0038" }));
    renderPanel();

    expect(await screen.findByText(/up \$0\.0038 on the period before/i)).toBeInTheDocument();
  });

  it("shows what nobody owns with its share of what providers billed", async () => {
    renderPanel();
    const tile = (await screen.findByText(/nobody owns/i)).closest("div[data-slot='card']");

    expect(tile).toHaveTextContent("$0.00774700");
    expect(tile).toHaveTextContent(/99\.3% of what providers billed/i);
  });

  it("states each provider's standing in words, not by colour alone", async () => {
    renderPanel();

    expect(await screen.findByText("openrouter")).toBeInTheDocument();
    expect(screen.getByText(/gateway recorded more than billed/i)).toBeInTheDocument();
  });

  it("shows the top recommendations and links to the rest rather than repeating them", async () => {
    renderPanel();

    expect(await screen.findByText(/spend is reaching providers/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /all recommendations/i })).toHaveAttribute(
      "href",
      expect.stringContaining("recommendations"),
    );
  });

  it("says when each source last reported", async () => {
    renderPanel();

    expect(await screen.findByText(/openrouter:/i)).toBeInTheDocument();
  });

  it("says a source has never reported rather than leaving it blank", async () => {
    overviewCall.mockResolvedValue(response({ freshness: [{ source: "azure", last_sync_at: null }] }));
    renderPanel();

    expect(await screen.findByText("Never")).toBeInTheDocument();
  });

  it("an empty period says nothing is recorded, not that nothing was spent", async () => {
    /* The difference between "you are not connected yet" and "you are free" is the whole
       value of this screen on day one. */
    overviewCall.mockResolvedValue(
      response({
        total: null,
        attributed: null,
        unallocated: null,
        unallocated_share: null,
        providers: [],
        recommendations: [],
        freshness: [],
      }),
    );
    renderPanel();

    expect(await screen.findByText(/nothing has been recorded for this period yet/i)).toBeInTheDocument();
    expect(screen.getByText(/not the same as spending nothing/i)).toBeInTheDocument();
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
  });

  it("says so when the overview cannot be read at all", async () => {
    overviewCall.mockRejectedValue(new Error("nope"));
    renderPanel();

    expect(await screen.findByText(/could not read the overview/i)).toBeInTheDocument();
  });
});
