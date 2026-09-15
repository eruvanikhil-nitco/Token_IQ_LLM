import type { CredentialItem } from "../networking";
import { Providers } from "../provider_info_helpers";

interface CredentialFormAdapter {
  getFieldValue: (field: string) => unknown;
  resetFields: () => void;
  setFieldValue: (field: string, value: unknown) => void;
}

/**
 * Reset the credential form when the user switches providers.
 *
 * Why: provider-specific fields (api_base, api_key, organization, ...)
 * share a single Antd Form state across providers. Without this reset,
 * the previous provider's values stick around — most visibly, OpenAI's
 * default `api_base` (https://api.openai.com/v1) carries over when the
 * user switches to Google AI Studio, overriding that provider's own
 * default_value.
 *
 * Strategy: blow away the whole form, then restore the provider-agnostic
 * fields (credential name + the new provider id) so the newly rendered
 * `ProviderSpecificFields` can apply its own defaults from a clean slate.
 *
 * The credential name is preserved because it's a user-supplied label
 * that shouldn't reset just because the admin re-selected a provider.
 */
export function resetCredentialFormOnProviderChange(
  form: CredentialFormAdapter,
  newProvider: Providers,
  setSelectedProvider: (p: Providers) => void,
): void {
  const preservedName = form.getFieldValue("credential_name");
  form.resetFields();
  if (preservedName !== undefined) {
    form.setFieldValue("credential_name", preservedName);
  }
  setSelectedProvider(newProvider);
  form.setFieldValue("custom_llm_provider", newProvider);
}

export const BILLING_PURPOSE = "billing_ingestion";

export const BILLING_PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "bedrock", label: "Amazon Bedrock" },
] as const satisfies ReadonlyArray<{ value: string; label: string }>;

export type BillingProvider = (typeof BILLING_PROVIDERS)[number]["value"];

const BEDROCK_BILLING_FIELDS = ["aws_access_key_id", "aws_secret_access_key", "aws_session_token", "service_name"];

export const BILLING_KEY_FIELDS = ["api_key", ...BEDROCK_BILLING_FIELDS];

const FORM_ONLY_FIELDS = ["credential_name", "custom_llm_provider", "purpose", "billing_provider"];

/**
 * Reset the credential form when the user switches Purpose (Model access <-> Billing access).
 *
 * Why: both purposes reuse the field name `api_key` under the same react-hook-form instance,
 * and RHF keeps a field's value after its Controller unmounts unless `shouldUnregister` is set.
 * Without this reset, a model-serving key typed before switching to Billing access would still
 * be present under `api_key` and get submitted as part of a billing credential (and the reverse).
 *
 * Strategy mirrors `resetCredentialFormOnProviderChange`: blow away the whole form, then restore
 * only the purpose-agnostic credential name, so every purpose-specific field starts from a clean
 * slate under its new Controller.
 */
export function resetCredentialFormOnPurposeChange(
  form: CredentialFormAdapter,
  newPurpose: "model_access" | "billing_access",
): void {
  const preservedName = form.getFieldValue("credential_name");
  form.resetFields();
  if (preservedName !== undefined) {
    form.setFieldValue("credential_name", preservedName);
  }
  form.setFieldValue("purpose", newPurpose);
  if (newPurpose === "billing_access") {
    form.setFieldValue("billing_provider", "openai");
  }
}

export const isBillingCredential = (credential: CredentialItem): boolean =>
  credential.credential_info?.purpose === BILLING_PURPOSE;

export const modelAccessCredentials = (credentials: readonly CredentialItem[]): CredentialItem[] =>
  credentials.filter((credential) => !isBillingCredential(credential));

export const credentialPurposeLabel = (credential: CredentialItem): string =>
  isBillingCredential(credential) ? "Billing access (read-only)" : "Model access";

const filled = (value: unknown): boolean => value !== "" && value !== undefined && value !== null;

export const buildCredentialPayload = (
  values: Record<string, unknown>,
): {
  credential_name: string;
  credential_values: Record<string, unknown>;
  credential_info: Record<string, unknown>;
} => {
  const credentialName = values.credential_name as string;
  if (values.purpose === "billing_access") {
    const provider = values.billing_provider as BillingProvider;
    const keys = provider === "bedrock" ? BEDROCK_BILLING_FIELDS : ["api_key"];
    return {
      credential_name: credentialName,
      credential_values: Object.fromEntries(keys.filter((key) => filled(values[key])).map((key) => [key, values[key]])),
      credential_info: { purpose: BILLING_PURPOSE, provider },
    };
  }
  return {
    credential_name: credentialName,
    credential_values: Object.fromEntries(Object.entries(values).filter(([key]) => !FORM_ONLY_FIELDS.includes(key))),
    credential_info: { custom_llm_provider: values.custom_llm_provider as string },
  };
};
