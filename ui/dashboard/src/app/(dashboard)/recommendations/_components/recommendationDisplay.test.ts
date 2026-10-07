import { describe, expect, it } from "vitest";

import { DECISION_LABEL, FIGURE_LABEL, KIND_LABEL, formatFigure } from "./recommendationDisplay";

describe("figure labels", () => {
  it("never labels money already being spent as a saving", () => {
    expect(FIGURE_LABEL.already_spent_unwatched).not.toMatch(/saving|save/i);
  });

  it("says plainly when money could stop being spent", () => {
    expect(FIGURE_LABEL.could_stop_spending).toMatch(/stop/i);
  });

  it("has no label at all for a card with no figure", () => {
    expect(FIGURE_LABEL.none).toBe("");
  });
});

describe("formatFigure", () => {
  it("keeps every digit rather than rounding for display", () => {
    expect(formatFigure("0.00774700", "already_spent_unwatched", "USD")).toBe("$0.00774700");
  });

  it("shows nothing at all when a card has no honest figure", () => {
    expect(formatFigure(null, "none", null)).toBe("");
  });

  it("shows nothing rather than a zero when the kind says there is no figure", () => {
    expect(formatFigure("0", "none", "USD")).toBe("");
  });

  it("names a currency it has no symbol for rather than dropping it", () => {
    expect(formatFigure("10", "could_stop_spending", "EUR")).toBe("EUR 10");
  });
});

describe("labels", () => {
  it("has copy for both kinds of card", () => {
    (["business", "technical"] as const).forEach((k) => expect(KIND_LABEL[k]).toBeTruthy());
  });

  it("has copy for both decisions", () => {
    (["done", "dismissed"] as const).forEach((d) => expect(DECISION_LABEL[d]).toBeTruthy());
  });
});
