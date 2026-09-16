import { describe, expect, it } from "vitest";
import { applyMoveKeyUpdate, buildMoveKeyRequests } from "./moveKeyToCredential";

describe("buildMoveKeyRequests", () => {
  it("saves the model's key as a credential and switches the model onto it", () => {
    const { credential, modelUpdate } = buildMoveKeyRequests("m-1", "openai-prod", "openai", {
      model: "gpt-4o",
      api_key: "sk-test-not-real",
    });

    expect(credential).toEqual({
      credential_name: "openai-prod",
      model_id: "m-1",
      credential_info: { custom_llm_provider: "openai" },
    });
    expect(modelUpdate.model_id).toBe("m-1");
    expect(modelUpdate.litellm_params.litellm_credential_name).toBe("openai-prod");
    expect(modelUpdate.litellm_params.api_key).toBeNull();
  });

  it("clears every secret the model carried, not only an api key", () => {
    const { modelUpdate } = buildMoveKeyRequests("m-2", "aws-prod", "bedrock", {
      model: "anthropic.claude-3",
      aws_access_key_id: "AKIATESTNOTREAL",
      aws_secret_access_key: "test-not-real",
      aws_region_name: "us-east-1",
    });

    expect(modelUpdate.litellm_params.aws_access_key_id).toBeNull();
    expect(modelUpdate.litellm_params.aws_secret_access_key).toBeNull();
    expect("aws_region_name" in modelUpdate.litellm_params).toBe(false);
  });

  it("asks for nothing to be cleared when the model carries no secret", () => {
    const { modelUpdate } = buildMoveKeyRequests("m-3", "ollama-local", "ollama", {
      model: "llama3",
      api_base: "http://localhost:11434",
    });

    expect(Object.keys(modelUpdate.litellm_params)).toEqual(["litellm_credential_name"]);
  });
});

describe("applyMoveKeyUpdate", () => {
  it("drops a cleared secret instead of storing its null", () => {
    const merged = applyMoveKeyUpdate(
      { model: "gpt-4o", api_key: "sk-test-not-real", api_base: "https://api.openai.com/v1" },
      { litellm_credential_name: "openai-prod", api_key: null },
    );

    expect(merged).toEqual({
      model: "gpt-4o",
      api_base: "https://api.openai.com/v1",
      litellm_credential_name: "openai-prod",
    });
  });
});
