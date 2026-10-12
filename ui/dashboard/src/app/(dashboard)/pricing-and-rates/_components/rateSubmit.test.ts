import { describe, expect, it } from "vitest";

import {
  EMPTY_CURRENCY,
  EMPTY_RATE,
  canSaveCurrency,
  canSaveRate,
  currencyPayload,
  currencyProblem,
  periodProblem,
  periodSummary,
  ratePayload,
  rateProblem,
  rateSummary,
  type CurrencyDraft,
  type RateDraft,
} from "./rateSubmit";

/**
 * What the two rate forms refuse before sending anything.
 *
 * The server refuses the same things, which is deliberate rather than duplicated: a form that
 * posts a rate it knows will be rejected makes an administrator read an error about a figure they
 * can already see is wrong, and the server's refusal has to stay because any other client would
 * otherwise get through.
 */

const DISCOUNT: RateDraft = {
  ...EMPTY_RATE,
  provider: "anthropic",
  basis: "discount",
  amount: "20",
  effectiveFrom: "2026-09-01",
  source: "enterprise agreement",
};

const COMMITTED: RateDraft = {
  ...EMPTY_RATE,
  provider: "anthropic",
  model: "claude-sonnet",
  field: "input_cost_per_token",
  basis: "unit_price",
  amount: "2.50",
  effectiveFrom: "2026-09-01",
  source: "committed-use agreement",
};

const CURRENCY: CurrencyDraft = {
  ...EMPTY_CURRENCY,
  sourceCurrency: "EUR",
  targetCurrency: "USD",
  rate: "1.0823",
  effectiveFrom: "2026-09-01",
  source: "the rate finance booked September at",
};

describe("a provider rate the form will send", () => {
  it("accepts a discount across a provider", () => {
    expect(rateProblem(DISCOUNT)).toBeNull();
    expect(canSaveRate(DISCOUNT)).toBe(true);
  });

  it("accepts a committed price for one model and meter", () => {
    expect(canSaveRate(COMMITTED)).toBe(true);
  });

  it("sends the figure on the field its kind uses", () => {
    expect(ratePayload(DISCOUNT)).toMatchObject({ basis: "discount", percent_off: "20", per_million: null });
    expect(ratePayload(COMMITTED)).toMatchObject({ basis: "unit_price", percent_off: null, per_million: "2.50" });
  });

  it("sends a rate covering every model as null rather than as a word", () => {
    // A screen writes "every model"; a payload writing it would put a model nobody can look up
    // into a field the server matches on.
    expect(ratePayload(DISCOUNT)).toMatchObject({ model: null, field: null });
  });

  it("sends an open-ended rate with no end", () => {
    expect(ratePayload(DISCOUNT).effective_to).toBeNull();
  });

  it("keeps the digits that were typed", () => {
    expect(ratePayload({ ...COMMITTED, amount: " 2.5000 " }).per_million).toBe("2.5000");
  });
});

describe("a provider rate the form refuses", () => {
  it("refuses a rate with no provider", () => {
    expect(rateProblem({ ...DISCOUNT, provider: "" })).toBeTruthy();
  });

  it("refuses a rate nobody can trace", () => {
    // The source is how a figure gets corrected later. Without it the row is a number with no
    // provenance, which nobody will touch and everybody will doubt.
    expect(rateProblem({ ...DISCOUNT, source: "   " })).toBeTruthy();
  });

  it("refuses a figure with a percent sign in it", () => {
    const problem = rateProblem({ ...DISCOUNT, amount: "20%" });

    expect(problem).toContain("percent sign");
  });

  it("refuses a discount over a hundred per cent", () => {
    expect(rateProblem({ ...DISCOUNT, amount: "120" })).toContain("negative");
  });

  it("refuses a negative discount, naming what to record instead", () => {
    expect(rateProblem({ ...DISCOUNT, amount: "-5" })).toContain("committed price");
  });

  it("accepts a free month, because credits are real", () => {
    expect(rateProblem({ ...DISCOUNT, amount: "100" })).toBeNull();
  });

  it("refuses a committed price with no model", () => {
    expect(rateProblem({ ...COMMITTED, model: "" })).toContain("model");
  });

  it("refuses a committed price with no meter", () => {
    expect(rateProblem({ ...COMMITTED, field: "" })).toContain("meter");
  });

  it("refuses a rate with no start, saying why a period matters", () => {
    const problem = periodProblem({ ...DISCOUNT, effectiveFrom: "" });

    expect(problem).toContain("closed month");
  });

  it("refuses a period that ends before it starts", () => {
    expect(periodProblem({ ...DISCOUNT, effectiveTo: "2026-08-01" })).toContain("ends before it starts");
  });

  it("says nothing about a last day left empty", () => {
    expect(periodProblem({ ...DISCOUNT, effectiveTo: "" })).toBeNull();
  });
});

describe("a conversion rate", () => {
  it("accepts a pair with a rate and a source", () => {
    expect(currencyProblem(CURRENCY)).toBeNull();
    expect(canSaveCurrency(CURRENCY)).toBe(true);
  });

  it("sends both currencies upper case so a pair matches itself", () => {
    const payload = currencyPayload({ ...CURRENCY, sourceCurrency: "eur", targetCurrency: "usd" });

    expect([payload.source_currency, payload.target_currency]).toEqual(["EUR", "USD"]);
  });

  it("refuses a currency that is not a three-letter code", () => {
    expect(currencyProblem({ ...CURRENCY, sourceCurrency: "euro" })).toBeTruthy();
  });

  it("refuses a currency converting to itself", () => {
    expect(currencyProblem({ ...CURRENCY, targetCurrency: "eur" })).toContain("converts to itself");
  });

  it("refuses a rate of zero, which would report every euro as nothing", () => {
    expect(currencyProblem({ ...CURRENCY, rate: "0" })).toBeTruthy();
  });

  it("refuses a negative rate", () => {
    expect(currencyProblem({ ...CURRENCY, rate: "-1.08" })).toBeTruthy();
  });

  it("refuses a rate nobody can trace", () => {
    expect(currencyProblem({ ...CURRENCY, source: "" })).toBeTruthy();
  });

  it("refuses a period that ends before it starts", () => {
    expect(canSaveCurrency({ ...CURRENCY, effectiveTo: "2026-08-01" })).toBe(false);
  });

  it("keeps the digits that were typed", () => {
    expect(currencyPayload({ ...CURRENCY, rate: " 1.08230 " }).rate).toBe("1.08230");
  });
});

describe("how a recorded rate reads in a table", () => {
  it("says a discount as a percentage off list", () => {
    expect(rateSummary({ basis: "discount", percent_off: "20", per_million: null })).toBe("20% off list");
  });

  it("says a committed price per million", () => {
    expect(rateSummary({ basis: "unit_price", percent_off: null, per_million: "2.50" })).toBe("2.50 per million");
  });

  it("says an open-ended period as from a day", () => {
    expect(periodSummary("2026-09-01", null)).toBe("from 2026-09-01");
  });

  it("says a closed period as both days", () => {
    expect(periodSummary("2026-09-01", "2026-12-31")).toBe("2026-09-01 to 2026-12-31");
  });
});
