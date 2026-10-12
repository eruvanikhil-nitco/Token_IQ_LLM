import { describe, expect, it } from "vitest";

import { PERIOD_CHOICES, isWholeMonth, monthOptions, periodFor, periodLabel } from "./period";

/**
 * One period, because there were three and two of them were wrong.
 *
 * `defaultPeriod()` was copy-pasted into the Ledger, the Overview page and Recommendations. The
 * Ledger's ran to the last day of the month; the other two ran to today. So the Overview total and
 * the Ledger total described different periods, and a reader comparing the two was comparing month
 * to date against a whole month with nothing on either screen saying so.
 *
 * The fix is not to pick one of the two. It is to name both, because both are things a reader
 * means, and to say which one a figure is for.
 */

const MID_MONTH = new Date(Date.UTC(2026, 8, 15, 10, 30));
const FIRST_OF_MONTH = new Date(Date.UTC(2026, 8, 1, 0, 5));
const LAST_OF_MONTH = new Date(Date.UTC(2026, 8, 30, 23, 55));

describe("the periods a reader means", () => {
  it("offers month to date, this whole month, and last month", () => {
    expect(PERIOD_CHOICES).toEqual(["month-to-date", "this-month", "last-month", "last-30-days", "named-month"]);
  });

  it("gives every choice a name a reader would use", () => {
    for (const choice of PERIOD_CHOICES) {
      expect(periodLabel(choice), choice).toBeTruthy();
    }
  });
});

describe("month to date", () => {
  it("runs from the first of the month to today", () => {
    expect(periodFor("month-to-date", MID_MONTH)).toEqual({ start: "2026-09-01", end: "2026-09-15" });
  });

  it("is one day long on the first of the month", () => {
    // Not an empty period. A figure for the first of the month is the month's figure so far.
    expect(periodFor("month-to-date", FIRST_OF_MONTH)).toEqual({ start: "2026-09-01", end: "2026-09-01" });
  });
});

describe("this whole month", () => {
  it("runs from the first to the last day, whatever today is", () => {
    // What the Ledger meant. A bill covers the month, so reconciling it against part of the month
    // reports a difference the size of the days that have not happened yet.
    expect(periodFor("this-month", MID_MONTH)).toEqual({ start: "2026-09-01", end: "2026-09-30" });
  });

  it("knows how long the month is", () => {
    expect(periodFor("this-month", new Date(Date.UTC(2026, 1, 10)))).toEqual({
      start: "2026-02-01",
      end: "2026-02-28",
    });
    expect(periodFor("this-month", new Date(Date.UTC(2024, 1, 10)))).toEqual({
      start: "2024-02-01",
      end: "2024-02-29",
    });
  });
});

describe("last month", () => {
  it("runs from the first to the last day of the month before", () => {
    expect(periodFor("last-month", MID_MONTH)).toEqual({ start: "2026-08-01", end: "2026-08-31" });
  });

  it("crosses a year boundary without inventing a month thirteen", () => {
    expect(periodFor("last-month", new Date(Date.UTC(2027, 0, 5)))).toEqual({
      start: "2026-12-01",
      end: "2026-12-31",
    });
  });
});

describe("the last thirty days", () => {
  it("ends today and starts twenty-nine days earlier, so it is thirty days long", () => {
    // The window the data-quality checks and the Uploads tab already use, so a reader moving
    // between them is looking at the same days.
    expect(periodFor("last-30-days", MID_MONTH)).toEqual({ start: "2026-08-17", end: "2026-09-15" });
  });
});

describe("what a period says about itself", () => {
  it("distinguishes month to date from the whole month, in words", () => {
    // The whole point. Two figures over two periods that look alike is the thing that was wrong.
    expect(periodLabel("month-to-date")).not.toBe(periodLabel("this-month"));
    expect(periodLabel("month-to-date")).toMatch(/to date/i);
  });

  it("reads the same whatever time of day it is asked", () => {
    // Every figure in this product is by day, so a period must not move with the clock.
    const early = periodFor("month-to-date", new Date(Date.UTC(2026, 8, 15, 0, 1)));
    const late = periodFor("month-to-date", LAST_OF_MONTH.getUTCDate() === 30 ? new Date(Date.UTC(2026, 8, 15, 23, 59)) : LAST_OF_MONTH);

    expect(early).toEqual(late);
  });
});

describe("whether a period is a whole month", () => {
  it("says so for the first to the last day of one month", () => {
    expect(isWholeMonth({ start: "2026-09-01", end: "2026-09-30" })).toBe(true);
    expect(isWholeMonth({ start: "2024-02-01", end: "2024-02-29" })).toBe(true);
  });

  it("says no for month to date", () => {
    // Invoice Reconciliation needs this: a bill covers the month, so comparing it against part of
    // one reports a difference the size of the days that have not happened yet.
    expect(isWholeMonth({ start: "2026-09-01", end: "2026-09-15" })).toBe(false);
  });

  it("says no for a period that starts mid-month", () => {
    expect(isWholeMonth({ start: "2026-09-02", end: "2026-09-30" })).toBe(false);
  });

  it("says no for a period spanning two months", () => {
    expect(isWholeMonth({ start: "2026-08-01", end: "2026-09-30" })).toBe(false);
  });

  it("says no for a last day that is not the month's last day", () => {
    expect(isWholeMonth({ start: "2026-02-01", end: "2026-02-29" })).toBe(false);
  });

  it("says no for dates it cannot read rather than guessing", () => {
    expect(isWholeMonth({ start: "September", end: "2026-09-30" })).toBe(false);
  });
});

describe("a month a reader names", () => {
  it("covers the whole of that month", () => {
    // A month is closed long after it ends: a finance team reconciles September in November.
    expect(periodFor("named-month", MID_MONTH, "2026-06")).toEqual({ start: "2026-06-01", end: "2026-06-30" });
  });

  it("knows how long the named month is", () => {
    expect(periodFor("named-month", MID_MONTH, "2024-02").end).toBe("2024-02-29");
  });

  it("falls back to this month rather than a period nobody chose", () => {
    // A blank or unreadable month must not become an empty period, which would read as a month
    // nobody spent anything in.
    expect(periodFor("named-month", MID_MONTH, null)).toEqual(periodFor("this-month", MID_MONTH));
    expect(periodFor("named-month", MID_MONTH, "whenever")).toEqual(periodFor("this-month", MID_MONTH));
    expect(periodFor("named-month", MID_MONTH, "2026-13")).toEqual(periodFor("this-month", MID_MONTH));
  });

  it("offers a year of months, newest first", () => {
    const months = monthOptions(MID_MONTH);

    expect(months).toHaveLength(12);
    expect(months[0]).toEqual({ value: "2026-09", label: "September 2026" });
    expect(months[11]).toEqual({ value: "2025-10", label: "October 2025" });
  });

  it("crosses a year boundary without inventing a month thirteen", () => {
    expect(monthOptions(new Date(Date.UTC(2027, 0, 5)))[1]).toEqual({ value: "2026-12", label: "December 2026" });
  });

  it("is a whole month, which is what reconciliation needs", () => {
    expect(isWholeMonth(periodFor("named-month", MID_MONTH, "2026-06"))).toBe(true);
  });
});
