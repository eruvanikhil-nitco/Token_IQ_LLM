import { describe, expect, it } from "vitest";

import { COMBINED_MAX_DAYS, combinedCoverage, daysSpanned } from "./usagePeriod";

const at = (iso: string) => new Date(`${iso}T12:00:00.000Z`);

describe("daysSpanned", () => {
  it("counts whole days between the ends, inclusive of the first", () => {
    expect(daysSpanned({ from: at("2026-10-01"), to: at("2026-10-08") })).toBe(7);
  });

  it("treats a single day as one day rather than none", () => {
    expect(daysSpanned({ from: at("2026-10-08"), to: at("2026-10-08") })).toBe(1);
  });

  it("is at least one day even when the ends arrive reversed", () => {
    expect(daysSpanned({ from: at("2026-10-08"), to: at("2026-10-01") })).toBe(1);
  });

  it("falls back to the default when a date is missing", () => {
    expect(daysSpanned({ from: undefined, to: at("2026-10-08") })).toBe(30);
  });
});

describe("combinedCoverage", () => {
  const today = at("2026-10-08");

  it("serves a period that ends today and fits the cap, exactly", () => {
    const coverage = combinedCoverage({ from: at("2026-10-01"), to: today }, today);
    expect(coverage).toEqual({ days: 7, exact: true });
  });

  it("says so when the period is longer than it can read", () => {
    // The combined endpoints take days with ge=1, le=90, so a year to date cannot be served.
    const coverage = combinedCoverage({ from: at("2026-01-01"), to: today }, today);
    expect(coverage.days).toBe(COMBINED_MAX_DAYS);
    expect(coverage.exact).toBe(false);
    expect(coverage.note).toContain("90 days");
  });

  it("says so when the period does not end today", () => {
    // `days` always means "the last N days", so an earlier window would be shown as a recent one.
    // Reporting that silently is the bug this whole task exists to remove.
    const coverage = combinedCoverage({ from: at("2026-09-01"), to: at("2026-09-08") }, today);
    expect(coverage.exact).toBe(false);
    expect(coverage.note).toContain("8 October");
  });

  it("never claims to be exact when it had to change the period", () => {
    const coverage = combinedCoverage({ from: at("2025-01-01"), to: at("2025-06-01") }, today);
    expect(coverage.exact).toBe(false);
    expect(coverage.days).toBeLessThanOrEqual(COMBINED_MAX_DAYS);
  });
});
