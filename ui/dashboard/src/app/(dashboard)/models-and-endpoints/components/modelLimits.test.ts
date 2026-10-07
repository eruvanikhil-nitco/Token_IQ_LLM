import { describe, expect, it } from "vitest";
import {
  buildPatch,
  describe as describeLimits,
  hasErrors,
  isDirty,
  isEditable,
  limitsOf,
  modelId,
  validate,
  type ModelRow,
} from "./modelLimits";

const model = (overrides: Partial<ModelRow> = {}): ModelRow => ({
  model_name: "openrouter/openai/gpt-4o-mini",
  model_info: { id: "m1", db_model: true },
  litellm_params: { model: "openrouter/openai/gpt-4o-mini", tpm: 100000, rpm: 60 },
  ...overrides,
});

describe("limitsOf", () => {
  it("reads the stored limits as strings for the inputs", () => {
    expect(limitsOf(model())).toEqual({ tpm: "100000", rpm: "60", timeout: "" });
  });

  it("treats an unset limit as blank rather than showing null", () => {
    expect(limitsOf(model({ litellm_params: {} }))).toEqual({ tpm: "", rpm: "", timeout: "" });
  });

  it("survives a deployment with no params at all", () => {
    expect(limitsOf(model({ litellm_params: null }))).toEqual({ tpm: "", rpm: "", timeout: "" });
  });

  it("keeps a zero rather than reading it as unset", () => {
    // 0 is falsy but meaningful; blanking it would silently discard what someone stored.
    expect(limitsOf(model({ litellm_params: { rpm: 0 } })).rpm).toBe("0");
  });
});

describe("isEditable", () => {
  it("allows a model stored in the database", () => {
    expect(isEditable(model())).toBe(true);
  });

  it("refuses a config file model, which the API cannot patch", () => {
    // Offering an input here would promise a save that cannot happen.
    expect(isEditable(model({ model_info: { id: "m2", db_model: false } }))).toBe(false);
    expect(isEditable(model({ model_info: null }))).toBe(false);
  });
});

describe("validate", () => {
  it("accepts a blank field, which means no limit", () => {
    expect(validate("rpm", "").ok).toBe(true);
    expect(validate("rpm", "   ").ok).toBe(true);
  });

  it("accepts a sensible number", () => {
    expect(validate("rpm", "60").ok).toBe(true);
    expect(validate("tpm", "100000").ok).toBe(true);
  });

  it("rejects text", () => {
    expect(validate("rpm", "sixty")).toEqual({ ok: false, error: "Must be a number" });
  });

  it("rejects zero and negatives, which would mean a limit nobody can satisfy", () => {
    expect(validate("rpm", "0").ok).toBe(false);
    expect(validate("rpm", "-5").ok).toBe(false);
  });

  it("requires whole numbers for request and token counts", () => {
    expect(validate("rpm", "1.5")).toEqual({ ok: false, error: "Must be a whole number" });
    expect(validate("tpm", "1.5").ok).toBe(false);
  });

  it("allows a fractional timeout, which is measured in seconds", () => {
    expect(validate("timeout", "2.5").ok).toBe(true);
  });
});

describe("hasErrors", () => {
  it("is false when everything is blank or valid", () => {
    expect(hasErrors({ tpm: "", rpm: "60", timeout: "2.5" })).toBe(false);
  });

  it("is true when any field is wrong", () => {
    expect(hasErrors({ tpm: "abc", rpm: "60", timeout: "" })).toBe(true);
  });
});

describe("isDirty", () => {
  it("is false when nothing moved", () => {
    expect(isDirty({ tpm: "1", rpm: "2", timeout: "" }, { tpm: "1", rpm: "2", timeout: "" })).toBe(false);
  });

  it("ignores whitespace, so a stray space is not a change", () => {
    expect(isDirty({ tpm: " 1 ", rpm: "2", timeout: "" }, { tpm: "1", rpm: "2", timeout: "" })).toBe(false);
  });

  it("notices a cleared field, which is a real change", () => {
    expect(isDirty({ tpm: "", rpm: "2", timeout: "" }, { tpm: "1", rpm: "2", timeout: "" })).toBe(true);
  });
});

describe("buildPatch", () => {
  it("sends numbers, not the strings the inputs hold", () => {
    expect(buildPatch({ tpm: "100000", rpm: "60", timeout: "2.5" })).toEqual({
      litellm_params: { tpm: 100000, rpm: 60, timeout: 2.5 },
    });
  });

  it("sends a cleared field as null rather than omitting it", () => {
    // Under PATCH semantics an omitted field means "leave as is", so omitting a cleared
    // limit would silently keep the old value while the UI showed it gone.
    expect(buildPatch({ tpm: "", rpm: "60", timeout: "" })).toEqual({
      litellm_params: { tpm: null, rpm: 60, timeout: null },
    });
  });
});

describe("describe", () => {
  it("says so when a model has no limits", () => {
    expect(describeLimits({ tpm: "", rpm: "", timeout: "" })).toBe("no limits set");
  });

  it("lists only the limits that are set", () => {
    expect(describeLimits({ tpm: "", rpm: "60", timeout: "2.5" })).toBe("rpm 60, timeout 2.5");
  });
});

describe("modelId", () => {
  it("reads the id the patch endpoint needs", () => {
    expect(modelId(model())).toBe("m1");
  });

  it("is empty when there is none, rather than undefined in a URL", () => {
    expect(modelId(model({ model_info: null }))).toBe("");
  });
});
