import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CostExplorerView from "./CostExplorerView";
import type { ExplorerResponse } from "@/components/networking";

const TEAM: ExplorerResponse = {
  dimension: "team",
  days: 30,
  slices: [
    { key: "t-1", through_gateway: "0.0052126", outside_gateway: "0" },
    { key: "t-2", through_gateway: "0.0013208", outside_gateway: "0" },
  ],
  total_through_gateway: "0.00797225",
  total_outside_gateway: "0.00774700",
  unallocated_to_a_slice: "0.00143880",
  unattributable_outside_gateway: "0.00774700",
  note: "Some spend that bypassed the gateway has no rule assigning it to an owner.",
};

const EMPTY_PROJECT: ExplorerResponse = {
  dimension: "project",
  days: 30,
  slices: [],
  total_through_gateway: "0",
  total_outside_gateway: "0",
  unallocated_to_a_slice: "0",
  unattributable_outside_gateway: "0",
  note: "No project spend recorded in this window.",
};

const explorerCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  combinedExplorerCall: (...args: unknown[]) => explorerCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderView = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CostExplorerView days={30} />
    </QueryClientProvider>,
  );
};

describe("CostExplorerView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    explorerCall.mockResolvedValue(TEAM);
  });

  it("names both sources so identity is never colour alone", async () => {
    renderView();
    // Twice each on purpose: once in the legend beside the swatch, once on the summary card.
    // The legend is what stops colour being the only thing telling the two series apart.
    expect(await screen.findAllByText("Through the gateway")).toHaveLength(2);
    expect(screen.getAllByText("Outside the gateway")).toHaveLength(2);
  });

  it("keeps every digit rather than rounding a total for display", async () => {
    renderView();
    expect(await screen.findByText("$0.00797225")).toBeInTheDocument();
    expect(screen.getByText("$0.00774700")).toBeInTheDocument();
  });

  it("names gateway spend the grouping cannot place rather than letting the bars under-add", async () => {
    renderView();
    expect(await screen.findByText(/\$0\.00143880 of that has no team recorded/)).toBeInTheDocument();
  });

  it("names outside-gateway spend nobody owns", async () => {
    renderView();
    expect(await screen.findByText(/\$0\.00774700 of that is money nobody owns/)).toBeInTheDocument();
  });

  it("says a grouping has no spend rather than drawing an empty chart", async () => {
    explorerCall.mockResolvedValue(EMPTY_PROJECT);
    renderView();
    fireEvent.change(screen.getByLabelText("Group by"), { target: { value: "project" } });
    expect(await screen.findByText("No project spend recorded in this window.")).toBeInTheDocument();
  });

  it("asks the server for the grouping the reader chose", async () => {
    renderView();
    await screen.findByText("$0.00797225");
    fireEvent.change(screen.getByLabelText("Group by"), { target: { value: "model" } });
    await screen.findByText("$0.00797225");
    expect(explorerCall).toHaveBeenLastCalledWith("sk-test", "model", 30);
  });
});
