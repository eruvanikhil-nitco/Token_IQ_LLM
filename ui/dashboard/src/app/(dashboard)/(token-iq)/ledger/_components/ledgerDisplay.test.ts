import { describe, expect, it } from "vitest";

import { ADJUSTMENT_LABEL, ENTERED_BY_HAND, EVIDENCE_LABEL, OUTCOME_LABEL, evidenceLabel, evidenceWord, formatAmount, hasRemainder, remainderDirection } from "./ledgerDisplay";

describe("formatAmount", () => {
  it("keeps every digit rather than rounding a ledger line for display", () => {
    expect(formatAmount("0.00774700", "USD")).toBe("$0.00774700");
  });

  it("names a currency it has no symbol for rather than dropping it", () => {
    expect(formatAmount("10", "SEK")).toBe("SEK 10");
  });

  it("shows a dash, never a zero, when there is no amount", () => {
    expect(formatAmount(null, "USD")).toBe("—");
  });
});

describe("evidence copy", () => {
  it("says a reconciled figure came from the provider", () => {
    expect(EVIDENCE_LABEL.reconciled).toMatch(/provider/i);
  });

  it("does not claim the provider asserted an allocated figure", () => {
    expect(EVIDENCE_LABEL.allocated).not.toMatch(/provider asserted/i);
  });

  it("has copy for every level the backend can send", () => {
    ["reconciled", "priced", "allocated"].forEach((level) => expect(EVIDENCE_LABEL[level]).toBeTruthy());
  });
});

describe("outcome copy", () => {
  it("has copy for every outcome the backend can send", () => {
    (["balanced", "unexplained_difference", "currency_mismatch", "no_invoice"] as const).forEach((outcome) =>
      expect(OUTCOME_LABEL[outcome]).toBeTruthy(),
    );
  });

  it("does not call an unexplained difference balanced", () => {
    expect(OUTCOME_LABEL.unexplained_difference).not.toMatch(/balanced/i);
  });

  it("names every kind of adjustment a bill can carry", () => {
    (["credit", "discount", "tax", "commitment"] as const).forEach((kind) =>
      expect(ADJUSTMENT_LABEL[kind]).toBeTruthy(),
    );
  });
});

describe("hasRemainder", () => {
  it("is false only when nothing is left over", () => {
    expect(hasRemainder("0")).toBe(false);
    expect(hasRemainder("0.00000000")).toBe(false);
    expect(hasRemainder("0.0000072")).toBe(true);
    expect(hasRemainder("-0.0000072")).toBe(true);
  });
});

describe("remainderDirection", () => {
  it("tells being overcharged apart from usage not yet billed", () => {
    expect(remainderDirection("20")).toBe("over");
    expect(remainderDirection("-20")).toBe("under");
    expect(remainderDirection("0")).toBe("none");
  });
});

describe("how a line says its figure was arrived at", () => {
  it("explains each grade the provider gave", () => {
    expect(evidenceLabel("reconciled")).toContain("provider asserted");
    expect(evidenceLabel("priced")).toContain("rates");
    expect(evidenceLabel("allocated")).toContain("gateway");
  });

  it("says a line nobody asserted was entered by hand", () => {
    // A seat or an entered bill is a figure a person read off a contract. Blank, the column reads
    // as a grade that failed to load.
    expect(evidenceLabel(null)).toBe(ENTERED_BY_HAND);
    expect(evidenceWord(null)).toBe("entered");
  });

  it("shows a grade it has no sentence for rather than nothing", () => {
    expect(evidenceLabel("something-new")).toBe("something-new");
    expect(evidenceWord("something-new")).toBe("something-new");
  });
});
