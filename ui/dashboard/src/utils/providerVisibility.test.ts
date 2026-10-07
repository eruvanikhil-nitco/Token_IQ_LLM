import { describe, expect, it } from "vitest";
import { filterModelsByVisibleProviders, isObservedOnly } from "./providerVisibility";
import type { ModelHubData } from "@/components/AIHub/ModelHubTableColumns";

const model = (model_group: string, providers: string[], extra: Partial<ModelHubData> = {}): ModelHubData =>
  ({ model_group, providers, ...extra }) as ModelHubData;

describe("filterModelsByVisibleProviders", () => {
  const models = [
    model("openrouter/openai/gpt-4o", ["openrouter"]),
    model("anthropic-haiku-4-5", ["anthropic"]),
    model("bedrock-sonnet", ["bedrock"]),
  ];

  it("keeps only models served by a provider the gateway is set up for", () => {
    // The sample config leaves anthropic and bedrock deployments that cannot be called.
    expect(filterModelsByVisibleProviders(models, ["openrouter"]).map((m) => m.model_group)).toEqual([
      "openrouter/openai/gpt-4o",
    ]);
  });

  it("keeps everything when the provider list is not known yet", () => {
    // Undefined means the overview has not answered, or the caller is unauthenticated on
    // the public hub. Blanking the page in either case would be worse.
    expect(filterModelsByVisibleProviders(models, undefined)).toHaveLength(3);
  });

  it("hides everything when no provider is set up, rather than falling back to all", () => {
    expect(filterModelsByVisibleProviders(models, [])).toEqual([]);
  });

  it("keeps an observed-only row whose provider column was blank", () => {
    const observed = model("mystery-model", [], { is_observed_only: true });

    // It exists because traffic happened; there is nothing to match it on.
    expect(filterModelsByVisibleProviders([observed], ["openrouter"])).toHaveLength(1);
  });

  it("keeps a model served by any one of several providers", () => {
    const shared = model("gpt-4", ["azure_ai", "openai"]);

    expect(filterModelsByVisibleProviders([shared], ["openai"])).toHaveLength(1);
    expect(filterModelsByVisibleProviders([shared], ["bedrock"])).toHaveLength(0);
  });

  it("treats a model with no providers as not set up", () => {
    expect(filterModelsByVisibleProviders([model("orphan", [])], ["openai"])).toEqual([]);
  });
});

describe("isObservedOnly", () => {
  it("is true only for a row built from traffic", () => {
    expect(isObservedOnly(model("x", [], { is_observed_only: true }))).toBe(true);
    expect(isObservedOnly(model("x", ["openai"]))).toBe(false);
  });
});
