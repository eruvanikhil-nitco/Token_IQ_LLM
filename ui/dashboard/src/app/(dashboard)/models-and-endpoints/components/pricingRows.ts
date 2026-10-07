/**
 * One row of the Model Pricing table.
 *
 * The rules for what a rate means and how it crosses the wire live in `@/lib/pricing`; this
 * only covers what a table needs on top of them: turning a deployment into editable text,
 * working out what the user actually changed, and refusing to offer an edit that cannot be
 * saved.
 */

import {
  BACKEND_PARAM,
  buildPricingPatch,
  isBlank,
  readRates,
  validateRate,
  PRICING_FIELDS,
  type PricingField,
  type RateError,
} from "@/lib/pricing/modelPricing";

export interface ModelRow {
  readonly model_name: string;
  readonly model_info?: { readonly id?: string; readonly db_model?: boolean; readonly ptu_count?: unknown } | null;
  readonly litellm_params?: Readonly<Record<string, unknown>> | null;
}

/** The four rates as the inputs hold them: text, blank for no rate. */
export type RateText = Readonly<Record<PricingField, string>>;

export const EMPTY_RATES: RateText = { input: "", output: "", cacheRead: "", cacheWrite: "" };

export const modelId = (model: ModelRow): string => model.model_info?.id ?? "";

/**
 * Whether this row can be edited.
 *
 * Only deployments stored in the database can be patched. A model declared in the config file
 * is read-only through the API, so an editable input would promise a save that cannot happen.
 */
export const isEditable = (model: ModelRow): boolean => model.model_info?.db_model === true;

/**
 * Whether a rate is the deployment's own or the built-in price map's.
 *
 * The table shows both, because a blank where the map has a rate would suggest the model is
 * free. Marking which is which is what stops the map's numbers reading as your settings.
 */
export const isOverridden = (model: ModelRow, field: PricingField): boolean =>
  model.litellm_params?.[BACKEND_PARAM[field]] != null;

/**
 * Whether this cell shows the built-in rate rather than one the deployment sets.
 *
 * Worth saying on the row, because otherwise the price list's numbers read as settings someone
 * chose, and clearing one looks like it would make the model free.
 */
export const isFromPriceList = (model: ModelRow, field: PricingField, rates: RateText): boolean =>
  !isBlank(rates[field]) && !isOverridden(model, field);

const asText = (rate: number | null): string => (rate === null ? "" : String(rate));

/** A deployment's rates as per-million text for the inputs. */
export const ratesOf = (model: ModelRow): RateText =>
  Object.fromEntries(
    Object.entries(readRates({ litellm_params: model.litellm_params, model_info: model.model_info })).map(
      ([field, rate]) => [field, asText(rate)],
    ),
  ) as RateText;

/** The PTU count on this deployment, which forbids a usage rate on top of it. */
export const ptuCountOf = (model: ModelRow): string | undefined => {
  const count = model.model_info?.ptu_count;
  return typeof count === "number" || typeof count === "string" ? String(count) : undefined;
};

/**
 * Which rates the user changed.
 *
 * A table has no separate notion of a touched field, so changed is the useful reading: it is
 * what should be sent, and a rate the user emptied is changed, which is what makes clearing an
 * override actually clear it.
 */
export const changedFields = (current: RateText, original: RateText): ReadonlySet<PricingField> =>
  new Set(PRICING_FIELDS.filter((field) => current[field].trim() !== original[field].trim()));

export const isDirty = (current: RateText, original: RateText): boolean => changedFields(current, original).size > 0;

export const errorsOf = (rates: RateText, ptuCount: string | undefined): Readonly<Partial<Record<PricingField, RateError>>> =>
  Object.fromEntries(
    PRICING_FIELDS.flatMap((field) => {
      const error = validateRate(rates[field], ptuCount);
      return error === null ? [] : [[field, error] as const];
    }),
  );

export const hasErrors = (rates: RateText, ptuCount: string | undefined): boolean =>
  Object.keys(errorsOf(rates, ptuCount)).length > 0;

/**
 * The PATCH body for one row.
 *
 * Only changed rates travel, so saving one row never disturbs a rate the user left alone, and a
 * rate they cleared travels as an explicit null rather than being omitted.
 */
export const buildRowPatch = (
  current: RateText,
  original: RateText,
): { readonly litellm_params: Readonly<Record<string, number | null>> } => ({
  litellm_params: buildPricingPatch(current, { kind: "update", touched: changedFields(current, original) }),
});

/** A rate summarised for a row that cannot be edited. */
export const describeRate = (rates: RateText, field: PricingField): string =>
  isBlank(rates[field]) ? "—" : `$${rates[field]}`;
