import { describe, expect, it } from "vitest";
import {
  filterModelsByProvider,
  filterProviderRows,
  hasUsage,
  indexUsageByModel,
  usageWindowLabel,
  type ModelUsageRow,
} from "./selectors";
import type { ProviderRow } from "./types";

const providerRow = (provider: string): ProviderRow => ({
  provider,
  models_configured: 1,
  models_in_catalogue: 10,
  has_credentials: true,
  requests: 0,
  spend: 0,
  last_used: null,
});

describe("usageWindowLabel", () => {
  it("never claims a rolling 24 hours, because the rollup cannot answer one", () => {
    expect(usageWindowLabel(1)).not.toContain("24");
    expect(usageWindowLabel(2)).not.toContain("24");
    expect(usageWindowLabel(30)).not.toContain("24");
  });

  it("names a single day as today rather than 'Last 1 UTC days'", () => {
    expect(usageWindowLabel(1)).toBe("Today (UTC)");
  });

  it("counts whole UTC days for a longer window", () => {
    expect(usageWindowLabel(7)).toBe("Last 7 UTC days");
  });
});

describe("filterProviderRows", () => {
  const rows = [providerRow("openrouter"), providerRow("anthropic")];

  it("returns every row when no provider is selected", () => {
    expect(filterProviderRows(rows, null)).toHaveLength(2);
  });

  it("narrows to the selected provider", () => {
    expect(filterProviderRows(rows, "anthropic").map((r) => r.provider)).toEqual(["anthropic"]);
  });

  it("returns nothing for a provider that has no row, rather than falling back to all", () => {
    expect(filterProviderRows(rows, "bedrock")).toEqual([]);
  });
});

describe("filterModelsByProvider", () => {
  const models = [
    { model_group: "a", providers: ["openrouter"] },
    { model_group: "b", providers: ["anthropic", "bedrock"] },
    { model_group: "c" },
  ];

  it("returns every model when no provider is selected", () => {
    expect(filterModelsByProvider(models, null)).toHaveLength(3);
  });

  it("matches membership, so a model served by several providers is found under each", () => {
    expect(filterModelsByProvider(models, "bedrock").map((m) => m.model_group)).toEqual(["b"]);
    expect(filterModelsByProvider(models, "anthropic").map((m) => m.model_group)).toEqual(["b"]);
  });

  it("drops a model with no providers rather than throwing on the missing field", () => {
    expect(filterModelsByProvider(models, "openrouter").map((m) => m.model_group)).toEqual(["a"]);
  });
});

describe("indexUsageByModel", () => {
  it("keys usage by model group so a row can look up its own", () => {
    const usage: ModelUsageRow[] = [
      { model_group: "gpt-4o", requests: 5, tokens: 100, spend: 0.01 },
      { model_group: "haiku", requests: 2, tokens: 20, spend: 0.001 },
    ];

    const index = indexUsageByModel(usage);

    expect(index.get("gpt-4o")?.requests).toBe(5);
    expect(index.get("never-called")).toBeUndefined();
  });

  it("is empty for no usage, so every row reads as untrafficked", () => {
    expect(indexUsageByModel([]).size).toBe(0);
  });
});

describe("hasUsage", () => {
  it("is false for a model absent from the range", () => {
    expect(hasUsage(undefined)).toBe(false);
  });

  it("is false for zero requests, so an untrafficked model shows a dash not zeros", () => {
    expect(hasUsage({ model_group: "x", requests: 0, tokens: 0, spend: 0 })).toBe(false);
  });

  it("is true for requests with zero spend, which is a real case not an empty one", () => {
    // gpt-4o-mini genuinely records requests and no spend, and must not be hidden
    // behind the same dash as a model that was never called.
    expect(hasUsage({ model_group: "gpt-4o-mini", requests: 2, tokens: 0, spend: 0 })).toBe(true);
  });
});
