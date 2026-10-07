/**
 * Per-model rate and timeout limits, as the Model Limits table edits them.
 *
 * These live in `litellm_params` and the backend has always supported them, but the only way
 * to set one was to hand-write JSON into an advanced settings box where `rpm` appeared as
 * placeholder text. A capability nobody can reach is not a capability.
 *
 * Limits are operational rather than create-time: you set them when a team starts hammering a
 * model, not while first adding it. That is why they belong on a table of every model rather
 * than in the Add Model form.
 */

/** What a deployment carries, as far as this screen cares. */
export interface ModelRow {
  readonly model_name: string;
  readonly model_info?: { readonly id?: string; readonly db_model?: boolean } | null;
  readonly litellm_params?: Record<string, unknown> | null;
}

export interface Limits {
  readonly tpm: string;
  readonly rpm: string;
  readonly timeout: string;
}

export const EMPTY_LIMITS: Limits = { tpm: "", rpm: "", timeout: "" };

/** The field names as they are stored, so the form and the payload cannot drift. */
export const LIMIT_FIELDS = ["tpm", "rpm", "timeout"] as const;
export type LimitField = (typeof LIMIT_FIELDS)[number];

const asText = (value: unknown): string => (value === null || value === undefined || value === "" ? "" : String(value));

/** A model's current limits, as strings for the inputs. */
export const limitsOf = (model: ModelRow): Limits => ({
  tpm: asText(model.litellm_params?.tpm),
  rpm: asText(model.litellm_params?.rpm),
  timeout: asText(model.litellm_params?.timeout),
});

/**
 * Whether this model can be edited here.
 *
 * Only deployments stored in the database can be patched; ones declared in the config file are
 * read-only through the API, so offering an input for them would promise something the save
 * cannot deliver.
 */
export const isEditable = (model: ModelRow): boolean => model.model_info?.db_model === true;

export const modelId = (model: ModelRow): string => model.model_info?.id ?? "";

/** Whether a field holds something that can be sent, or is blank, or is nonsense. */
export const validate = (field: LimitField, raw: string): { readonly ok: boolean; readonly error?: string } => {
  const value = raw.trim();
  if (value === "") return { ok: true };

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return { ok: false, error: "Must be a number" };
  if (parsed <= 0) return { ok: false, error: "Must be greater than zero" };
  if (field !== "timeout" && !Number.isInteger(parsed)) return { ok: false, error: "Must be a whole number" };
  return { ok: true };
};

export const hasErrors = (limits: Limits): boolean => LIMIT_FIELDS.some((field) => !validate(field, limits[field]).ok);

/** Whether anything actually changed, so an unchanged row does not trigger a save. */
export const isDirty = (current: Limits, original: Limits): boolean =>
  LIMIT_FIELDS.some((field) => current[field].trim() !== original[field].trim());

/**
 * The PATCH body for one model's limits.
 *
 * A cleared field is sent as null rather than omitted: omitting it means "leave as is" under
 * PATCH semantics, so clearing a limit in the UI would silently do nothing.
 */
export const buildPatch = (limits: Limits): { readonly litellm_params: Record<string, number | null> } => ({
  litellm_params: Object.fromEntries(
    LIMIT_FIELDS.map((field) => {
      const value = limits[field].trim();
      return [field, value === "" ? null : Number(value)];
    }),
  ),
});

/** A model's limits summarised for a read-only row. */
export const describe = (limits: Limits): string => {
  const parts = LIMIT_FIELDS.filter((field) => limits[field].trim() !== "").map(
    (field) => `${field} ${limits[field].trim()}`,
  );
  return parts.length === 0 ? "no limits set" : parts.join(", ");
};
