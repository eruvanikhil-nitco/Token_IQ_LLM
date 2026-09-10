import { describe, expect, it } from "vitest";
import {
  BACKEND_PARAM,
  buildPerSecondPatch,
  buildPricingPatch,
  isBlank,
  perMillion,
  readRate,
  readRates,
  validateRate,
  validateRates,
  type PricingField,
  type PricingValues,
  type WriteMode,
} from "./modelPricing";

const rates = (values: Partial<PricingValues> = {}): PricingValues => ({
  input: undefined,
  output: undefined,
  cacheRead: undefined,
  cacheWrite: undefined,
  ...values,
});

const create: WriteMode = { kind: "create" };
const update = (...touched: PricingField[]): WriteMode => ({ kind: "update", touched: new Set(touched) });

describe("reading stored rates", () => {
  it("scales a stored per-token rate to the per-million figure the UI shows", () => {
    // A real rate from the proxy: anthropic-haiku-4-5 input, which displays as $1.00 / 1M.
    expect(perMillion(0.000001)).toBe(1);
  });

  it("prefers the deployment's own override over the built-in price map", () => {
    const source = {
      litellm_params: { input_cost_per_token: 0.000002 },
      model_info: { input_cost_per_token: 0.00000015 },
    };

    expect(readRate(source, "input")).toBe(2);
  });

  it("falls back to the price map when the deployment sets no override", () => {
    // openrouter/openai/gpt-4o-mini on the live proxy: no override, $0.15 / 1M from the map.
    const source = { litellm_params: {}, model_info: { input_cost_per_token: 0.00000015 } };

    expect(readRate(source, "input")).toBeCloseTo(0.15, 10);
  });

  it("reports an unset rate as null rather than zero", () => {
    // Zero is a real rate, so it must never stand in for "not set".
    expect(readRate({ litellm_params: {}, model_info: {} }, "cacheWrite")).toBeNull();
  });

  it("keeps a stored zero rather than treating it as missing", () => {
    expect(readRate({ litellm_params: { output_cost_per_token: 0 } }, "output")).toBe(0);
  });

  it("reads every rate off one deployment", () => {
    const source = {
      litellm_params: {
        input_cost_per_token: 0.000003,
        output_cost_per_token: 0.000015,
        cache_read_input_token_cost: 0.0000003,
      },
    };

    const expected = { input: 3, output: 15, cacheRead: 0.3, cacheWrite: null };

    expect(readRates(source)).toEqual(expected);
  });

  it("ignores a non-numeric stored value instead of producing NaN", () => {
    expect(readRate({ litellm_params: { input_cost_per_token: "cheap" } }, "input")).toBeNull();
  });
});

describe("isBlank", () => {
  it.each([undefined, null, ""])("treats %o as no rate", (value) => {
    expect(isBlank(value)).toBe(true);
  });

  it.each([0, "0", 1.5])("treats %o as a real rate", (value) => {
    // Zero exempts a model from budget accounting, so it is a setting, not an absence.
    expect(isBlank(value)).toBe(false);
  });
});

describe("writing on create", () => {
  it("converts a typed per-million rate to the per-token value the backend stores", () => {
    expect(buildPricingPatch(rates({ input: "2", output: "10" }), create)).toMatchObject({
      input_cost_per_token: 0.000002,
      output_cost_per_token: 0.00001,
    });
  });

  it("omits a blank rate rather than sending a zero", () => {
    // Sending 0 would persist a free model; omitting leaves the price map in charge.
    expect(buildPricingPatch(rates({ input: "2" }), create)).not.toHaveProperty("output_cost_per_token");
  });

  it("sends a typed zero, which is how a model is exempted from budgets", () => {
    expect(buildPricingPatch(rates({ output: "0" }), create)).toEqual({ output_cost_per_token: 0 });
  });

  it("sends a numeric zero too, since the edit form holds rates as numbers not strings", () => {
    expect(buildPricingPatch(rates({ output: 0 }), create)).toEqual({ output_cost_per_token: 0 });
  });

  it("defaults a blank cache read to the input rate", () => {
    // The backend has no fallback for this key, so a blank would otherwise bill cached reads
    // at the price map's rate instead of the override just set.
    expect(buildPricingPatch(rates({ input: "3" }), create)).toEqual({
      input_cost_per_token: 0.000003,
      cache_read_input_token_cost: 0.000003,
    });
  });

  it("prefers an explicit cache read over the input rate", () => {
    expect(buildPricingPatch(rates({ input: "3", cacheRead: "0.3" }), create)).toMatchObject({
      cache_read_input_token_cost: 0.0000003,
    });
  });

  it("omits cache read when there is no input rate to fall back to", () => {
    expect(buildPricingPatch(rates({ output: "5" }), create)).not.toHaveProperty("cache_read_input_token_cost");
  });

  it("omits a blank cache write, leaving the backend's own fallback in charge", () => {
    expect(buildPricingPatch(rates({ input: "3" }), create)).not.toHaveProperty("cache_creation_input_token_cost");
  });

  it("never sends a null on create, because there is nothing stored to clear", () => {
    const patch = buildPricingPatch(rates(), create);

    expect(Object.values(patch)).not.toContain(null);
    expect(patch).toEqual({});
  });
});

