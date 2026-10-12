"use client";

import { PERIOD_CHOICES, monthOptions, periodLabel } from "./period";
import { usePeriod } from "./PeriodContext";

/**
 * The period control in the top bar, which every page that shows money then reads.
 *
 * It names the days it covers beside the choice, because "month to date" and "this whole month"
 * are the two things a reader means and the difference between them is the whole reason this
 * exists: the same spend looked like two different figures depending on which page you were on.
 */
export default function PeriodPicker() {
  const { choice, month, period, setChoice } = usePeriod();
  const months = monthOptions();

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="sr-only">Period</span>
      <select
        aria-label="Period"
        className="h-8 rounded-md border bg-background px-2 text-sm"
        value={choice}
        onChange={(event) => {
          const next = event.target.value as typeof choice;
          // A named month needs a month, so choosing it lands on the most recent one rather than
          // on a blank that would silently mean this month.
          setChoice(next, next === "named-month" ? (month ?? months[0].value) : null);
        }}
      >
        {PERIOD_CHOICES.map((option) => (
          <option key={option} value={option}>
            {periodLabel(option)}
          </option>
        ))}
      </select>
      {choice === "named-month" ? (
        <select
          aria-label="Month"
          className="h-8 rounded-md border bg-background px-2 text-sm"
          value={month ?? months[0].value}
          onChange={(event) => setChoice("named-month", event.target.value)}
        >
          {months.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : null}
      <span className="hidden text-xs whitespace-nowrap text-muted-foreground lg:inline">
        {period.start} to {period.end}
      </span>
    </label>
  );
}
