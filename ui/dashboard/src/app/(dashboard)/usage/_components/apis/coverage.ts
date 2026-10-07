import type { ProviderRawFact } from "@/components/networking";

// Fields the wire contract allows to be null on a per-row basis. bucket_start, grain,
// evidence, credential_name, billed_cost, billing_currency and fetched_at are required by
// the backend on every row, so they carry no coverage signal and stay out of this list.
const NULLABLE_FIELDS: ReadonlyArray<{ field: keyof ProviderRawFact; label: string }> = [
  { field: "model", label: "Model" },
  { field: "provider_request_id", label: "Provider request ID" },
  { field: "provider_api_key_id", label: "Provider's own key ID" },
  { field: "cached_input_tokens", label: "Cached input tokens" },
  { field: "cache_write_tokens", label: "Cache write tokens" },
];

export const fieldsNotReported = (rows: readonly ProviderRawFact[]): readonly string[] => {
  if (rows.length === 0) {
    return [];
  }
  return NULLABLE_FIELDS.filter(({ field }) => rows.every((row) => row[field] === null)).map(({ label }) => label);
};

export const joinWithAnd = (items: readonly string[]): string => {
  if (items.length <= 1) {
    return items[0] ?? "";
  }
  if (items.length === 2) {
    return `${items[0]} and ${items[1]}`;
  }
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
};
