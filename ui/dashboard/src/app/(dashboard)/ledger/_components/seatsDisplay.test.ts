import { describe, expect, it } from "vitest";

import { CADENCE_LABEL, hasNoSeats, isIncomplete } from "./seatsDisplay";
import type { UserCost } from "@/components/networking";

const cost = (overrides: Partial<UserCost> = {}): UserCost => ({
  user_id: "u-1",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency: "USD",
  gateway: "10",
  seats: "30",
  total: "40",
  seat_lines: [{ tool: "claude-code", currency: "USD", amount: "30" }],
  tool_usage_known: false,
  note: "This covers gateway traffic and subscriptions.",
  ...overrides,
});

describe("isIncomplete", () => {
  it("warns while no user tool is connected", () => {
    expect(isIncomplete(cost())).toBe(true);
  });

  it("stops warning on its own once tool usage is known, rather than needing a code change", () => {
    expect(isIncomplete(cost({ tool_usage_known: true }))).toBe(false);
  });
});

describe("hasNoSeats", () => {
  it("is true when this person holds nothing in the currency asked for", () => {
    expect(hasNoSeats(cost({ seat_lines: [] }))).toBe(true);
  });

  it("is false when a subscription is listed", () => {
    expect(hasNoSeats(cost())).toBe(false);
  });
});

describe("cadence copy", () => {
  it("has copy for every cadence the backend can send", () => {
    (["monthly", "annual"] as const).forEach((c) => expect(CADENCE_LABEL[c]).toBeTruthy());
  });
});
