/**
 * What leaves the enter-a-bill dialog, and what it makes of the answer.
 *
 * A bill is the only thing reconciliation compares the ledger against, so every figure here is
 * typed exactly as a person read it off the bill and crosses as a string. Parsed into a number it
 * would be rounded somewhere, and a rounded bill manufactures a discrepancy that does not exist.
 *
 * The period is a whole calendar month because that is what every provider here bills, and because
 * the stored period is matched exactly when a month is reconciled: a period a person assembled from
 * two loose dates is a bill that silently fails to cover the last day of its own month.
 */

import { migratedHref } from "@/utils/migratedPages";
import type { InvoiceDraft } from "@/app/(dashboard)/hooks/ledger/useInvoices";
import type { AdjustmentKind, Invoice, InvoiceProviderOption } from "@/components/networking";

export const INVOICE_CURRENCIES = ["USD", "EUR", "GBP", "INR"] as const;

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

export interface MonthOption {
  /** YYYY-MM, which is what the draft holds. */
  value: string;
  label: string;
}

const MONTHS_OFFERED = 12;

function monthValue(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

/**
 * The months a bill may be entered for, newest first.
 *
 * The current month is offered because a provider can bill mid-month, and a year of history
 * because that is roughly as far back as a provider's own console goes.
 */
export function monthOptions(today: Date): readonly MonthOption[] {
  const year = today.getUTCFullYear();
  const month = today.getUTCMonth() + 1;
  return Array.from({ length: MONTHS_OFFERED }, (_, back) => {
    const shifted = new Date(Date.UTC(year, month - 1 - back, 1));
    const shiftedYear = shifted.getUTCFullYear();
    const shiftedMonth = shifted.getUTCMonth() + 1;
    return {
      value: monthValue(shiftedYear, shiftedMonth),
      label: `${MONTH_NAMES[shiftedMonth - 1]} ${shiftedYear}`,
    };
  });
}

/**
 * The month the dialog opens on: the one just finished.
 *
 * A bill for the month in progress does not exist yet, so opening on it would have somebody
 * correct the field every time before they could use the dialog.
 */
export function defaultMonth(today: Date): string {
  return monthOptions(today)[1].value;
}

export interface Period {
  period_start: string;
  period_end: string;
}

/** The first and last day of a month, as the dates the save takes. */
export function periodForMonth(month: string): Period | null {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const index = Number(match[2]);
  if (index < 1 || index > 12) {
    return null;
  }
  const lastDay = new Date(Date.UTC(year, index, 0)).getUTCDate();
  return {
    period_start: `${match[1]}-${match[2]}-01`,
    period_end: `${match[1]}-${match[2]}-${String(lastDay).padStart(2, "0")}`,
  };
}

export interface AdjustmentSpec {
  kind: AdjustmentKind;
  label: string;
  explanation: string;
  /** Whether this kind normally makes the bill larger than the usage behind it. */
  addsToTheBill: boolean;
}

/**
 * The four reasons a bill legitimately differs from what usage says it should be.
 *
 * The sign is the part worth explaining. An adjustment is subtracted from the bill before the
 * comparison, so something charged on top of usage is positive and money taken off the bill is
 * negative. Entered the wrong way round it does not fail: it moves the unexplained remainder by
 * twice the amount and blames the provider for it.
 */
export const ADJUSTMENT_KINDS: readonly AdjustmentSpec[] = [
  {
    kind: "commitment",
    label: "Commitment",
    explanation: "Prepaid or reserved capacity charged instead of per request. Charged on top of usage, so positive.",
    addsToTheBill: true,
  },
  {
    kind: "tax",
    label: "Tax",
    explanation: "Tax added on top of usage. Positive.",
    addsToTheBill: true,
  },
  {
    kind: "credit",
    label: "Credit",
    explanation: "Money the provider gave back, which makes the bill smaller than usage. Normally negative.",
    addsToTheBill: false,
  },
  {
    kind: "discount",
    label: "Discount",
    explanation: "An agreed reduction on list price. Normally negative.",
    addsToTheBill: false,
  },
];

export interface AdjustmentDraft {
  kind: AdjustmentKind;
  amount: string;
  note: string;
}

export interface InvoiceFormDraft {
  provider: string;
  month: string;
  currency: string;
  total: string;
  note: string;
  adjustments: readonly AdjustmentDraft[];
}

const AMOUNT_PATTERN = /^-?\d+(\.\d+)?$/;

/**
 * Whether this is an amount the save can store.
 *
 * Caught here because the alternative is a 400 that says the value is not an amount, which is
 * true and says nothing about the dollar sign that caused it. Empty is nobody's mistake yet, so
 * required-ness is reported separately.
 */
export function amountProblem(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed === "") {
    return null;
  }
  if (!AMOUNT_PATTERN.test(trimmed)) {
    return "Enter the figure in digits, with no currency symbol and no thousands separators, for example 48210.07";
  }
  return null;
}

