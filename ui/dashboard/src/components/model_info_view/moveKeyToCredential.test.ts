import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/http/client";
import { applyMoveKeyUpdate, buildMoveKeyRequests, moveKeyToCredential } from "./moveKeyToCredential";

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

describe("moveKeyToCredential", () => {
  const baseInput = {
    modelId: "m-1",
    credentialName: "openai-prod",
    provider: "openai",
    litellmParams: { model: "gpt-4o", api_key: "sk-test-not-real" },
  };

  it("reports success and the cleared params once both calls succeed", async () => {
    const createCredential = vi.fn().mockResolvedValue({});
    const updateModel = vi.fn().mockResolvedValue({});

    const result = await moveKeyToCredential({ ...baseInput, createCredential, updateModel });

    expect(createCredential).toHaveBeenCalledWith({
      credential_name: "openai-prod",
      model_id: "m-1",
      credential_info: { custom_llm_provider: "openai" },
    });
    expect(updateModel).toHaveBeenCalledWith({
      litellm_params: { litellm_credential_name: "openai-prod", api_key: null },
    });
    expect(result).toEqual({
      status: "success",
      litellmParams: { model: "gpt-4o", litellm_credential_name: "openai-prod" },
    });
  });

  it("reports credential_failed and never attempts the model update when the credential save rejects", async () => {
    const createCredential = vi.fn().mockRejectedValue(new Error("network error"));
    const updateModel = vi.fn().mockResolvedValue({});

    const result = await moveKeyToCredential({ ...baseInput, createCredential, updateModel });

    expect(result).toEqual({ status: "credential_failed" });
    expect(updateModel).not.toHaveBeenCalled();
  });

  it("finishes the move when an earlier attempt already stored the credential of that name", async () => {
    const createCredential = vi
      .fn()
      .mockRejectedValue(new ApiError("A credential named openai-prod already exists.", 409, {}));
    const updateModel = vi.fn().mockResolvedValue({});

    const result = await moveKeyToCredential({ ...baseInput, createCredential, updateModel });

    expect(updateModel).toHaveBeenCalledWith({
      litellm_params: { litellm_credential_name: "openai-prod", api_key: null },
    });
    expect(result).toEqual({
      status: "success",
      litellmParams: { model: "gpt-4o", litellm_credential_name: "openai-prod" },
    });
  });

  it("still reports credential_failed when the credential is refused for a reason other than its name", async () => {
    const createCredential = vi.fn().mockRejectedValue(new ApiError("Only a proxy admin may store this", 403, {}));
    const updateModel = vi.fn().mockResolvedValue({});

    const result = await moveKeyToCredential({ ...baseInput, createCredential, updateModel });

    expect(result).toEqual({ status: "credential_failed" });
    expect(updateModel).not.toHaveBeenCalled();
  });

  it("reports model_update_failed when the credential saved but the model update rejects", async () => {
    const createCredential = vi.fn().mockResolvedValue({});
    const updateModel = vi.fn().mockRejectedValue(new Error("billing credential"));

    const result = await moveKeyToCredential({ ...baseInput, createCredential, updateModel });

    expect(createCredential).toHaveBeenCalled();
    expect(result).toEqual({ status: "model_update_failed" });
  });
});
