import type { AdjustmentKind, ReconciliationOutcome } from "@/components/networking";
import { formatExactMoney } from "@/lib/money";

/**
 * A ledger line is shown to the digit, because this screen exists to reconcile against a bill
 * and independently rounded lines stop adding up. Headline tiles use `formatMoney` instead.
 */
export const formatAmount = formatExactMoney;

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
