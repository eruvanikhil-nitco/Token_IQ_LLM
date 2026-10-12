/**
 * The period every page that shows money reads, named once.
 *
 * There were three copies of this and two of them were wrong. `defaultPeriod()` was pasted into the
 * Ledger, the Overview page and Recommendations; the Ledger's ran to the last day of the month and
 * the other two ran to today. So the headline total and the ledger total described different
 * periods, and a reader comparing them was comparing month to date against a whole month with
 * nothing on either screen saying so.
 *
 * The fix is not to pick one. Both are things a reader means: month to date is "what have we spent
 * so far" and the whole month is what a provider's bill covers, so reconciling a bill against part
 * of a month reports a difference the size of the days that have not happened yet. So both are
 * named, and a figure says which one it is for.
 *
 * Days are counted in UTC, because every figure this product stores is bucketed by UTC day. A
 * period that moved with the reader's clock would quietly include or exclude a day's spend.
 */

export const PERIOD_CHOICES = ["month-to-date", "this-month", "last-month", "last-30-days", "named-month"] as const;

export type PeriodChoice = (typeof PERIOD_CHOICES)[number];

export const DEFAULT_PERIOD: PeriodChoice = "month-to-date";
/** What a reader asks first: what have we spent. A whole month that has not happened reads as a drop. */

export interface Period {
  start: string;
  end: string;
}

const LABELS: Readonly<Record<PeriodChoice, string>> = {
  "month-to-date": "Month to date",
  "this-month": "This whole month",
  "last-month": "Last month",
  "last-30-days": "Last 30 days",
  "named-month": "A month I choose",
};

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

const MONTHS_OFFERED = 12;

export interface MonthOption {
  value: string;
  label: string;
}

/**
 * The months a reader can name, newest first.
 *
 * Needed because a month is closed long after it ends: a finance team reconciles September in
 * November. Without this the only way to reach a past month would be a page keeping its own date
 * inputs, which is the thing this replaces.
 */
export function monthOptions(now: Date = new Date(), count: number = MONTHS_OFFERED): readonly MonthOption[] {
  return Array.from({ length: count }, (_, back) => {
    const shifted = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - back, 1));
    const month = shifted.getUTCMonth();
    return {
      value: `${shifted.getUTCFullYear()}-${String(month + 1).padStart(2, "0")}`,
      label: `${MONTH_NAMES[month]} ${shifted.getUTCFullYear()}`,
    };
  });
}

/** The whole of one named month, as `YYYY-MM`. A month nobody can read falls back to this one. */
export function namedMonthPeriod(month: string | null, now: Date = new Date()): Period {
  const match = /^(\d{4})-(\d{2})$/.exec(month ?? "");
  if (!match || Number(match[2]) < 1 || Number(match[2]) > 12) {
    return periodFor("this-month", now);
  }
  const lastDay = new Date(Date.UTC(Number(match[1]), Number(match[2]), 0)).getUTCDate();
  return { start: `${match[1]}-${match[2]}-01`, end: `${match[1]}-${match[2]}-${String(lastDay).padStart(2, "0")}` };
}

/** What the period is called on screen, so two figures over two periods never look alike. */
export function periodLabel(choice: PeriodChoice): string {
  return LABELS[choice];
}

function day(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function firstOfMonth(now: Date): Date {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
}

function lastOfMonth(now: Date, monthsBack = 0): Date {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1 - monthsBack, 0));
}

/**
 * The two days a period runs between, inclusive at both ends.
 *
 * Inclusive because every endpoint here takes a first and last day and widens the last to the end
 * of that day: a period that excluded its own last day would drop a day of spend and blame the
 * provider for the difference.
 */
export function periodFor(choice: PeriodChoice, now: Date = new Date(), month: string | null = null): Period {
  switch (choice) {
    case "named-month":
      return namedMonthPeriod(month, now);
    case "month-to-date":
      return { start: day(firstOfMonth(now)), end: day(now) };
    case "this-month":
      return { start: day(firstOfMonth(now)), end: day(lastOfMonth(now)) };
    case "last-month": {
      const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1));
      return { start: day(first), end: day(lastOfMonth(now, 1)) };
    }
    case "last-30-days": {
      // Twenty-nine days back, so the window is thirty days including today. The same window the
      // data-quality checks and the Uploads tab use, so a reader moving between them sees the same
      // days rather than a window that is one longer here.
      const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 29));
      return { start: day(start), end: day(now) };
    }
  }
}

/**
 * Whether a period is a whole calendar month.
 *
 * Invoice Reconciliation needs to know. A provider's bill covers the month, so comparing it
 * against part of one reports a difference the size of the days that have not happened yet and
 * blames the provider for it. The screen says so rather than letting a reader read that difference
 * as a problem with the bill.
 */
export function isWholeMonth(period: Period): boolean {
  const from = /^(\d{4})-(\d{2})-(\d{2})$/.exec(period.start);
  const to = /^(\d{4})-(\d{2})-(\d{2})$/.exec(period.end);
  if (!from || !to) {
    return false;
  }
  if (from[1] !== to[1] || from[2] !== to[2] || from[3] !== "01") {
    return false;
  }
  const lastDay = new Date(Date.UTC(Number(to[1]), Number(to[2]), 0)).getUTCDate();
  return Number(to[3]) === lastDay;
}
