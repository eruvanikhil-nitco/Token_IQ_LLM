CREATE TABLE "LiteLLM_RecommendationState" (
    "rule_id" TEXT NOT NULL,
    "state" TEXT NOT NULL,
    "decided_by" TEXT,
    "decided_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "note" TEXT,
    CONSTRAINT "LiteLLM_RecommendationState_pkey" PRIMARY KEY ("rule_id")
);
