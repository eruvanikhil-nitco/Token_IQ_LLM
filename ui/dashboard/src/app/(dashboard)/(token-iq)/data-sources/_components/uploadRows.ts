/**
 * What Data Sources > Uploads shows, worked out away from the rendering.
 *
 * The rows that matter are the bills nobody entered. They are invisible everywhere else:
 * reconciliation for that month reports no bill rather than a difference, and the Overview tab's
 * coverage figure says how many are missing without saying which. So a missing bill is a row with
 * a reason rather than a gap in a list of the work already done.
 *
 * A missing row carries no total, and not a zero. There is no bill, so the only figure available
 * would be one Token IQ worked out itself, and a figure it worked out sitting in an invoice column
 * is how a provider total and an attribution total get added together by accident.
 */

import type { InvoiceForwarding, UploadRow } from "@/components/networking";

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

interface Day {
  year: number;
  month: number;
  day: number;
}

/**
 * A YYYY-MM-DD as its three numbers.
 *
 * Read by hand rather than through `new Date`, which parses a bare date as UTC midnight and then
 * renders it as the day before for any reader west of Greenwich. A billing period is a set of
 * calendar days on a bill, not an instant, so it has no timezone to be shifted into.
 */
function dayParts(value: string): Day | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) {
    return null;
  }
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

function lastDayOfMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

export function dayLabel(value: string): string {
  const parts = dayParts(value);
  if (parts === null) {
    return value;
  }
  return `${parts.day} ${MONTH_NAMES[parts.month - 1].slice(0, 3)} ${parts.year}`;
}

/**
 * The period a bill covers, as a reader would say it.
 *
 * A whole calendar month is named, because that is what a provider bills and what somebody is
 * looking for when they ask whether September is in. Anything else is given as its two days
 * rather than rounded to the month it mostly falls in.
 */
export function periodLabel(start: string, end: string): string {
  const from = dayParts(start);
  const to = dayParts(end);
  if (from === null || to === null) {
    return `${start} to ${end}`;
  }
  const sameMonth = from.year === to.year && from.month === to.month;
  const spansIt = from.day === 1 && to.day === lastDayOfMonth(to.year, to.month);
  if (sameMonth && spansIt) {
    return `${MONTH_NAMES[from.month - 1]} ${from.year}`;
  }
  return `${dayLabel(start)} to ${dayLabel(end)}`;
}

export interface UploadRowView {
  id: string;
  provider: string;
  period: string;
  /** Null when no bill exists, which is a dash on the screen rather than a figure. */
  total: string | null;
  note: string | null;
  status: "recorded" | "missing";
  statusLabel: string;
  /** What to do about it, for a row that needs doing something about. */
  detail: string | null;
}

export function uploadRowView(row: UploadRow, checkedFrom: string): UploadRowView {
  if (row.kind === "not_entered") {
    return {
      id: `missing:${row.provider}`,
      provider: row.display_name,
      // The window that was checked, not a period of its own. There is no bill, so there is no
      // period it covers, and a month named here would be one nobody has seen a bill for.
      period: `Billing since ${dayLabel(checkedFrom)}`,
      total: null,
      note: null,
      status: "missing",
      statusLabel: "No bill entered",
      detail: "Nothing has been entered to check that billing against",
    };
  }
  return {
    id: row.invoice_id,
    provider: row.display_name,
    period: periodLabel(row.period_start, row.period_end),
    total: `${row.total} ${row.currency}`,
    note: row.note,
    status: "recorded",
    statusLabel: "Recorded",
    detail: null,
  };
}

export function uploadRowViews(rows: readonly UploadRow[], checkedFrom: string): readonly UploadRowView[] {
  return rows.map((row) => uploadRowView(row, checkedFrom));
}

export function billsMissing(rows: readonly UploadRow[]): number {
  return rows.filter((row) => row.kind === "not_entered").length;
}

export interface ForwardingMessage {
  tone: "configured" | "unset" | "unusable";
  text: string;
  /** The address itself, so it can be shown as something to copy rather than buried in a sentence. */
  address: string | null;
}

/**
 * What the tab says about forwarding a bill by email.
 *
 * Three states, because an address that cannot receive mail is not the same as no address. Shown
 * as though it worked, a typo sends a finance team's invoices nowhere and nothing says so until a
 * month-end close has nothing to reconcile against.
 *
 * Even a working address is said plainly to be a mailbox a person reads: nothing here opens mail
 * or parses an attachment, and an address presented as automatic would have a customer forwarding
 * bills for a month and wondering why none of them arrived.
 */
export function forwardingMessage(forwarding: InvoiceForwarding): ForwardingMessage {
  if (forwarding.kind === "configured") {
    return {
      tone: "configured",
      text: "Bills may be forwarded here. Nothing reads this mailbox automatically yet, so an administrator still enters the figures below.",
      address: forwarding.address,
    };
  }
  if (forwarding.kind === "unusable") {
    return {
      tone: "unusable",
      text: `${forwarding.setting} is set to something that cannot receive mail, so anything forwarded to it is lost. ${forwarding.problem}`,
      address: forwarding.value,
    };
  }
  return {
    tone: "unset",
    text: `No forwarding address is configured, so every bill is entered here by hand. Whoever deployed this installation can set ${forwarding.setting} to a mailbox your finance team may forward bills to.`,
    address: null,
  };
}
