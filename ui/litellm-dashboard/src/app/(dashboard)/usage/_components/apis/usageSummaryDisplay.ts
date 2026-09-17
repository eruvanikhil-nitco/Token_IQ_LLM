import type { ProviderTokenTotals, ProviderUsageSummaryResponse } from "@/components/networking";

export const hasUsage = (summary: ProviderUsageSummaryResponse): boolean => summary.facts > 0;

export interface TokenRow {
  label: string;
  value: number;
}

export const tokenRows = (tokens: ProviderTokenTotals): TokenRow[] => [
  { label: "Input tokens", value: tokens.input_tokens },
  { label: "Output tokens", value: tokens.output_tokens },
  { label: "Cached input tokens", value: tokens.cached_input_tokens },
  { label: "Cache write tokens", value: tokens.cache_write_tokens },
];

export interface EvidenceRow {
  level: string;
  label: string;
  description: string;
  cost: string;
}

const EVIDENCE_LEVELS: ReadonlyArray<{ level: string; label: string; description: string }> = [
  { level: "reconciled", label: "Reconciled", description: "The provider asserted these dollars directly" },
  { level: "priced", label: "Priced", description: "The provider asserted tokens; we applied rates" },
  { level: "allocated", label: "Allocated", description: "Only our own gateway events exist here" },
];

// by_evidence arrives as a plain string-keyed map, not a typed union: look each level up
// defensively and fall back to "0" so a level the backend has not started sending yet still
// renders as an explicit zero rather than disappearing from the row.
export const evidenceRows = (byEvidence: Record<string, string>): EvidenceRow[] =>
  EVIDENCE_LEVELS.map(({ level, label, description }) => ({
    level,
    label,
    description,
    cost: level in byEvidence ? byEvidence[level] : "0",
  }));
