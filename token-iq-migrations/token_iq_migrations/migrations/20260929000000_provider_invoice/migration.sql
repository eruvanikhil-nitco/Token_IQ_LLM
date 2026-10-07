CREATE TABLE "LiteLLM_ProviderInvoice" (
    "invoice_id" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'USD',
    "total" TEXT NOT NULL,
    "adjustments" JSONB,
    "note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "LiteLLM_ProviderInvoice_pkey" PRIMARY KEY ("invoice_id")
);

CREATE UNIQUE INDEX "LiteLLM_ProviderInvoice_provider_period_start_period_end_key"
    ON "LiteLLM_ProviderInvoice"("provider", "period_start", "period_end");

CREATE INDEX "LiteLLM_ProviderInvoice_provider_period_start_idx"
    ON "LiteLLM_ProviderInvoice"("provider", "period_start");
