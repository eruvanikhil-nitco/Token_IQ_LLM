export interface FieldDefault {
  key: string;
  defaultValue?: string;
}

/**
 * Which declared provider defaults still need to be put into form state.
 *
 * The proxy publishes a default_value for some provider fields, OpenAI's api_base among
 * them. Rendering it as placeholder text is not enough: the payload is built from form
 * state, so a default that never lands there is never saved, and the credential is stored
 * without a value the form implied it had.
 */
export const defaultsToSeed = (
  fields: readonly FieldDefault[],
  currentValues: Readonly<Record<string, unknown>>,
): ReadonlyArray<[string, string]> =>
  fields
    .filter((field) => field.defaultValue !== undefined)
    .filter((field) => currentValues[field.key] === undefined || currentValues[field.key] === "")
    .map((field) => [field.key, field.defaultValue as string]);
