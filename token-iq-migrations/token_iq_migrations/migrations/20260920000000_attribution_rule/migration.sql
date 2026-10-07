CREATE TABLE "LiteLLM_AttributionRule" (
    "rule_id" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "match_type" TEXT NOT NULL,
    "match_value" TEXT NOT NULL,
    "owner_type" TEXT NOT NULL,
    "owner_id" TEXT NOT NULL,
    "note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "LiteLLM_AttributionRule_pkey" PRIMARY KEY ("rule_id")
);

CREATE UNIQUE INDEX "LiteLLM_AttributionRule_provider_match_type_match_value_key"
    ON "LiteLLM_AttributionRule"("provider", "match_type", "match_value");

CREATE INDEX "LiteLLM_AttributionRule_provider_idx"
    ON "LiteLLM_AttributionRule"("provider");
