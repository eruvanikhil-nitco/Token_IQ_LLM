import { describe, expect, it } from "vitest";

import { STATE_EXPLANATION, STATE_LABEL, formatAmount, needsAttention } from "./gapDisplay";
import type { UnallocatedLine } from "@/components/networking";

const line = (overrides: Partial<UnallocatedLine> = {}): UnallocatedLine => ({
  day: "2026-09-15",
  provider: "openrouter",
  credential_name: "openrouter-billing",
  provider_cost: "0.00774700",
  gateway_cost: "0",
  gap: "0.00774700",
  state: "unallocated",
  owner_type: null,
  owner_id: null,
  rule_id: null,
  ...overrides,
});

describe("formatAmount", () => {
  it("keeps every digit the provider billed rather than rounding for display", () => {
    expect(formatAmount("0.00774700")).toBe("$0.00774700");
  });

  it("shows a dash when the provider reported nothing, never a zero", () => {
    expect(formatAmount(null)).toBe("—");
  });
});

describe("state copy", () => {
  it("never tells the reader the two sources agree when the provider said nothing", () => {
    expect(STATE_LABEL.no_provider_data).not.toMatch(/match/i);
    expect(STATE_EXPLANATION.no_provider_data).toMatch(/reported nothing/i);
  });

  it("describes an unclaimed gap as unclaimed rather than as an error", () => {
    expect(STATE_LABEL.unallocated).toBe("No rule matches");
  });

  it("has copy for every state the backend can send", () => {
    const states = ["owned", "unallocated", "matched", "not_settled", "no_provider_data"] as const;
    states.forEach((state) => {
      expect(STATE_LABEL[state]).toBeTruthy();
      expect(STATE_EXPLANATION[state]).toBeTruthy();
    });
  });
});

describe("needsAttention", () => {
  it("flags only spend that is real and unclaimed", () => {
    expect(needsAttention(line())).toBe(true);
    expect(needsAttention(line({ state: "owned" }))).toBe(false);
    expect(needsAttention(line({ state: "matched" }))).toBe(false);
    expect(needsAttention(line({ state: "not_settled" }))).toBe(false);
    expect(needsAttention(line({ state: "no_provider_data" }))).toBe(false);
  });
});
