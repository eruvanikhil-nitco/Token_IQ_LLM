/**
 * Which way a horizontally scrolling strip can still move.
 *
 * A tab strip that overflows already scrolls, but with the scrollbar hidden there is nothing
 * to tell you more tabs exist or how to reach them. Arrows only help if they appear exactly
 * when there is somewhere to go, so this decides that from the element's own measurements.
 */

export interface ScrollMetrics {
  readonly scrollLeft: number;
  readonly scrollWidth: number;
  readonly clientWidth: number;
}

export interface ScrollAffordance {
  readonly canScrollLeft: boolean;
  readonly canScrollRight: boolean;
}

/**
 * Sub-pixel slack.
 *
 * Browsers report fractional widths, and a strip scrolled fully right often lands a fraction
 * short of scrollWidth - clientWidth. Comparing exactly leaves the right arrow enabled at the
 * end, pointing nowhere.
 */
const EPSILON = 1;

export const affordance = ({ scrollLeft, scrollWidth, clientWidth }: ScrollMetrics): ScrollAffordance => ({
  canScrollLeft: scrollLeft > EPSILON,
  canScrollRight: scrollLeft + clientWidth < scrollWidth - EPSILON,
});

/**
 * How far one press should move the strip.
 *
 * Most of a screenful, so a press makes obvious progress while leaving a tab or two in view to
 * keep your place. Never more than the strip can actually scroll.
 */
export const stepFor = (clientWidth: number): number => Math.max(120, Math.round(clientWidth * 0.75));
