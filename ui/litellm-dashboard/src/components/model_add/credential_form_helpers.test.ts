import { describe, expect, it, vi } from "vitest";
import type { CredentialItem } from "../networking";
import { Providers } from "../provider_info_helpers";
import {
  BILLING_PROVIDERS,
  buildCredentialPayload,
  credentialPurposeLabel,
  isBillingCredential,
  modelAccessCredentials,
  resetCredentialFormOnProviderChange,
  resetCredentialFormOnPurposeChange,
} from "./credential_form_helpers";

/**
 * Build a minimal FormInstance stub that records calls. We don't depend
 * on the full Antd API surface — only the three methods the helper uses.
 */
function makeFormStub(initialFields: Record<string, unknown> = {}) {
  const fields: Record<string, unknown> = { ...initialFields };
  const stub = {
    getFieldValue: vi.fn((key: string) => fields[key]),
    setFieldValue: vi.fn((key: string, value: unknown) => {
      fields[key] = value;
    }),
    resetFields: vi.fn(() => {
      Object.keys(fields).forEach((k) => delete fields[k]);
    }),
  };
  return { stub: stub as unknown as Parameters<typeof resetCredentialFormOnProviderChange>[0], fields, calls: stub };
}

describe("resetCredentialFormOnProviderChange", () => {
  it("clears all fields when switching providers", () => {
    // Simulate the OpenAI->Google AI Studio leak: api_base picked up
    // OpenAI's default value and the user typed a custom URL.
    const { stub, fields, calls } = makeFormStub({
      credential_name: "my-prod-key",
      custom_llm_provider: "OpenAI",
      api_base: "https://api.openai.com/v1",
      api_key: "sk-stale-openai-key",
      organization: "org-leak",
    });
    const setSelectedProvider = vi.fn();

    resetCredentialFormOnProviderChange(stub, Providers.Google_AI_Studio, setSelectedProvider);

    expect(calls.resetFields).toHaveBeenCalledTimes(1);
    // Provider-specific fields must be gone so the next render starts
    // from the new provider's default_value, not OpenAI's leftover.
    expect(fields.api_base).toBeUndefined();
    expect(fields.api_key).toBeUndefined();
    expect(fields.organization).toBeUndefined();
  });

  it("preserves credential_name across the switch", () => {
    // credential_name is user-supplied metadata, not provider-specific.
    // The admin shouldn't have to retype it just because they re-picked
    // the provider.
    const { stub, fields } = makeFormStub({
      credential_name: "my-prod-key",
      custom_llm_provider: "OpenAI",
      api_base: "https://api.openai.com/v1",
    });

    resetCredentialFormOnProviderChange(stub, Providers.Google_AI_Studio, vi.fn());

    expect(fields.credential_name).toBe("my-prod-key");
  });

  it("updates custom_llm_provider and selectedProvider state to the new value", () => {
    const { stub, fields } = makeFormStub({ credential_name: "x" });
    const setSelectedProvider = vi.fn();

    resetCredentialFormOnProviderChange(stub, Providers.Google_AI_Studio, setSelectedProvider);

    expect(fields.custom_llm_provider).toBe(Providers.Google_AI_Studio);
    expect(setSelectedProvider).toHaveBeenCalledExactlyOnceWith(Providers.Google_AI_Studio);
  });

  it("does not call setFieldValue('credential_name', undefined) when the name was unset", () => {
    // Edge case: brand-new modal with no name typed yet. We shouldn't
    // explicitly write `undefined` back into the form (Antd treats that
    // as a touched empty field, triggering the "required" validation
    // prematurely).
    const { stub, calls } = makeFormStub({});

    resetCredentialFormOnProviderChange(stub, Providers.Anthropic, vi.fn());

    const credentialNameCalls = calls.setFieldValue.mock.calls.filter(([key]) => key === "credential_name");
    expect(credentialNameCalls).toHaveLength(0);
  });
});

