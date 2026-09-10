import { describe, expect, it } from "vitest";
import {
  buildRowPatch,
  changedFields,
  describeRate,
  errorsOf,
  hasErrors,
  isDirty,
  isEditable,
  isFromPriceList,
  isOverridden,
  modelId,
  ptuCountOf,
  ratesOf,
  type ModelRow,
  type RateText,
} from "./pricingRows";

const text = (values: Partial<RateText> = {}): RateText => ({
  input: "",
  output: "",
  cacheRead: "",
  cacheWrite: "",
  ...values,
});

/** Modelled on openrouter/openai/gpt-4o-mini as the live proxy returns it. */
const mapPriced: ModelRow = {
  model_name: "openrouter/openai/gpt-4o-mini",
  model_info: { id: "m1", db_model: true, input_cost_per_token: 0.00000015, output_cost_per_token: 0.0000006 },
  litellm_params: {},
};

/** Modelled on anthropic-haiku-4-5, which is declared in the config file. */
const configPriced: ModelRow = {
  model_name: "anthropic-haiku-4-5",
  model_info: { id: "m2", db_model: false },
  litellm_params: { input_cost_per_token: 0.000001, output_cost_per_token: 0.000005 },
};

describe("what a row can do", () => {
  it("edits a database-backed model", () => {
    expect(isEditable(mapPriced)).toBe(true);
  });

  it("refuses to edit a config file model, which the API cannot patch", () => {
    expect(isEditable(configPriced)).toBe(false);
  });

  it("reads the model's id", () => {
    expect(modelId(mapPriced)).toBe("m1");
  });
});

describe("reading rates onto a row", () => {
  it("shows a rate the deployment sets", () => {
    expect(ratesOf(configPriced)).toMatchObject({ input: "1", output: "5" });
  });

  it("shows the built-in rate when the deployment sets none", () => {
    // A blank here would suggest the model is free rather than priced elsewhere.
    expect(ratesOf(mapPriced)).toMatchObject({ input: "0.15", output: "0.6" });
  });

  it("leaves a rate nobody sets blank", () => {
    expect(ratesOf(mapPriced).cacheWrite).toBe("");
  });

  it("calls a shown rate the price list's when the deployment does not set it", () => {
    expect(isFromPriceList(mapPriced, "input", ratesOf(mapPriced))).toBe(true);
  });

  it("does not call a rate the price list's when the deployment sets it", () => {
    expect(isFromPriceList(configPriced, "input", ratesOf(configPriced))).toBe(false);
  });

  it("says nothing about a rate nobody sets at all", () => {
    // There is no rate to attribute, so labelling it would be noise.
    expect(isFromPriceList(mapPriced, "cacheWrite", ratesOf(mapPriced))).toBe(false);
  });

  it("marks which rates are the deployment's own", () => {
    expect(isOverridden(configPriced, "input")).toBe(true);
    expect(isOverridden(mapPriced, "input")).toBe(false);
  });

  it("reads a PTU count, which forbids a usage rate on top", () => {
    expect(ptuCountOf({ ...mapPriced, model_info: { id: "m3", db_model: true, ptu_count: 15 } })).toBe("15");
    expect(ptuCountOf(mapPriced)).toBeUndefined();
  });
});

describe("tracking what changed", () => {
  it("notices nothing when a row is untouched", () => {
    expect(isDirty(text({ input: "1" }), text({ input: "1" }))).toBe(false);
  });

  it("notices an edited rate", () => {
    expect(changedFields(text({ input: "2" }), text({ input: "1" }))).toEqual(new Set(["input"]));
  });

  it("notices a cleared rate, which is how an override gets removed", () => {
    expect(changedFields(text(), text({ input: "1" }))).toEqual(new Set(["input"]));
  });

  it("ignores surrounding whitespace rather than calling it a change", () => {
    expect(isDirty(text({ input: " 1 " }), text({ input: "1" }))).toBe(false);
  });
});

describe("building the save", () => {
  it("sends only what changed, so saving one rate leaves the others alone", () => {
    const patch = buildRowPatch(text({ input: "2", output: "5" }), text({ input: "1", output: "5" }));

    expect(patch.litellm_params).toMatchObject({ input_cost_per_token: 0.000002 });
    expect(patch.litellm_params).not.toHaveProperty("output_cost_per_token");
  });

  it("converts the per-million figure to what the backend stores", () => {
    expect(buildRowPatch(text({ output: "10" }), text()).litellm_params).toMatchObject({
      output_cost_per_token: 0.00001,
    });
  });

  it("clears a rate with an explicit null, not by leaving it out", () => {
    // Leaving it out means "leave as is" under PATCH, and the old override would survive.
    expect(buildRowPatch(text({ output: "" }), text({ output: "5" })).litellm_params).toMatchObject({
      output_cost_per_token: null,
    });
  });

  it("sends nothing when the row is untouched", () => {
    expect(buildRowPatch(text({ input: "1" }), text({ input: "1" })).litellm_params).toEqual({});
  });
});

describe("validation", () => {
  it("accepts a normal rate", () => {
    expect(hasErrors(text({ input: "1.5" }), undefined)).toBe(false);
  });

  it("rejects a rate that is not a number", () => {
    expect(errorsOf(text({ input: "free" }), undefined)).toEqual({ input: "not-a-number" });
  });

  it("rejects a negative rate", () => {
    expect(errorsOf(text({ output: "-1" }), undefined)).toEqual({ output: "negative" });
  });

  it("rejects a usage rate on a PTU deployment, which already paid for throughput", () => {
    expect(errorsOf(text({ input: "3" }), "15")).toEqual({ input: "ptu-conflict" });
  });
});

describe("describeRate", () => {
  it("shows a dash where there is no rate", () => {
    expect(describeRate(text(), "cacheWrite")).toBe("—");
  });

  it("shows the rate with its unit", () => {
    expect(describeRate(text({ input: "1.5" }), "input")).toBe("$1.5");
  });
});
