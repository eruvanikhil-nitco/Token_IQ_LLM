const SECRET_FIELDS = [
  "api_key",
  "aws_access_key_id",
  "aws_secret_access_key",
  "aws_session_token",
  "vertex_credentials",
  "azure_ad_token",
  "client_secret",
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
