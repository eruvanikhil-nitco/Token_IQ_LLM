"use client";

import * as React from "react";
import {
  BACKEND_PARAM,
  EDIT_FORM_FIELD,
  PER_SECOND_PARAM,
  PRICING_FIELDS,
  type PricingField,
} from "@/lib/pricing/modelPricing";

/** Which set of rates a deployment is priced on. The two are alternatives, never both. */
export type PricingMode = "per_token" | "per_second";

/** A rate slot, including the per-second alternative that replaces all four per-token ones. */
export type RateSlot = PricingField | "perSecond";

export interface RateFieldProps {
  readonly slot: RateSlot;
  /** The host form's own name for this rate. */
  readonly name: string;
  readonly label: string;
  readonly help?: string;
  readonly placeholder?: string;
}

/**
 * How a host renders one rate.
 *
 * Each form supplies its own, because their submit mechanics are not interchangeable: Add Model
 * builds its payload from the fields registered through `MountedFormField`, so a rate rendered
 * any other way there would never be submitted at all, while the edit form drives its payload
 * from which fields the user touched. Sharing the copy and the ordering is worth doing; forcing
 * one wrapper on both would break one of them.
 */
export type RenderRateField = (props: RateFieldProps) => React.ReactNode;

export type PricingFieldNames = Readonly<Record<RateSlot, string>>;

/** Add Model names its fields after the wire format, so the backend names serve directly. */
export const ADD_MODEL_PRICING_NAMES: PricingFieldNames = {
  ...BACKEND_PARAM,
  perSecond: PER_SECOND_PARAM,
} as const;

/** The edit form has no per-second option, so that slot never renders and needs no name. */
export const EDIT_FORM_PRICING_NAMES: PricingFieldNames = {
  ...EDIT_FORM_FIELD,
  perSecond: PER_SECOND_PARAM,
} as const;

const CACHE_FALLBACK_PLACEHOLDER = "Defaults to Input Cost if blank";

/**
 * The label and help text for each rate, in the order they should appear.
 *
 * Both forms wrote this copy out separately and had already drifted. Keeping it here means the
 * cache-read and cache-write fields explain their fallback the same way wherever they appear,
 * which matters because that fallback is the least obvious thing about pricing a model.
 */
const RATE_COPY: Readonly<Record<PricingField, Omit<RateFieldProps, "slot" | "name">>> = {
  input: { label: "Input Cost (per 1M tokens)", placeholder: "Enter input cost" },
  output: { label: "Output Cost (per 1M tokens)", placeholder: "Enter output cost" },
  cacheRead: {
    label: "Cache Read Cost (per 1M tokens)",
    help: "If left blank, defaults to Input Cost.",
    placeholder: CACHE_FALLBACK_PLACEHOLDER,
  },
  cacheWrite: {
    label: "Cache Write Cost (per 1M tokens)",
    help: "If left blank, defaults to Input Cost.",
    placeholder: CACHE_FALLBACK_PLACEHOLDER,
  },
};

const PER_SECOND_COPY: Omit<RateFieldProps, "slot" | "name"> = { label: "Cost Per Second" };

/** The rate slots a given pricing mode asks for, in display order. */
export const slotsFor = (mode: PricingMode): readonly RateSlot[] =>
  mode === "per_second" ? ["perSecond"] : PRICING_FIELDS;

export const copyFor = (slot: RateSlot): Omit<RateFieldProps, "slot" | "name"> =>
  slot === "perSecond" ? PER_SECOND_COPY : RATE_COPY[slot];

export interface PricingFieldsProps {
  readonly mode: PricingMode;
  readonly names: PricingFieldNames;
  readonly renderField: RenderRateField;
  /**
   * Render only these rates, still in the canonical order.
   *
   * The edit form puts its PTU fields between the usage rates and the cache rates, so it asks
   * for them in two calls rather than one. Ordering stays this component's job either way.
   */
  readonly slots?: readonly RateSlot[];
}

/**
 * The custom pricing rates, wherever they are edited.
 *
 * Owns which rates a mode asks for, their order, and what each one is called; the host owns how
 * a field is wired to its form. The switch that turns custom pricing on and the per-token /
 * per-second choice stay with the host too, because only the create form has them.
 */
const PricingFields: React.FC<PricingFieldsProps> = ({ mode, names, renderField, slots }) => {
  const wanted = slotsFor(mode).filter((slot) => slots === undefined || slots.includes(slot));

  return (
    <>
      {wanted.map((slot) => (
        <React.Fragment key={slot}>{renderField({ slot, name: names[slot], ...copyFor(slot) })}</React.Fragment>
      ))}
    </>
  );
};

export default PricingFields;
