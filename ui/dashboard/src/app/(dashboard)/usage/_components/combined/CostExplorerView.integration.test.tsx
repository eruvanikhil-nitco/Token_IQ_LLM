import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CostExplorerView from "./CostExplorerView";
import type { ExplorerResponse } from "@/components/networking";

const TEAM: ExplorerResponse = {
  dimension: "team",
  days: 30,
  slices: [
    { key: "t-1", name: "Platform", through_gateway: "0.0052126", outside_gateway: "0" },
    { key: "t-2", name: "t-2", through_gateway: "0.0013208", outside_gateway: "0" },
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

/** The grouping is a Base UI select: it answers to real clicks, not to a raw change event. */
const choose = async (user: ReturnType<typeof userEvent.setup>, control: string, option: string) => {
  await user.click(screen.getByRole("combobox", { name: control }));
  await user.click(await screen.findByRole("option", { name: option }));
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

  it("rounds a total for reading while keeping a sub-cent amount visible", async () => {
    renderView();
    expect(await screen.findByText("$0.008")).toBeInTheDocument();
    expect(screen.getByText("$0.0077")).toBeInTheDocument();
  });

  it("names gateway spend the grouping cannot place rather than letting the bars under-add", async () => {
    renderView();
    expect(await screen.findByText(/\$0\.0014 of that has no team recorded/)).toBeInTheDocument();
  });

  it("names outside-gateway spend nobody owns", async () => {
    renderView();
    expect(await screen.findByText(/\$0\.0077 of that is money nobody owns/)).toBeInTheDocument();
  });

  it("says a grouping has no spend rather than drawing an empty chart", async () => {
    const user = userEvent.setup();
    explorerCall.mockResolvedValue(EMPTY_PROJECT);
    renderView();
    await choose(user, "Group by", "Project");
    expect(await screen.findByText("No project spend recorded in this window.")).toBeInTheDocument();
  });

  it("asks the server for the grouping the reader chose", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByText("$0.008");
    await choose(user, "Group by", "Model");
    await screen.findByText("$0.008");
    expect(explorerCall).toHaveBeenLastCalledWith("sk-test", "model", 30);
  });

  it("calls a team by its name rather than by the uuid in the database", async () => {
    // The explorer grouped by team_id and printed that id, so a reader looking for what their
    // own team spent had nothing on the page to recognise.
    renderView();
    expect(await screen.findByText("Platform")).toBeInTheDocument();
  });

  it("still shows the identifier, because that is what a rule is written against", async () => {
    renderView();
    expect(await screen.findByText("t-1")).toBeInTheDocument();
  });

  it("does not print the identifier twice for a spender that has no name", async () => {
    // t-2 has no name, so the server sends the id as the name. Printing both would read as
    // "t-2 t-2".
    renderView();
    expect(await screen.findAllByText("t-2")).toHaveLength(1);
  });
});
