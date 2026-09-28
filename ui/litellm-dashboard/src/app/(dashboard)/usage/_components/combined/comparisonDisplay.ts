import type { ComparisonDay, ComparisonStatus } from "@/components/networking";

/**
 * What each status means to the person reading the screen.
 *
 * These are claims, not labels. "Matched" says the two sources agree, so it must never appear
 * for a day the provider has not reported: that is why "no_provider_data" is separate.
 */
export const STATUS_LABEL: Record<ComparisonStatus, string> = {
  matched: "Matched",
  gap: "Gap",
  not_settled: "Not settled yet",
  no_provider_data: "Provider reported nothing",
};

export const STATUS_EXPLANATION: Record<ComparisonStatus, string> = {
  matched: "The gateway recorded at least what the provider billed.",
  gap: "The provider charged more than the gateway recorded. That spend bypassed the gateway.",
  not_settled: "The provider has not finished billing this day, so no comparison is made yet.",
  no_provider_data: "The provider has reported nothing for this day, so there is nothing to compare.",
};

/** Money arrives as exact digit strings. Format for reading without ever parsing to a number. */
export const formatAmount = (amount: string | null): string => {
  if (amount === null) return "—";
  const trimmed = amount.trim();
  return trimmed === "" ? "—" : `$${trimmed}`;
};

export const ownerOf = (row: ComparisonDay): string =>
  row.owner_id === null ? "—" : `${row.owner_type}: ${row.owner_id}`;

/** Only a real difference nobody has claimed needs an admin's attention. */
export const needsAttention = (row: ComparisonDay): boolean => row.status === "gap" && row.owner_id === null;
