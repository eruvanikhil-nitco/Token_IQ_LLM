-- One rate a customer booked a period at, in one direction, so several currencies can be reported
-- as one figure. The rate is text so the digits a finance team booked survive exactly. Never
-- inverted here: a pair recorded the other way round is a different row, because one divided by a
-- rate is a figure nobody entered.
-- Create-only: rows are written by an administrator at runtime, so this migration touches no data.
CREATE TABLE IF NOT EXISTS "LiteLLM_CurrencyRate" (
    "rate_id"         TEXT NOT NULL,
    "source_currency" TEXT NOT NULL,
    "target_currency" TEXT NOT NULL,
    "rate"            TEXT NOT NULL,
    "effective_from"  TIMESTAMP(3) NOT NULL,
    "effective_to"    TIMESTAMP(3),
    "source"          TEXT NOT NULL,
    "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "LiteLLM_CurrencyRate_pkey" PRIMARY KEY ("rate_id")
);

CREATE INDEX IF NOT EXISTS "LiteLLM_CurrencyRate_pair_effective_from_idx"
    ON "LiteLLM_CurrencyRate" ("source_currency", "target_currency", "effective_from");
