import { describe, expect, it } from "vitest";
import type { ProviderRawFact } from "@/components/networking";
import { fieldsNotReported } from "./coverage";

const row = (overrides: Partial<ProviderRawFact> = {}): ProviderRawFact => ({
  bucket_start: "2026-09-16T12:40:50.477000+00:00",
  grain: "request",
  evidence: "reconciled",
  credential_name: "openrouter-billing",
  model: "openai/gpt-4o-mini",
  provider_request_id: "gen-1789562236-kKqVw1BljrOCreiAVfES",
  provider_api_key_id: null,
  billed_cost: "0.00001365",
  billing_currency: "USD",
  input_tokens: 55,
  output_tokens: 9,
  cached_input_tokens: null,
  cache_write_tokens: null,
  raw: null,
  fetched_at: "2026-09-16T12:40:51.847000+00:00",
  ...overrides,
});

describe("fieldsNotReported", () => {
  it("names a field no row in the window populated", () => {
    expect(fieldsNotReported([row({ provider_api_key_id: null })])).toContain("API key");
  });

  it("does not name a field some row did populate", () => {
    expect(
      fieldsNotReported([row({ provider_api_key_id: null }), row({ provider_api_key_id: "k" })]),
    ).not.toContain("API key");
  });

  it("says nothing at all for an empty window rather than claiming everything is missing", () => {
    // An empty window means we have no evidence either way. Listing every field as
    // unreported would tell a customer their provider is broken when nothing has synced.
    expect(fieldsNotReported([])).toEqual([]);
  });

  it("names every field left null across the whole window, not just the first one checked", () => {
    const allFieldsUnreported = {
      model: null,
      provider_request_id: null,
      cached_input_tokens: null,
      cache_write_tokens: null,
    };
    const rows = [row(allFieldsUnreported), row(allFieldsUnreported)];

    expect(fieldsNotReported(rows)).toEqual([
      "Model",
      "Provider request ID",
      "API key",
      "Cached input tokens",
      "Cache write tokens",
    ]);
  });

  it("reports no missing fields once every field has been populated by some row", () => {
    const rows = [
      row({ provider_api_key_id: "key-1", cached_input_tokens: 10, cache_write_tokens: 5 }),
      row({ provider_api_key_id: null, cached_input_tokens: null, cache_write_tokens: null }),
    ];

    expect(fieldsNotReported(rows)).toEqual([]);
  });
});
