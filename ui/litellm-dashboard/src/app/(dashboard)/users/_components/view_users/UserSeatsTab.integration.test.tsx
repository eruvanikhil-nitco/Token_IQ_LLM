import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UserSeatsTab from "./UserSeatsTab";
import type { UserCost } from "@/components/networking";

const NOTE =
  "This covers gateway traffic and subscriptions. It does not include what this person spent " +
  "inside Claude Code, Copilot, Cursor or Codex, because no user tool is connected.";

const WITH_SEAT: UserCost = {
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
};

const NO_SEATS: UserCost = { ...WITH_SEAT, seats: "0", total: "10", seat_lines: [] };

const COMPLETE: UserCost = { ...WITH_SEAT, tool_usage_known: true };

const userCostCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  userCostCall: (...args: unknown[]) => userCostCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "internal_user" }),
}));

const renderTab = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <UserSeatsTab userId="u-1" />
    </QueryClientProvider>,
  );
};

describe("UserSeatsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    userCostCall.mockResolvedValue(WITH_SEAT);
  });

  it("shows this person's gateway spend and subscriptions separately", async () => {
    renderTab();
    expect(await screen.findByText("$10")).toBeInTheDocument();
    expect(screen.getByText("$40")).toBeInTheDocument();
    // Twice on purpose: the subscriptions card and the line it is made of. Counting them pins
    // that the headline figure agrees with the item beneath it.
    expect(screen.getAllByText("$30")).toHaveLength(2);
  });

  it("names the part that is missing rather than implying the total is complete", async () => {
    renderTab();
    expect(await screen.findByText(/does not include/i)).toBeInTheDocument();
  });

  it("stops warning once tool usage is counted, without needing a code change", async () => {
    userCostCall.mockResolvedValue(COMPLETE);
    renderTab();
    await screen.findByText("$40");
    expect(screen.queryByText(/does not include/i)).not.toBeInTheDocument();
  });

  it("says a person with no subscription has none, rather than showing a blank", async () => {
    userCostCall.mockResolvedValue(NO_SEATS);
    renderTab();
    expect(await screen.findByText("No subscriptions assigned to this person.")).toBeInTheDocument();
  });

  it("names each subscription rather than only their sum", async () => {
    renderTab();
    expect(await screen.findByText("claude-code")).toBeInTheDocument();
  });

  it("says which period the total covers", async () => {
    renderTab();
    expect(await screen.findByText(/2026-09-01 to 2026-09-30/)).toBeInTheDocument();
  });

  it("asks only for this person's cost, never everyone's", async () => {
    renderTab();
    await screen.findByText("$40");
    expect(userCostCall).toHaveBeenCalledWith("sk-test", "u-1", expect.any(String), expect.any(String), "USD");
  });
});
