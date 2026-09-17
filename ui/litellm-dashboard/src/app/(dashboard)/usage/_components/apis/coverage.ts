import type { ProviderRawFact } from "@/components/networking";

// Fields the wire contract allows to be null on a per-row basis. bucket_start, grain,
// evidence, credential_name, billed_cost, billing_currency and fetched_at are required by
// the backend on every row, so they carry no coverage signal and stay out of this list.
const NULLABLE_FIELDS: ReadonlyArray<{ field: keyof ProviderRawFact; label: string }> = [
  { field: "model", label: "Model" },
  { field: "provider_request_id", label: "Provider request ID" },
  { field: "provider_api_key_id", label: "API key" },
  { field: "cached_input_tokens", label: "Cached input tokens" },
  { field: "cache_write_tokens", label: "Cache write tokens" },
];

export const fieldsNotReported = (rows: readonly ProviderRawFact[]): readonly string[] => {
  if (rows.length === 0) {
    return [];
  }
  return NULLABLE_FIELDS.filter(({ field }) => rows.every((row) => row[field] === null)).map(({ label }) => label);
};
