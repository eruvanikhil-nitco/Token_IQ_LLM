import type { DailyData } from "@/components/UsagePage/types";

export type ModelSpend = {
  model: string;
  spend: number;
};

export const spendByModel = (days: readonly DailyData[]): ModelSpend[] => {
  const totals = days
    .flatMap((day) => Object.entries(day.breakdown.models))
    .reduce(
      (sums, [model, entry]) => sums.set(model, (sums.get(model) ?? 0) + entry.metrics.spend),
      new Map<string, number>(),
    );
  return Array.from(totals, ([model, spend]) => ({ model, spend })).sort((a, b) => b.spend - a.spend);
};
