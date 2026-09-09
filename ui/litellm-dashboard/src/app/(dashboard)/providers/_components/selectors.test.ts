import { describe, expect, it } from "vitest";
import { isObservedOnly } from "@/utils/providerVisibility";
import {
  filterModelsByProvider,
  filterProviderRows,
  hasUsage,
  indexUsageByModel,
  observedOnlyModels,
  usageWindowLabel,
  type ModelUsageRow,
} from "./selectors";
import type { ProviderRow } from "./types";

const providerRow = (provider: string): ProviderRow => ({
  provider,
  models_configured: 1,
  models_in_catalogue: 10,
  has_credentials: true,
  is_configured: true,
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
      { model_group: "gpt-4o", providers: ["openai"], requests: 5, tokens: 100, spend: 0.01 },
      { model_group: "haiku", providers: ["anthropic"], requests: 2, tokens: 20, spend: 0.001 },
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
    const untrafficked: ModelUsageRow = { model_group: "x", providers: [], requests: 0, tokens: 0, spend: 0 };

    expect(hasUsage(untrafficked)).toBe(false);
  });

  it("is true for requests with zero spend, which is a real case not an empty one", () => {
    // gpt-4o-mini genuinely records requests and no spend, and must not be hidden
    // behind the same dash as a model that was never called.
    const freeButCalled: ModelUsageRow = {
      model_group: "gpt-4o-mini",
      providers: ["openai"],
      requests: 2,
      tokens: 0,
      spend: 0,
    };

    expect(hasUsage(freeButCalled)).toBe(true);
  });
});

describe("observedOnlyModels", () => {
  const configured = [{ model_group: "gpt-4", providers: ["openai"] }] as unknown as Parameters<
    typeof observedOnlyModels
  >[0];

  const baseUsage: ModelUsageRow = {
    model_group: "openrouter/openai/gpt-4o",
    providers: ["openrouter"],
    requests: 24,
    tokens: 1458,
    spend: 0.00642,
  };

  const usage = (overrides: Partial<ModelUsageRow> = {}): ModelUsageRow => ({ ...baseUsage, ...overrides });

  it("builds a row for a model that served traffic but is no longer configured", () => {
    const rows = observedOnlyModels(configured, [usage()]);

    // Dropping it would hide real spend, which is the opposite of an observer gateway.
    expect(rows).toHaveLength(1);
    expect(rows[0].model_group).toBe("openrouter/openai/gpt-4o");
    expect(rows[0].providers).toEqual(["openrouter"]);
    expect(isObservedOnly(rows[0])).toBe(true);
  });

  it("does not duplicate a model that is still configured", () => {
    expect(observedOnlyModels(configured, [usage({ model_group: "gpt-4", providers: ["openai"] })])).toEqual([]);
  });

  it("ignores a usage row with no requests, which would add an empty row", () => {
    expect(observedOnlyModels(configured, [usage({ requests: 0 })])).toEqual([]);
  });

  it("marks configured models as not observed-only, so the flag means something", () => {
    expect(isObservedOnly(configured[0])).toBe(false);
  });

  it("keeps the provider so the row survives the provider filter", () => {
    const rows = observedOnlyModels(configured, [usage()]);

    expect(filterModelsByProvider(rows, "openrouter")).toHaveLength(1);
    expect(filterModelsByProvider(rows, "anthropic")).toHaveLength(0);
  });
});