/** A sign that contradicts the kind, said as a note rather than refused. A reversed credit is real. */
export function signHint(kind: AdjustmentKind, amount: string): string | null {
  const trimmed = amount.trim();
  if (amountProblem(trimmed) !== null || trimmed === "") {
    return null;
  }
  const spec = ADJUSTMENT_KINDS.find((candidate) => candidate.kind === kind);
  if (spec === undefined) {
    return null;
  }
  const negative = trimmed.startsWith("-");
  if (spec.addsToTheBill && negative) {
    return `A ${spec.label.toLowerCase()} is normally charged on top of usage, so this is usually positive`;
  }
  if (!spec.addsToTheBill && !negative && Number(trimmed) !== 0) {
    return `A ${spec.label.toLowerCase()} normally comes off the bill, so this is usually negative`;
  }
  return null;
}

/** The adjustments worth sending: a row nobody filled in is not an adjustment of zero. */
function adjustmentsOf(draft: InvoiceFormDraft): InvoiceDraft["adjustments"] {
  return draft.adjustments
    .filter((adjustment) => adjustment.amount.trim() !== "")
    .map((adjustment) => ({
      kind: adjustment.kind,
      amount: adjustment.amount.trim(),
      note: adjustment.note.trim() === "" ? null : adjustment.note.trim(),
    }));
}

export function invoicePayload(draft: InvoiceFormDraft): InvoiceDraft | null {
  const period = periodForMonth(draft.month);
  if (period === null) {
    return null;
  }
  return {
    provider: draft.provider,
    period_start: period.period_start,
    period_end: period.period_end,
    currency: draft.currency,
    total: draft.total.trim(),
    adjustments: adjustmentsOf(draft),
    note: draft.note.trim() === "" ? null : draft.note.trim(),
  };
}

export function canSaveInvoice(draft: InvoiceFormDraft): boolean {
  if (draft.provider === "" || periodForMonth(draft.month) === null) {
    return false;
  }
  if (draft.total.trim() === "" || amountProblem(draft.total) !== null) {
    return false;
  }
  return draft.adjustments.every((adjustment) => amountProblem(adjustment.amount) === null);
}

/**
 * What to tell somebody who just entered a bill.
 *
 * It names the period the bill was stored against, because entering the wrong month is the
 * mistake this dialog makes easiest and the one nothing downstream can detect: reconciliation
 * compares a real bill against a month of usage that has nothing to do with it.
 */
export function invoiceSavedMessage(invoice: Invoice, providerName: string): string {
  return `${providerName} is recorded for ${invoice.period_start} to ${invoice.period_end} at ${invoice.total} ${invoice.currency}. Reconciliation compares it against that period's usage.`;
}

/**
 * The month a period belongs to, or null when it is not a date.
 *
 * For a link from a screen that already knows which month it is looking at, so the dialog opens on
 * that month rather than on its own default. A period that spans two months names the first, which
 * is the month a provider's bill is for.
 */
export function monthOfPeriod(periodStart: string): string | null {
  const match = /^(\d{4})-(\d{2})/.exec(periodStart);
  if (!match) {
    return null;
  }
  return periodForMonth(`${match[1]}-${match[2]}`) === null ? null : `${match[1]}-${match[2]}`;
}

export interface EnterBillLink {
  provider?: string | null;
  month?: string | null;
}

export const ENTER_BILL_PARAM = "enter";

/**
 * A link that opens the enter-a-bill dialog, with what the linking screen already knows.
 *
 * The reconciliation screen's dead end is the reason this exists: its outcome for a month nobody
 * has entered is "No bill entered", and naming a place for the reader to go and find is worse than
 * taking them there with the provider and the month already filled in.
 */
export function enterBillHref({ provider, month }: EnterBillLink = {}): string {
  const params = new URLSearchParams([[ENTER_BILL_PARAM, "1"]]);
  if (provider) {
    params.set("provider", provider);
  }
  if (month) {
    params.set("month", month);
  }
  return `${migratedHref("data-sources/uploads")}/?${params.toString()}`;
}

/**
 * The provider a link asked for, if the save would accept it.
 *
 * A value from a URL is a value somebody could have typed, so it is checked against the providers
 * the server offered rather than trusted. An unknown one falls back to the first, because a dialog
 * opening on nothing is worse than one opening on the wrong provider, which is visible and one
 * click from right.
 */
export function prefilledProvider(param: string | null, providers: readonly InvoiceProviderOption[]): string {
  const found = providers.find((option) => option.provider === param);
  return found?.provider ?? providers[0]?.provider ?? "";
}

/** The month a link asked for, if it is one this dialog offers. */
export function prefilledMonth(param: string | null, today: Date): string {
  const offered = monthOptions(today).some((option) => option.value === param);
  return offered && param !== null ? param : defaultMonth(today);
}
