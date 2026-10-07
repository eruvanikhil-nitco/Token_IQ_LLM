import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SeatsView from "./SeatsView";
import type { SeatListResponse, UserCostListResponse } from "@/components/networking";

const NOTE =
  "This covers gateway traffic and subscriptions. It does not include what this person spent " +
  "inside Claude Code, Copilot, Cursor or Codex, because no user tool is connected.";

const COSTS: UserCostListResponse = {
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency: "USD",
  costs: [
    {
      user_id: "u-1",
      period_start: "2026-09-01",
      period_end: "2026-09-30",
      currency: "USD",
      gateway: "10",
      seats: "30",
      total: "40",
      seat_lines: [{ tool: "claude-code", currency: "USD", amount: "30" }],
      tool_usage_known: false,
      note: NOTE,
    },
    {
      user_id: "u-2",
      period_start: "2026-09-01",
      period_end: "2026-09-30",
      currency: "USD",
      gateway: "5",
      seats: "0",
      total: "5",
      seat_lines: [],
      tool_usage_known: false,
      note: NOTE,
    },
  ],
};

const NO_SEATS: SeatListResponse = { seats: [] };

const SAVED_SEAT = {
  seat_id: "s1",
  tool: "claude-code",
  user_id: "u-1",
  cadence: "monthly",
  currency: "USD",
  amount: "30.00",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  note: null,
} as const;

const seatsCall = vi.fn();
const userCostsCall = vi.fn();
const upsertCall = vi.fn();
const deleteCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  seatsCall: (...args: unknown[]) => seatsCall(...args),
  userCostsCall: (...args: unknown[]) => userCostsCall(...args),
  upsertSeatCall: (...args: unknown[]) => upsertCall(...args),
  deleteSeatCall: (...args: unknown[]) => deleteCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderView = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SeatsView periodStart="2026-09-01" periodEnd="2026-09-30" />
    </QueryClientProvider>,
  );
};

describe("SeatsView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seatsCall.mockResolvedValue(NO_SEATS);
    userCostsCall.mockResolvedValue(COSTS);
    upsertCall.mockResolvedValue(SAVED_SEAT);
  });

  it("shows a person's cost with its parts, not one blended number", async () => {
    renderView();
    expect(await screen.findByText("$40")).toBeInTheDocument();
    expect(screen.getByText("$10")).toBeInTheDocument();
    expect(screen.getByText("$30")).toBeInTheDocument();
  });

  it("says the total does not include what a person spent inside their tools", async () => {
    renderView();
    expect(await screen.findByText(/does not include/i)).toBeInTheDocument();
  });

  it("says a person with no subscription has gateway traffic only, rather than showing a blank", async () => {
    renderView();
    expect(await screen.findByText("gateway traffic only")).toBeInTheDocument();
  });

  it("will not save a seat with no amount", async () => {
    renderView();
    fireEvent.change(await screen.findByLabelText("Person"), { target: { value: "u-1" } });
    expect(screen.getByRole("button", { name: "Save seat" })).toBeDisabled();
  });

  it("will not save a seat with no person", async () => {
    renderView();
    fireEvent.change(await screen.findByLabelText("Seat amount"), { target: { value: "30" } });
    expect(screen.getByRole("button", { name: "Save seat" })).toBeDisabled();
  });

  it("sends the seat an admin typed, for the period they chose", async () => {
    const user = userEvent.setup();
    renderView();
    fireEvent.change(await screen.findByLabelText("Person"), { target: { value: " u-1 " } });
    fireEvent.change(screen.getByLabelText("Seat amount"), { target: { value: " 30.00 " } });
    await user.click(screen.getByRole("button", { name: "Save seat" }));

    const expected = {
      tool: "claude-code",
      user_id: "u-1",
      cadence: "monthly",
      currency: "USD",
      amount: "30.00",
      period_start: "2026-09-01",
      period_end: "2026-09-30",
    };
    expect(upsertCall).toHaveBeenCalledWith("sk-test", expect.objectContaining(expected));
  });

  it("says no subscriptions are assigned rather than leaving the tab blank", async () => {
    renderView();
    expect(await screen.findByText("No subscriptions assigned yet.")).toBeInTheDocument();
  });

  it("tells an admin when a removal failed, so they do not assume it worked", async () => {
    const user = userEvent.setup();
    seatsCall.mockResolvedValue({ seats: [SAVED_SEAT] });
    deleteCall.mockRejectedValueOnce(new Error("nope"));
    renderView();

    await user.click(await screen.findByRole("button", { name: "Remove the claude-code seat for u-1" }));
    expect(await screen.findByText(/could not remove that seat/i)).toBeInTheDocument();
  });
});