describe("credential purpose", () => {
  const billing: CredentialItem = {
    credential_name: "anthropic-costs",
    credential_values: {},
    credential_info: { purpose: "billing_ingestion", provider: "anthropic" },
  };
  const modelAccess: CredentialItem = {
    credential_name: "openai-models",
    credential_values: { api_key: "sk-****" },
    credential_info: { custom_llm_provider: "OpenAI" },
  };

  it("tells billing credentials from model access credentials", () => {
    expect(isBillingCredential(billing)).toBe(true);
    expect(isBillingCredential(modelAccess)).toBe(false);
  });

  it("keeps billing credentials out of the lists used to serve models", () => {
    expect(modelAccessCredentials([billing, modelAccess]).map((c) => c.credential_name)).toEqual(["openai-models"]);
  });

  it("labels each purpose in plain words", () => {
    expect(credentialPurposeLabel(billing)).toBe("Billing access (read-only)");
    expect(credentialPurposeLabel(modelAccess)).toBe("Model access");
  });

  it("offers exactly the providers this build can read bills from", () => {
    expect(BILLING_PROVIDERS.map((p) => p.value)).toEqual(["openai", "anthropic", "openrouter", "bedrock"]);
  });

  it("builds a billing credential with the marker the ingestion job looks for", () => {
    expect(
      buildCredentialPayload({
        credential_name: "anthropic-costs",
        purpose: "billing_access",
        billing_provider: "anthropic",
        api_key: "sk-ant-admin01-test-not-real",
      }),
    ).toEqual({
      credential_name: "anthropic-costs",
      credential_values: { api_key: "sk-ant-admin01-test-not-real" },
      credential_info: { purpose: "billing_ingestion", provider: "anthropic" },
    });
  });

  it("keeps only the Bedrock values that were filled in", () => {
    expect(
      buildCredentialPayload({
        credential_name: "aws-costs",
        purpose: "billing_access",
        billing_provider: "bedrock",
        aws_access_key_id: "AKIATESTNOTREAL",
        aws_secret_access_key: "test-not-real",
        aws_session_token: "",
      }).credential_values,
    ).toEqual({ aws_access_key_id: "AKIATESTNOTREAL", aws_secret_access_key: "test-not-real" });
  });

  it("builds a model access credential exactly as before", () => {
    expect(
      buildCredentialPayload({
        credential_name: "openai-models",
        purpose: "model_access",
        custom_llm_provider: "OpenAI",
        api_key: "sk-test-not-real",
        api_base: "https://api.openai.com/v1",
      }),
    ).toEqual({
      credential_name: "openai-models",
      credential_values: { api_key: "sk-test-not-real", api_base: "https://api.openai.com/v1" },
      credential_info: { custom_llm_provider: "OpenAI" },
    });
  });

  it("treats a form with no purpose as model access, so existing callers keep working", () => {
    expect(
      buildCredentialPayload({ credential_name: "x", custom_llm_provider: "OpenAI", api_key: "k" }).credential_info,
    ).toEqual({ custom_llm_provider: "OpenAI" });
  });
});

describe("resetCredentialFormOnPurposeChange", () => {
  it("clears every field except credential_name, so a model-access key can't survive under Billing access", () => {
    const { stub, fields } = makeFormStub({
      credential_name: "openai-costs",
      custom_llm_provider: "OpenAI",
      api_key: "sk-model-serving-key",
      api_base: "https://api.openai.com/v1",
    });

    resetCredentialFormOnPurposeChange(stub, "billing_access");

    expect(fields.credential_name).toBe("openai-costs");
    expect(fields.custom_llm_provider).toBeUndefined();
    expect(fields.api_key).toBeUndefined();
    expect(fields.api_base).toBeUndefined();
  });

  it("clears a billing key so it can't survive under Model access", () => {
    const { stub, fields } = makeFormStub({
      credential_name: "openai-costs",
      purpose: "billing_access",
      billing_provider: "openai",
      api_key: "sk-admin-test-not-real",
    });

    resetCredentialFormOnPurposeChange(stub, "model_access");

    expect(fields.api_key).toBeUndefined();
    expect(fields.billing_provider).toBeUndefined();
  });

  it("writes the new purpose into the form", () => {
    const { stub, fields } = makeFormStub({ credential_name: "x" });

    resetCredentialFormOnPurposeChange(stub, "billing_access");

    expect(fields.purpose).toBe("billing_access");
  });

  it("defaults the billing provider to openai when switching to Billing access", () => {
    const { stub, fields } = makeFormStub({ credential_name: "x" });

    resetCredentialFormOnPurposeChange(stub, "billing_access");

    expect(fields.billing_provider).toBe("openai");
  });

  it("does not invent a billing provider when switching to Model access", () => {
    const { stub, fields } = makeFormStub({ credential_name: "x" });

    resetCredentialFormOnPurposeChange(stub, "model_access");

    expect(fields.billing_provider).toBeUndefined();
  });
});
