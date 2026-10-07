-- Provider-reported usage and cost, one row per fact at whatever grain the provider offers.
-- fact_key is connector-computed and unique so a re-fetch overwrites rather than duplicates.
-- billed_cost is TEXT so the provider's exact digits survive: prisma-client-py gates its Decimal
-- scalar behind an experimental generator flag, and a float would round away what this table exists
-- to record. Cast with billed_cost::numeric wherever arithmetic is needed.
CREATE TABLE IF NOT EXISTS "LiteLLM_ProviderUsageFact" (
    "id"                  TEXT PRIMARY KEY,
    "fact_key"            TEXT NOT NULL,
    "provider"            TEXT NOT NULL,
    "credential_name"     TEXT NOT NULL,
    "grain"               TEXT NOT NULL,
    "bucket_start"        TIMESTAMP(3) NOT NULL,
    "evidence"            TEXT NOT NULL,
    "provider_request_id" TEXT,
    "provider_api_key_id" TEXT,
    "model"               TEXT,
    "billed_cost"         TEXT NOT NULL DEFAULT '0',
    "billing_currency"    TEXT NOT NULL DEFAULT 'USD',
    "input_tokens"        BIGINT,
    "output_tokens"       BIGINT,
    "cached_input_tokens" BIGINT,
    "cache_write_tokens"  BIGINT,
    "raw"                 JSONB,
    "fetched_at"          TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_fact_key_key"
    ON "LiteLLM_ProviderUsageFact"("fact_key");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_provider_bucket_idx"
    ON "LiteLLM_ProviderUsageFact"("provider", "bucket_start");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_request_idx"
    ON "LiteLLM_ProviderUsageFact"("provider_request_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_credential_bucket_idx"
    ON "LiteLLM_ProviderUsageFact"("credential_name", "bucket_start");
