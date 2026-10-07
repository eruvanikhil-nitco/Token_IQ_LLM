ALTER TABLE "LiteLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "provider_credentials" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];
