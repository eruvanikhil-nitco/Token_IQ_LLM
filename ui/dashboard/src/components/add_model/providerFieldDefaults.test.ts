import { describe, expect, it } from "vitest";

import { defaultsToSeed } from "./providerFieldDefaults";

describe("defaultsToSeed", () => {
  it("seeds a declared default the form has no value for", () => {
    expect(defaultsToSeed([{ key: "api_base", defaultValue: "https://api.openai.com/v1" }], {})).toEqual([
      ["api_base", "https://api.openai.com/v1"],
    ]);
  });

  it("leaves a field the admin already typed into alone", () => {
    // Overwriting a typed value would silently replace a customer's private endpoint with
    // the public one, and the form would look like it accepted what they typed.
    expect(
      defaultsToSeed([{ key: "api_base", defaultValue: "https://api.openai.com/v1" }], {
        api_base: "https://internal.example/v1",
      }),
    ).toEqual([]);
  });

  it("seeds a field the admin cleared back to empty", () => {
    expect(defaultsToSeed([{ key: "api_base", defaultValue: "https://api.openai.com/v1" }], { api_base: "" })).toEqual([
      ["api_base", "https://api.openai.com/v1"],
    ]);
  });

  it("ignores a field that declares no default", () => {
    expect(defaultsToSeed([{ key: "api_key" }], {})).toEqual([]);
  });

  it("returns every field that needs seeding, not only the first", () => {
    expect(
      defaultsToSeed(
        [
          { key: "api_base", defaultValue: "https://api.openai.com/v1" },
          { key: "api_version", defaultValue: "2024-02-01" },
        ],
        {},
      ),
    ).toEqual([
      ["api_base", "https://api.openai.com/v1"],
      ["api_version", "2024-02-01"],
    ]);
  });
});
