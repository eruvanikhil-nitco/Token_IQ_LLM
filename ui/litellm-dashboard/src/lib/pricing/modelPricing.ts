/**
 * Custom per-model pricing: the single owner of how rates cross the UI/backend boundary.
 *
 * Three screens deal in these rates, and each one used to carry its own copy of the rules
 * below. That is a bad place for duplication, because every rule here is a factor-of-a-million
 * or a real-money default, and a copy that drifts produces spend logs that are quietly wrong
 * rather than visibly broken.
 *
 * Two facts drive everything in this file:
 *
 *   1. The UI talks in dollars per million tokens, the backend stores dollars per token.
 *   2. The two forms named the same four rates differently, so the names have to meet
 *      somewhere. That somewhere is `BACKEND_PARAM`.
 */

/** The four rates, named as this module names them. */
export const PRICING_FIELDS = ["input", "output", "cacheRead", "cacheWrite"] as const;
export type PricingField = (typeof PRICING_FIELDS)[number];

/**
 * The one place the UI's names and the backend's names meet.
 *
 * Add Model spelled these `input_cost_per_token` and the edit form spelled them `input_cost`,
 * for the same number. Anything that needs the wire name asks here.
 */
export const BACKEND_PARAM: Readonly<Record<PricingField, string>> = {
  input: "input_cost_per_token",
  output: "output_cost_per_token",
  cacheRead: "cache_read_input_token_cost",
  cacheWrite: "cache_creation_input_token_cost",
};

/**
 * The edit form's own names for the same four rates.
 *
 * Add Model names its fields after the wire format, so `BACKEND_PARAM` doubles as its form
 * vocabulary. The edit form does not, and this is the only place that difference is written
 * down; anywhere else would be a second copy of exactly the mapping this module exists to own.
 */
export const EDIT_FORM_FIELD: Readonly<Record<PricingField, string>> = {
  input: "input_cost",
  output: "output_cost",
  cacheRead: "cache_read_cost",
  cacheWrite: "cache_write_cost",
};

/** Per-second pricing is an alternative to the four per-token rates, and is stored as typed. */
export const PER_SECOND_PARAM = "input_cost_per_second";

const PER_MILLION = 1_000_000;

/** A rate as a form holds it: a typed string, a number, or nothing. */
export type RateInput = string | number | null | undefined;

export type PricingValues = Readonly<Record<PricingField, RateInput>>;

/**
 * Blank means "no rate", which is not the same as zero.
 *
 * A zero rate is a real setting: it is how a model is exempted from budget accounting. Treating
 * it as blank would silently drop it and start charging for a model meant to be free.
 */
export const isBlank = (value: RateInput): boolean => value === undefined || value === null || value === "";

const toNumber = (value: RateInput): number => Number(value);

/* -------------------------------------------------------------------------- */
/* Reading: backend -> form                                                    */
/* -------------------------------------------------------------------------- */

/** Where a stored rate can be found, in the order it should be trusted. */
export interface RateSource {
  readonly litellm_params?: Readonly<Record<string, unknown>> | null;
  readonly model_info?: Readonly<Record<string, unknown>> | null;
}

const asRate = (value: unknown): number | null => (typeof value === "number" ? value : null);

/**
 * The first rate that is actually set, scaled to the per-million figure the UI shows.
 *
 * A deployment's own override lives in `litellm_params`; `model_info` carries what the built-in
 * price map knows. Falling through in that order is what makes an un-overridden model show the
 * map's rate rather than a blank.
 */
export const perMillion = (...rates: readonly (number | null | undefined)[]): number | null => {
  const rate = rates.find((candidate) => candidate != null);
  return rate == null ? null : rate * PER_MILLION;
};

export const readRate = (source: RateSource, field: PricingField): number | null =>
  perMillion(asRate(source.litellm_params?.[BACKEND_PARAM[field]]), asRate(source.model_info?.[BACKEND_PARAM[field]]));

/** Every rate on a deployment, as per-million figures for display. */
export const readRates = (source: RateSource): Readonly<Record<PricingField, number | null>> =>
  Object.fromEntries(PRICING_FIELDS.map((field) => [field, readRate(source, field)])) as Record<
    PricingField,
    number | null
  >;

/* -------------------------------------------------------------------------- */
/* Writing: form -> backend                                                    */
/* -------------------------------------------------------------------------- */

