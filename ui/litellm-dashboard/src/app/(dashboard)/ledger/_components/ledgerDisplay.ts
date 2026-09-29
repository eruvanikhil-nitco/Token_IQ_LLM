import type { AdjustmentKind, ReconciliationOutcome } from "@/components/networking";

const SYMBOLS: Record<string, string> = { USD: "$", EUR: "€", GBP: "£" };

/**
 * Money arrives as exact digit strings and is never parsed to a number here.
 *
 * A currency with no symbol is named rather than dropped: showing "10" for ten Swedish krona
 * beside "$10" would read as the same amount.
 */
export const formatAmount = (amount: string | null, currency: string | null): string => {
  if (amount === null) return "—";
  const trimmed = amount.trim();
  if (trimmed === "") return "—";
  const symbol = currency === null ? "" : SYMBOLS[currency];
  return symbol === undefined ? `${currency} ${trimmed}` : `${symbol}${trimmed}`;
};

/** What each evidence level claims about how a figure was arrived at. */
export const EVIDENCE_LABEL: Record<string, string> = {
  reconciled: "The provider asserted this amount",
  priced: "The provider gave tokens and we applied rates",
  allocated: "Only our own gateway records cover this",
};

export const OUTCOME_LABEL: Record<ReconciliationOutcome, string> = {
  balanced: "Balanced",
  unexplained_difference: "Difference not fully explained",
  currency_mismatch: "Different currencies",
  no_invoice: "No bill entered",
};

export const ADJUSTMENT_LABEL: Record<AdjustmentKind, string> = {
  credit: "Credit",
  discount: "Discount",
  tax: "Tax",
  commitment: "Commitment",
};

/** A remainder of any size, either direction, is worth a reader's attention. Zero is not. */
export const hasRemainder = (unexplained: string): boolean => unexplained.trim() !== "" && Number(unexplained) !== 0;

/** Whether the bill was larger than the ledger, which reads differently from being smaller. */
export const remainderDirection = (unexplained: string): "over" | "under" | "none" => {
  const value = Number(unexplained);
  if (value === 0 || Number.isNaN(value)) return "none";
  return value > 0 ? "over" : "under";
};
