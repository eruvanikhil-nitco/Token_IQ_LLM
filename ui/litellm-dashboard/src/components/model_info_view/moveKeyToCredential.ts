// Every name here must be a declared field on the proxy's CredentialLiteLLMParams, or the move
// deletes the secret instead of storing it; the backend test
// test_every_cleared_param_is_a_field_a_credential_can_hold enforces that against the matching
// CREDENTIAL_CARRYING_PARAMS list, which this must stay in step with.
const SECRET_FIELDS = [
  "api_key",
  "aws_access_key_id",
  "aws_secret_access_key",
  "aws_session_token",
  "vertex_credentials",
  "azure_ad_token",
] as const;

export interface MoveKeyRequests {
  credential: { credential_name: string; model_id: string; credential_info: Record<string, unknown> };
  modelUpdate: { model_id: string; litellm_params: Record<string, unknown> };
}

export const buildMoveKeyRequests = (
  modelId: string,
  credentialName: string,
  provider: string,
  litellmParams: Record<string, unknown>,
): MoveKeyRequests => {
  const cleared = Object.fromEntries(
    SECRET_FIELDS.filter((field) => litellmParams[field] !== undefined && litellmParams[field] !== null).map(
      (field) => [field, null],
    ),
  );
  return {
    credential: {
      credential_name: credentialName,
      model_id: modelId,
      credential_info: { custom_llm_provider: provider },
    },
    modelUpdate: {
      model_id: modelId,
      litellm_params: { litellm_credential_name: credentialName, ...cleared },
    },
  };
};

// A moveKeyRequests.modelUpdate.litellm_params null clears a secret on the server; applying
// the same update to the locally cached params must drop the key rather than store the null.
export const applyMoveKeyUpdate = (
  litellmParams: Record<string, unknown>,
  update: Record<string, unknown>,
): Record<string, unknown> =>
  Object.fromEntries(Object.entries({ ...litellmParams, ...update }).filter(([, value]) => value !== null));

export type MoveKeyResult =
  | { status: "success"; litellmParams: Record<string, unknown> }
  | { status: "credential_failed" }
  | { status: "model_update_failed" };

export interface MoveKeyToCredentialInput {
  modelId: string;
  credentialName: string;
  provider: string;
  litellmParams: Record<string, unknown>;
  createCredential: (credential: MoveKeyRequests["credential"]) => Promise<unknown>;
  updateModel: (update: { litellm_params: Record<string, unknown> }) => Promise<unknown>;
}

// Two calls, two ways to fail partway through: the credential never gets created, or it does
// but the model never picks it up. The caller decides how to tell the admin about each; this
// function only decides which one happened, and never rolls the credential back on the second
// failure, since the typed key is already safely stored under that name either way.
export const moveKeyToCredential = async (input: MoveKeyToCredentialInput): Promise<MoveKeyResult> => {
  const { modelId, credentialName, provider, litellmParams, createCredential, updateModel } = input;
  const { credential, modelUpdate } = buildMoveKeyRequests(modelId, credentialName, provider, litellmParams);

  try {
    await createCredential(credential);
  } catch (error) {
    console.error("Error storing credential:", error);
    return { status: "credential_failed" };
  }

  try {
    await updateModel({ litellm_params: modelUpdate.litellm_params });
  } catch (error) {
    console.error("Error moving model onto stored credential:", error);
    return { status: "model_update_failed" };
  }

  return { status: "success", litellmParams: applyMoveKeyUpdate(litellmParams, modelUpdate.litellm_params) };
};
