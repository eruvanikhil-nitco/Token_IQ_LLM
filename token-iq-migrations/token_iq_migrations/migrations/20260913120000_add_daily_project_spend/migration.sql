-- CreateTable
CREATE TABLE "LiteLLM_DailyProjectSpend" (
    "id" TEXT NOT NULL,
    "project_id" TEXT,
    "date" TEXT NOT NULL,
    "api_key" TEXT NOT NULL,
    "model" TEXT,
    "model_group" TEXT,
    "custom_llm_provider" TEXT,
    "mcp_namespaced_tool_name" TEXT,
    "endpoint" TEXT,
    "prompt_tokens" BIGINT NOT NULL DEFAULT 0,
    "completion_tokens" BIGINT NOT NULL DEFAULT 0,
    "cache_read_input_tokens" BIGINT NOT NULL DEFAULT 0,
    "cache_creation_input_tokens" BIGINT NOT NULL DEFAULT 0,
    "compression_saved_tokens" BIGINT NOT NULL DEFAULT 0,
    "compression_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "prompt_caching_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "gateway_injected_caching_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "autorouter_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "api_requests" BIGINT NOT NULL DEFAULT 0,
    "successful_requests" BIGINT NOT NULL DEFAULT 0,
    "failed_requests" BIGINT NOT NULL DEFAULT 0,
    "ptu_flat_cost" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "LiteLLM_DailyProjectSpend_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "LiteLLM_DailyProjectSpend_date_idx" ON "LiteLLM_DailyProjectSpend"("date");

-- CreateIndex
CREATE INDEX "LiteLLM_DailyProjectSpend_project_id_date_idx" ON "LiteLLM_DailyProjectSpend"("project_id", "date");

-- CreateIndex
CREATE INDEX "LiteLLM_DailyProjectSpend_api_key_idx" ON "LiteLLM_DailyProjectSpend"("api_key");

-- CreateIndex
CREATE INDEX "LiteLLM_DailyProjectSpend_model_idx" ON "LiteLLM_DailyProjectSpend"("model");

-- CreateIndex
CREATE INDEX "LiteLLM_DailyProjectSpend_mcp_namespaced_tool_name_idx" ON "LiteLLM_DailyProjectSpend"("mcp_namespaced_tool_name");

-- CreateIndex
CREATE INDEX "LiteLLM_DailyProjectSpend_endpoint_idx" ON "LiteLLM_DailyProjectSpend"("endpoint");

-- CreateIndex
CREATE UNIQUE INDEX "LiteLLM_DailyProjectSpend_project_id_date_api_key_model_cus_key" ON "LiteLLM_DailyProjectSpend"("project_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");

