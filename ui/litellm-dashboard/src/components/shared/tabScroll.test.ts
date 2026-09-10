import { describe, expect, it } from "vitest";
import { affordance, stepFor } from "./tabScroll";

describe("affordance", () => {
  it("offers neither direction when everything fits", () => {
    expect(affordance({ scrollLeft: 0, scrollWidth: 500, clientWidth: 500 })).toEqual({
      canScrollLeft: false,
      canScrollRight: false,
    });
  });

  it("offers only right at the start of an overflowing strip", () => {
    expect(affordance({ scrollLeft: 0, scrollWidth: 1200, clientWidth: 600 })).toEqual({
      canScrollLeft: false,
      canScrollRight: true,
    });
  });

  it("offers both in the middle", () => {
    expect(affordance({ scrollLeft: 300, scrollWidth: 1200, clientWidth: 600 })).toEqual({
      canScrollLeft: true,
      canScrollRight: true,
    });
  });

  it("offers only left at the end", () => {
    expect(affordance({ scrollLeft: 600, scrollWidth: 1200, clientWidth: 600 })).toEqual({
      canScrollLeft: true,
      canScrollRight: false,
    });
  });

  it("treats a fraction short of the end as the end", () => {
    // Browsers report fractional widths, so an exact comparison leaves the right arrow
    // enabled at the end, pointing nowhere.
    expect(affordance({ scrollLeft: 599.6, scrollWidth: 1200, clientWidth: 600 }).canScrollRight).toBe(false);
  });

  it("treats a fraction past the start as the start", () => {
    expect(affordance({ scrollLeft: 0.4, scrollWidth: 1200, clientWidth: 600 }).canScrollLeft).toBe(false);
  });
});

describe("stepFor", () => {
  it("moves most of a screenful, leaving something in view to keep your place", () => {
    expect(stepFor(800)).toBe(600);
  });

  it("still moves a useful distance on a narrow strip", () => {
    // Three quarters of 100px is a step nobody would notice.
    expect(stepFor(100)).toBe(120);
  });

  it("rounds to whole pixels", () => {
    expect(Number.isInteger(stepFor(777))).toBe(true);
  });
});