describe("writing on update", () => {
  it("leaves an untouched rate out entirely, so a PATCH does not disturb it", () => {
    expect(buildPricingPatch(rates({ input: "2", output: "10" }), update("input"))).toEqual({
      input_cost_per_token: 0.000002,
      cache_read_input_token_cost: 0.000002,
    });
  });

  it("clears a rate the user emptied by sending an explicit null", () => {
    // Omitting it would mean "leave as is" under PATCH, and the old override would survive.
    expect(buildPricingPatch(rates({ input: "" }), update("input"))).toMatchObject({
      input_cost_per_token: null,
    });
  });

  it("clears cache write on demand rather than falling back", () => {
    expect(buildPricingPatch(rates({ cacheWrite: "" }), update("cacheWrite"))).toEqual({
      cache_creation_input_token_cost: null,
    });
  });

  it("clears cache read when the user emptied that field specifically", () => {
    expect(buildPricingPatch(rates({ input: "3", cacheRead: "" }), update("cacheRead"))).toMatchObject({
      cache_read_input_token_cost: null,
    });
  });

  it("re-derives cache read from input when only input changed", () => {
    expect(buildPricingPatch(rates({ input: "4" }), update("input"))).toMatchObject({
      cache_read_input_token_cost: 0.000004,
    });
  });

  it("does not touch cache read when input was cleared and cache read was not", () => {
    // There is no rate left to derive one from, so inventing a null here would clear an
    // override the user never asked to remove.
    expect(buildPricingPatch(rates({ input: "" }), update("input"))).not.toHaveProperty(
      "cache_read_input_token_cost",
    );
  });

  it("keeps an existing cache read when input changes but cache read holds a value", () => {
    const patch = buildPricingPatch(rates({ input: "4", cacheRead: "0.4" }), update("input"));

    // Its own value wins over the input fallback. Compared loosely because 0.4 has no exact
    // binary form, so dividing it by a million lands a hair off the literal.
    expect(patch.cache_read_input_token_cost).toBeCloseTo(0.0000004, 12);
  });

  it("sends nothing at all when nothing was touched", () => {
    expect(buildPricingPatch(rates({ input: "2", output: "10", cacheRead: "1" }), update())).toEqual({});
  });
});

describe("per-second pricing", () => {
  it("stores the rate exactly as typed, with no per-million scaling", () => {
    expect(buildPerSecondPatch("0.002")).toEqual({ input_cost_per_second: 0.002 });
  });

  it("sends nothing when left blank", () => {
    expect(buildPerSecondPatch("")).toEqual({});
  });
});

describe("validation", () => {
  it("accepts a blank rate", () => {
    expect(validateRate("", undefined)).toBeNull();
  });

  it("rejects something that is not a number", () => {
    expect(validateRate("two dollars", undefined)).toBe("not-a-number");
  });

  it("rejects a negative rate", () => {
    expect(validateRate("-1", undefined)).toBe("negative");
  });

  it("accepts zero", () => {
    expect(validateRate("0", undefined)).toBeNull();
  });

  it("rejects a usage rate on a PTU deployment, which already paid for throughput", () => {
    // Charging per token on top of reserved capacity counts the same spend twice.
    expect(validateRate("3", "15")).toBe("ptu-conflict");
  });

  it("allows a zero usage rate on a PTU deployment", () => {
    expect(validateRate("0", "15")).toBeNull();
  });

  it("allows a usage rate when there is no PTU count", () => {
    expect(validateRate("3", "")).toBeNull();
  });

  it("reports every failing rate at once, so a form can mark them together", () => {
    expect(validateRates(rates({ input: "nope", output: "-2", cacheRead: "1" }), undefined)).toEqual({
      input: "not-a-number",
      output: "negative",
    });
  });
});

describe("the name mapping", () => {
  it("names every field, since a missing one would silently drop a rate", () => {
    expect(Object.keys(BACKEND_PARAM).sort()).toEqual(["cacheRead", "cacheWrite", "input", "output"]);
  });
});
