/**
 * What the two rate forms send, and what they refuse before sending it.
 *
 * The server refuses the same things, with the same reasons, and that is the point rather than a
 * duplication: a form that posts a rate it knows the server will reject makes an administrator read
 * an error about a figure they can see is wrong. The server's refusal stays because any other
 * client would otherwise get through.
 *
 * Every amount leaves as the string that was typed. Parsed into a number it would be rounded
 * somewhere between the form and the contract it came from.
 */

import type { CurrencyRateBody, ProviderRateBody } from "@/components/networking";

export const PRICE_FIELDS = [
  { value: "input_cost_per_token", label: "Input" },
  { value: "output_cost_per_token", label: "Output" },
  { value: "cache_read_input_token_cost", label: "Cached input" },
  { value: "cache_creation_input_token_cost", label: "Cache write" },
] as const;

const AMOUNT = /^-?\d+(\.\d+)?$/;
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

export interface RateDraft {
  provider: string;
  model: string;
  field: string;
  basis: "discount" | "unit_price";
  amount: string;
  effectiveFrom: string;
  effectiveTo: string;
  source: string;
}

export const EMPTY_RATE: RateDraft = {
  provider: "",
  model: "",
  field: "",
  basis: "discount",
  amount: "",
  effectiveFrom: "",
  effectiveTo: "",
  source: "",
};

/**
 * Why this rate cannot be recorded, in the words the server would use.
 *
 * A committed price needs a model and a meter: one price across a catalogue would price a small
 * model like a large one, and one price across meters would charge output at the input rate, which
 * differ by a factor of three or more at list.
 */
export function rateProblem(draft: RateDraft): string | null {
  if (draft.provider === "") {
    return "Choose the provider whose bill this covers.";
  }
  if (draft.source.trim() === "") {
    return "Say where this rate came from, so somebody can check it later.";
  }
  const amount = draft.amount.trim();
  if (amount === "" || !AMOUNT.test(amount)) {
    return "Enter the figure in digits, with no percent sign and no currency symbol.";
  }
  if (draft.basis === "discount") {
    return discountProblem(amount);
  }
  return committedPriceProblem(draft, amount);
}

function discountProblem(amount: string): string | null {
  if (Number(amount) < 0) {
    return "A discount cannot be negative. A price above list is recorded as a committed price.";
  }
  if (Number(amount) > 100) {
    return "A discount over a hundred per cent would make spend negative.";
  }
  return null;
}

function committedPriceProblem(draft: RateDraft, amount: string): string | null {
  if (Number(amount) < 0) {
    return "A price cannot be negative.";
  }
  if (draft.model.trim() === "") {
    return "A committed price needs a model: one price across a catalogue prices a small model like a large one.";
  }
  if (draft.field === "") {
    return "A committed price needs a meter: input and output differ by a factor of three or more at list.";
  }
  return null;
}

/** Whether the dates are readable and in order. Separate, so a half-typed date is not an error yet. */
export function periodProblem(draft: RateDraft): string | null {
  if (!ISO_DAY.test(draft.effectiveFrom)) {
    return "Give the first day this rate applies, so a closed month prices at the rate that applied then.";
  }
  if (draft.effectiveTo !== "" && !ISO_DAY.test(draft.effectiveTo)) {
    return "That last day is not a date.";
  }
  if (draft.effectiveTo !== "" && draft.effectiveTo < draft.effectiveFrom) {
    return "The period ends before it starts.";
  }
  return null;
}

export function canSaveRate(draft: RateDraft): boolean {
  return rateProblem(draft) === null && periodProblem(draft) === null;
}

export function ratePayload(draft: RateDraft): ProviderRateBody {
  const amount = draft.amount.trim();
  return {
    provider: draft.provider,
    model: draft.model.trim() === "" ? null : draft.model.trim(),
    field: draft.field === "" ? null : draft.field,
    basis: draft.basis,
    percent_off: draft.basis === "discount" ? amount : null,
    per_million: draft.basis === "unit_price" ? amount : null,
    effective_from: draft.effectiveFrom,
    effective_to: draft.effectiveTo === "" ? null : draft.effectiveTo,
    source: draft.source.trim(),
  };
}

export interface CurrencyDraft {
  sourceCurrency: string;
  targetCurrency: string;
  rate: string;
  effectiveFrom: string;
  effectiveTo: string;
  source: string;
}

export const EMPTY_CURRENCY: CurrencyDraft = {
  sourceCurrency: "",
  targetCurrency: "",
  rate: "",
  effectiveFrom: "",
  effectiveTo: "",
  source: "",
};

const CURRENCY_CODE = /^[A-Za-z]{3}$/;

/**
 * Why this conversion rate cannot be recorded.
 *
 * A rate recorded the other way round is not inverted anywhere in this product, so the form says so
 * rather than letting somebody record one direction and wonder why the other does not convert.
 */
export function currencyProblem(draft: CurrencyDraft): string | null {
  if (!CURRENCY_CODE.test(draft.sourceCurrency) || !CURRENCY_CODE.test(draft.targetCurrency)) {
    return "Give both currencies as three-letter codes, such as EUR and USD.";
  }
  if (draft.sourceCurrency.toUpperCase() === draft.targetCurrency.toUpperCase()) {
    return "A currency converts to itself at one, so there is no rate to record.";
  }
  const rate = draft.rate.trim();
  if (rate === "" || !AMOUNT.test(rate) || Number(rate) <= 0) {
    return "Enter the rate in digits: how many of the second currency one of the first buys.";
  }
  if (draft.source.trim() === "") {
    return "Say where this rate came from, so a converted figure can be checked.";
  }
  return null;
}

/** The period check reads the same two fields on either draft, so both share one shape for it. */
export function currencyPeriodProblem(draft: CurrencyDraft): string | null {
  const dated: RateDraft = { ...EMPTY_RATE, effectiveFrom: draft.effectiveFrom, effectiveTo: draft.effectiveTo };
  return periodProblem(dated);
}

export function canSaveCurrency(draft: CurrencyDraft): boolean {
  return currencyProblem(draft) === null && currencyPeriodProblem(draft) === null;
}

export function currencyPayload(draft: CurrencyDraft): CurrencyRateBody {
  return {
    source_currency: draft.sourceCurrency.toUpperCase(),
    target_currency: draft.targetCurrency.toUpperCase(),
    rate: draft.rate.trim(),
    effective_from: draft.effectiveFrom,
    effective_to: draft.effectiveTo === "" ? null : draft.effectiveTo,
    source: draft.source.trim(),
  };
}

/** How a recorded rate reads in a table: "20% off list" or "$2.50 per million". */
export function rateSummary(rate: { basis: string; percent_off: string | null; per_million: string | null }): string {
  if (rate.basis === "discount") {
    return `${rate.percent_off ?? "?"}% off list`;
  }
  return `${rate.per_million ?? "?"} per million`;
}

/** The period a rate covers, as a reader would say it. */
export function periodSummary(from: string, to: string | null): string {
  return to === null ? `from ${from}` : `${from} to ${to}`;
}
