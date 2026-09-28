import { describe, expect, it } from "vitest";

import { STATUS_EXPLANATION, STATUS_LABEL, formatAmount, needsAttention, ownerOf } from "./comparisonDisplay";
import type { ComparisonDay } from "@/components/networking";

const row = (overrides: Partial<ComparisonDay> = {}): ComparisonDay => ({
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
  ...overrides,
});

describe("status copy", () => {
  it("never tells the reader the two sources agree when the provider said nothing", () => {
    expect(STATUS_LABEL.no_provider_data).not.toMatch(/match/i);
    expect(STATUS_EXPLANATION.no_provider_data).toMatch(/reported nothing/i);
  });

  it("calls a settling day settling rather than a gap", () => {
    expect(STATUS_LABEL.not_settled).toBe("Not settled yet");
  });

  it("has copy for every status the backend can send", () => {
    (["matched", "gap", "not_settled", "no_provider_data"] as const).forEach((status) => {
      expect(STATUS_LABEL[status]).toBeTruthy();
      expect(STATUS_EXPLANATION[status]).toBeTruthy();
    });
  });
});

describe("formatAmount", () => {
  it("keeps every digit the provider billed rather than rounding for display", () => {
    expect(formatAmount("0.00774700")).toBe("$0.00774700");
  });

  it("shows a dash, never a zero, when the provider reported nothing", () => {
    expect(formatAmount(null)).toBe("—");
  });
});

describe("ownerOf", () => {
  it("names the owner a rule assigned", () => {
    expect(ownerOf(row({ owner_type: "team", owner_id: "t-1" }))).toBe("team: t-1");
  });

  it("shows a dash rather than inventing an owner", () => {
    expect(ownerOf(row())).toBe("—");
  });
});

describe("needsAttention", () => {
  it("flags a difference nobody has claimed", () => {
    expect(needsAttention(row())).toBe(true);
  });

  it("does not flag a difference a rule already assigned", () => {
    expect(needsAttention(row({ owner_type: "team", owner_id: "t-1" }))).toBe(false);
  });

  it("does not flag a settling day or a silent provider as needing attention", () => {
    expect(needsAttention(row({ status: "not_settled" }))).toBe(false);
    expect(needsAttention(row({ status: "no_provider_data" }))).toBe(false);
    expect(needsAttention(row({ status: "matched" }))).toBe(false);
  });
});