/**
 * How a blank field should be understood.
 *
 * On create there is no stored value, so a blank simply means "do not send this". On update
 * there may be an override already stored, so a blank the user actually cleared has to travel
 * as an explicit null; omitting it under PATCH means "leave as is" and the old rate survives.
 * That difference is the whole reason this is a tagged union rather than a boolean.
 */
export type WriteMode =
  | { readonly kind: "create" }
  | { readonly kind: "update"; readonly touched: ReadonlySet<PricingField> };

const wasTouched = (mode: WriteMode, field: PricingField): boolean =>
  mode.kind === "update" && mode.touched.has(field);

/** A rate converted for storage, or null to clear it, or absent to leave it alone. */
type Resolved = { readonly send: true; readonly value: number | null } | { readonly send: false };

const OMIT: Resolved = { send: false };

const send = (value: number | null): Resolved => ({ send: true, value });

const perToken = (value: RateInput): number => toNumber(value) / PER_MILLION;

/** Input, output and cache-write all follow the same rule; only cache-read is special. */
const resolvePlain = (value: RateInput, mode: WriteMode, field: PricingField): Resolved => {
  if (mode.kind === "update" && !wasTouched(mode, field)) return OMIT;
  if (!isBlank(value)) return send(perToken(value));
  return mode.kind === "create" ? OMIT : send(null);
};

/**
 * Cache-read defaults to the input rate when it is left blank.
 *
 * The backend has no such fallback for this key, so leaving it out would bill cached reads at
 * whatever the price map says rather than at the override the user just set. Writing the input
 * rate into it is what makes "blank means same as input" true.
 */
const resolveCacheRead = (values: PricingValues, mode: WriteMode): Resolved => {
  const own = values.cacheRead;
  const touchedRead = wasTouched(mode, "cacheRead");

  if (mode.kind === "update" && !touchedRead && !wasTouched(mode, "input")) return OMIT;
  if (!isBlank(own)) return send(perToken(own));
  if (touchedRead) return send(null);
  return isBlank(values.input) ? OMIT : send(perToken(values.input));
};

const resolve = (values: PricingValues, mode: WriteMode, field: PricingField): Resolved =>
  field === "cacheRead" ? resolveCacheRead(values, mode) : resolvePlain(values[field], mode, field);

/**
 * The rates to write, keyed by their backend names.
 *
 * A field that should be left untouched is absent rather than null, so this can be spread into
 * a PATCH body without clearing anything the user never edited.
 */
export const buildPricingPatch = (
  values: PricingValues,
  mode: WriteMode,
): Readonly<Record<string, number | null>> =>
  Object.fromEntries(
    PRICING_FIELDS.flatMap((field) => {
      const outcome = resolve(values, mode, field);
      return outcome.send ? [[BACKEND_PARAM[field], outcome.value] as const] : [];
    }),
  );

/** Per-second pricing is stored exactly as typed, with no per-million scaling. */
export const buildPerSecondPatch = (value: RateInput): Readonly<Record<string, number>> =>
  isBlank(value) ? {} : { [PER_SECOND_PARAM]: toNumber(value) };

/* -------------------------------------------------------------------------- */
/* Validation                                                                  */
/* -------------------------------------------------------------------------- */

export type RateError = "not-a-number" | "negative" | "ptu-conflict";

export const RATE_ERROR_TEXT: Readonly<Record<RateError, string>> = {
  "not-a-number": "Must be a number",
  negative: "Must be zero or more",
  "ptu-conflict": "A PTU deployment bills by reserved capacity, so this cost must be 0 or blank",
};

/**
 * Whether a typed rate can be stored.
 *
 * A PTU deployment has already paid for its throughput up front, so charging per token on top
 * would count the same spend twice. Both existing forms enforced that; it belongs here now.
 */
export const validateRate = (value: RateInput, ptuCount: RateInput): RateError | null => {
  if (isBlank(value)) return null;

  const parsed = toNumber(value);
  if (!Number.isFinite(parsed)) return "not-a-number";
  if (parsed < 0) return "negative";
  if (!isBlank(ptuCount) && parsed !== 0) return "ptu-conflict";
  return null;
};

/** Every rate that fails validation, so a form can mark them all at once. */
export const validateRates = (
  values: PricingValues,
  ptuCount: RateInput,
): Readonly<Partial<Record<PricingField, RateError>>> =>
  Object.fromEntries(
    PRICING_FIELDS.flatMap((field) => {
      const error = validateRate(values[field], ptuCount);
      return error === null ? [] : [[field, error] as const];
    }),
  );
