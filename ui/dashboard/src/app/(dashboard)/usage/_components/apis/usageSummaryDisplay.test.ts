import { describe, expect, it } from "vitest";

import type { ProviderUsageSummaryResponse } from "@/components/networking";
import { evidenceRows, hasUsage, tokenRows } from "./usageSummaryDisplay";

const summary = (overrides: Partial<ProviderUsageSummaryResponse> = {}): ProviderUsageSummaryResponse => ({
  provider: "openrouter",
  display_name: "OpenRouter",
  days: 30,
  total_cost: "0.00780515",
  facts: 50,
  by_model: [{ model: "openai/gpt-4o", billed_cost: "0.0064525" }],
  by_account: [{ credential_name: "openrouter-billing", billed_cost: "0.00780515" }],
  by_evidence: { reconciled: "0.00780515", priced: "0", allocated: "0" },
  tokens: { input_tokens: 3372, output_tokens: 1489, cached_input_tokens: 0, cache_write_tokens: 0 },
  grain: "request",
  delay_note: "delay note",
  settling_note: "settling note",
  ...overrides,
});

describe("hasUsage", () => {
  it("is true when the window recorded at least one fact", () => {
    expect(hasUsage(summary({ facts: 50 }))).toBe(true);
  });

  it("is false when the window recorded no facts, even if a cost field is non-empty", () => {
    expect(hasUsage(summary({ facts: 0 }))).toBe(false);
  });
});

describe("tokenRows", () => {
  it("lists all four token types in a fixed order with their exact counts", () => {
    const tokens = { input_tokens: 3372, output_tokens: 1489, cached_input_tokens: 7, cache_write_tokens: 2 };
    const rows = tokenRows(tokens);

    expect(rows).toEqual([
      { label: "Input tokens", value: 3372 },
      { label: "Output tokens", value: 1489 },
      { label: "Cached input tokens", value: 7 },
      { label: "Cache write tokens", value: 2 },
    ]);
  });
});

describe("evidenceRows", () => {
  it("orders reconciled, priced, then allocated and carries each cost through as a string", () => {
    const rows = evidenceRows({ reconciled: "0.00780515", priced: "0", allocated: "0" });

    expect(rows.map((row) => row.level)).toEqual(["reconciled", "priced", "allocated"]);
    expect(rows[0].cost).toBe("0.00780515");
    expect(typeof rows[0].cost).toBe("string");
    expect(rows[1].cost).toBe("0");
    expect(rows[2].cost).toBe("0");
  });

  it("fills in an explicit zero for a level missing from the map rather than dropping the row", () => {
    const rows = evidenceRows({ reconciled: "12.5" });

    expect(rows).toHaveLength(3);
    expect(rows.find((row) => row.level === "priced")?.cost).toBe("0");
    expect(rows.find((row) => row.level === "allocated")?.cost).toBe("0");
  });

  it("does not round or reformat a long decimal cost", () => {
    const rows = evidenceRows({ reconciled: "0.123456789012345", priced: "0", allocated: "0" });

    expect(rows[0].cost).toBe("0.123456789012345");
  });

  it("tells the reader how much to trust each level, in plain language a finance reader can act on", () => {
    const rows = evidenceRows({ reconciled: "1", priced: "1", allocated: "1" });

    expect(rows.find((row) => row.level === "reconciled")?.description).toBe(
      "The provider billed this amount. These are their figures, not ours.",
    );
    expect(rows.find((row) => row.level === "priced")?.description).toBe(
      "The provider reported the usage but not the cost, so we applied their published rates.",
    );
    expect(rows.find((row) => row.level === "allocated")?.description).toBe(
      "The provider has not reported this at all. It is our own estimate from traffic that passed through the gateway, and it may change.",
    );
  });
});
