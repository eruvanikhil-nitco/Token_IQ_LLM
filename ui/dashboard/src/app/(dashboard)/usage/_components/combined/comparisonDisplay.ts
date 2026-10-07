import type { ComparisonDay, ComparisonStatus } from "@/components/networking";
import { formatExactMoney, formatMoney } from "@/lib/money";

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

/**
 * A comparison row is shown to the digit: provider billed, gateway recorded and the difference
 * between them have to agree on screen, and independently rounded figures do not.
 */
export const formatAmount = (amount: string | null): string => formatExactMoney(amount, "USD");

/** A headline figure nothing is subtracted from, rounded for reading. */
export const formatTotal = (amount: string | null): string => formatMoney(amount, "USD");

export const ownerOf = (row: ComparisonDay): string =>
  row.owner_id === null ? "—" : `${row.owner_type}: ${row.owner_id}`;

/** Only a real difference nobody has claimed needs an admin's attention. */
export const needsAttention = (row: ComparisonDay): boolean => row.status === "gap" && row.owner_id === null;
