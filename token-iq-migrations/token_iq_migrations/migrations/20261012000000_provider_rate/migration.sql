-- What a customer actually pays, as opposed to what a model costs at list: a percentage off list
-- across a provider, or a committed price per million tokens for one model and one meter.
-- Amounts are text so the digits a person read off a contract survive exactly.
-- The period is required because a closed month re-prices with the rate that applied then, and a
-- renegotiation is a new row rather than an edit for the same reason.
-- Create-only: rows are written by an administrator at runtime, so this migration touches no data.
CREATE TABLE IF NOT EXISTS "LiteLLM_ProviderRate" (
    "rate_id"        TEXT NOT NULL,
    "provider"       TEXT NOT NULL,
    "model"          TEXT,
    "field"          TEXT,
    "basis"          TEXT NOT NULL,
    "percent_off"    TEXT,
    "per_million"    TEXT,
    "effective_from" TIMESTAMP(3) NOT NULL,
    "effective_to"   TIMESTAMP(3),
    "source"         TEXT NOT NULL,
    "created_at"     TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"     TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "LiteLLM_ProviderRate_pkey" PRIMARY KEY ("rate_id")
);

CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderRate_provider_effective_from_idx"
    ON "LiteLLM_ProviderRate" ("provider", "effective_from");
