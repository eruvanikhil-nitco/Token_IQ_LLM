-- One record per provider fetch attempt, per account. Create-only: the ingestion job appends
-- rows at runtime, so this migration never touches data.
CREATE TABLE IF NOT EXISTS "LiteLLM_ProviderSyncRun" (
    "id"              TEXT PRIMARY KEY,
    "provider"        TEXT NOT NULL,
    "credential_name" TEXT NOT NULL,
    "started_at"      TIMESTAMP(3) NOT NULL,
    "finished_at"     TIMESTAMP(3) NOT NULL,
    "outcome"         TEXT NOT NULL,
    "facts_written"   INTEGER NOT NULL DEFAULT 0,
    "window_start"    TIMESTAMP(3) NOT NULL,
    "window_end"      TIMESTAMP(3) NOT NULL,
    "detail"          TEXT
);

CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderSyncRun_provider_started_idx"
    ON "LiteLLM_ProviderSyncRun"("provider", "started_at");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderSyncRun_credential_started_idx"
    ON "LiteLLM_ProviderSyncRun"("credential_name", "started_at");
