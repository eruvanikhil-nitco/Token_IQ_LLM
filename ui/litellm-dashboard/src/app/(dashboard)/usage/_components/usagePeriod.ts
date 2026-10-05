import type { DateRangePickerValue } from "@/components/shared/date_picker_types";

/**
 * The period the Usage page is looking at, and what each view can honestly do with it.
 *
 * The page used to hold two periods. Combined had a 7/30/90 dropdown defaulting to 30 days, Gateway
 * had its own picker defaulting to 7, and both panels stayed mounted, so switching tab changed the
 * window with nothing on screen saying so. Opening on Combined and moving to Gateway took you from
 * thirty days to seven.
 *
 * One period now, chosen once. The two views still cannot read the same windows: Gateway takes a
 * start and an end, while the combined endpoints take a number of days bounded to 90 and always
 * mean "the last N days from now". So a view that cannot serve the chosen period says what it did
 * instead, rather than showing a different window that looks like the one that was asked for.
 */

/** `days` on /usage/combined/* is `ge=1, le=90`, so a longer period cannot be requested. */
export const COMBINED_MAX_DAYS = 90;

/** What the Combined views fall back to when the period gives them nothing to work from. */
export const DEFAULT_DAYS = 30;

const MS_PER_DAY = 24 * 60 * 60 * 1000;

const startOfDay = (date: Date): number => {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy.getTime();
};

/**
 * Whole days from the start of `from` to the start of `to`, counting the first day.
 *
 * One day rather than zero for a single-day period, because asking for today and being given
 * nothing reads as a broken screen. Reversed ends also give one day: it is a picker that should not
 * produce them, and guessing which way round the reader meant would be worse than the narrow answer.
 */
export const daysSpanned = (period: DateRangePickerValue): number => {
  if (!period.from || !period.to) return DEFAULT_DAYS;
  const span = Math.round((startOfDay(period.to) - startOfDay(period.from)) / MS_PER_DAY);
  return span < 1 ? 1 : span;
};

export interface CombinedCoverage {
  /** What will actually be requested. */
  readonly days: number;
  /** Whether that is the period the reader chose, or something the view had to settle for. */
  readonly exact: boolean;
  /** Present only when `exact` is false: what to tell the reader, in their terms. */
  readonly note?: string;
}

const asDay = (date: Date): string =>
  date.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

/**
 * What the Combined views can serve for this period, and what to say when it is not what was asked.
 *
 * Two reasons it cannot be exact, and they can both apply. The period may be longer than 90 days,
 * which the endpoint refuses. Or it may not end today, in which case `days` would be read as a
 * recent window and the figures would belong to the wrong dates entirely.
 */
export const combinedCoverage = (period: DateRangePickerValue, today: Date = new Date()): CombinedCoverage => {
  const requested = daysSpanned(period);
  const days = Math.min(requested, COMBINED_MAX_DAYS);
  const endsToday = period.to !== undefined && startOfDay(period.to) === startOfDay(today);

  const reasons = [
    requested > COMBINED_MAX_DAYS
      ? `these figures cover the last ${COMBINED_MAX_DAYS} days, the longest this view can read`
      : undefined,
    endsToday ? undefined : `these figures end on ${asDay(today)}, not on the date you chose`,
  ].filter((reason): reason is string => reason !== undefined);

  if (reasons.length === 0) return { days, exact: true };
  return { days, exact: false, note: `${reasons.join(", and ")}.` };
};
