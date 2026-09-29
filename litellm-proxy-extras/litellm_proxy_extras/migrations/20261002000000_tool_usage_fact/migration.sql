CREATE TABLE "LiteLLM_ToolUsageFact" (
    "id" TEXT NOT NULL,
    "fact_key" TEXT NOT NULL,
    "tool" TEXT NOT NULL,
    "credential_name" TEXT NOT NULL,
    "person" TEXT NOT NULL,
    "usage_day" TIMESTAMP(3) NOT NULL,
    "cost" TEXT NOT NULL DEFAULT '0',
    "currency" TEXT NOT NULL DEFAULT 'USD',
    "basis" TEXT NOT NULL,
    "model" TEXT,
    "input_tokens" BIGINT,
    "output_tokens" BIGINT,
    "sessions" INTEGER,
    "raw" JSONB,
    "fetched_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "LiteLLM_ToolUsageFact_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "LiteLLM_ToolUsageFact_fact_key_key" ON "LiteLLM_ToolUsageFact"("fact_key");

CREATE INDEX "LiteLLM_ToolUsageFact_tool_usage_day_idx" ON "LiteLLM_ToolUsageFact"("tool", "usage_day");

CREATE INDEX "LiteLLM_ToolUsageFact_person_usage_day_idx" ON "LiteLLM_ToolUsageFact"("person", "usage_day");
