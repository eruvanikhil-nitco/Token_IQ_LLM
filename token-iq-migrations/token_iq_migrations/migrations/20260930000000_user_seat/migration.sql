CREATE TABLE "LiteLLM_UserSeat" (
    "seat_id" TEXT NOT NULL,
    "tool" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "cadence" TEXT NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'USD',
    "amount" TEXT NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "LiteLLM_UserSeat_pkey" PRIMARY KEY ("seat_id")
);

CREATE UNIQUE INDEX "LiteLLM_UserSeat_tool_user_id_period_start_period_end_key"
    ON "LiteLLM_UserSeat"("tool", "user_id", "period_start", "period_end");

CREATE INDEX "LiteLLM_UserSeat_user_id_period_start_idx"
    ON "LiteLLM_UserSeat"("user_id", "period_start");
