-- One external ID per connection, minted once and never regenerated. The customer writes this
-- exact value into their role's trust policy, so a second value for the same connection locks
-- them out. The primary key is the connection, which is what makes the mint idempotent.
-- Create-only: rows are written by the connect flow at runtime, so this migration touches no data.
CREATE TABLE IF NOT EXISTS "LiteLLM_ProviderConnectionExternalId" (
    "provider"        TEXT NOT NULL,
    "credential_name" TEXT NOT NULL,
    "external_id"     TEXT NOT NULL,
    "issued_at"       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "LiteLLM_ProviderConnectionExternalId_pkey"
        PRIMARY KEY ("provider", "credential_name")
);
