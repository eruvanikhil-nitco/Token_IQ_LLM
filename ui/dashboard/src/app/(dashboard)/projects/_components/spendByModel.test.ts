import { describe, expect, it } from "vitest";
import type { DailyData, SpendMetrics } from "@/components/UsagePage/types";
import { spendByModel } from "./spendByModel";

const metrics = (spend: number): SpendMetrics => ({
  spend,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  api_requests: 0,
  successful_requests: 0,
  failed_requests: 0,
  cache_read_input_tokens: 0,
  cache_creation_input_tokens: 0,
});

const day = (date: string, models: Record<string, number>): DailyData => ({
  date,
  metrics: metrics(Object.values(models).reduce((total, spend) => total + spend, 0)),
  breakdown: {
    models: Object.fromEntries(
      Object.entries(models).map(([model, spend]) => [
        model,
        { metrics: metrics(spend), metadata: {}, api_key_breakdown: {} },
      ]),
    ),
    model_groups: {},
    mcp_servers: {},
    providers: {},
    api_keys: {},
    entities: {},
  },
});

describe("spendByModel", () => {
  it("adds up each model's spend across days, biggest spender first", () => {
    const days = [day("2026-09-01", { "gpt-5.2": 1.5, "claude-sonnet-5": 4 }), day("2026-09-02", { "gpt-5.2": 3 })];

    expect(spendByModel(days)).toEqual([
      { model: "gpt-5.2", spend: 4.5 },
      { model: "claude-sonnet-5", spend: 4 },
    ]);
  });

  it("is empty when the project has no recorded days", () => {
    expect(spendByModel([])).toEqual([]);
  });
});
