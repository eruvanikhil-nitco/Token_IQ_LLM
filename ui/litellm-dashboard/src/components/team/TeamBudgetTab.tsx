"use client";

import { Meter, MeterIndicator, MeterTrack } from "@/components/shared/Meter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumberWithCommas } from "@/utils/dataUtils";

interface TeamBudgetTabProps {
  spend: number;
  maxBudget: number | null;
  budgetDuration: string | null;
  budgetResetAt: string | null;
  memberBudget: { max_budget: number; budget_duration: string | null } | null;
}

const utilisationTone = (percent: number) => {
  if (percent >= 90) return "over";
  if (percent >= 70) return "warning";
  return "default";
};

export default function TeamBudgetTab({
  spend,
  maxBudget,
  budgetDuration,
  budgetResetAt,
  memberBudget,
}: TeamBudgetTabProps) {
  const limit = maxBudget !== null && maxBudget > 0 ? maxBudget : null;
  const percentUsed = limit === null ? 0 : Math.round(Math.min((spend / limit) * 100, 100));

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Team budget</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <p className="text-[28px] leading-none font-medium text-foreground">${formatNumberWithCommas(spend, 2)}</p>
          <p className="text-muted-foreground">
            {limit === null ? "No budget limit" : `of $${formatNumberWithCommas(limit, 2)} budget`}
          </p>
          {limit !== null && (
            <Meter value={percentUsed}>
              <MeterTrack>
                <MeterIndicator tone={utilisationTone(percentUsed)} />
              </MeterTrack>
            </Meter>
          )}
          <p>{budgetDuration ? `Resets every ${budgetDuration}` : "Never resets"}</p>
          {budgetResetAt && (
            <p className="text-muted-foreground">Next reset: {new Date(budgetResetAt).toLocaleString()}</p>
          )}
          <p className="text-muted-foreground">
            When the budget is reached, the gateway blocks further requests from this team&apos;s keys.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Budget per member</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {memberBudget ? (
            <p>
              {`$${formatNumberWithCommas(memberBudget.max_budget, 2)} per member, ${
                memberBudget.budget_duration ? `resets every ${memberBudget.budget_duration}` : "never resets"
              }`}
            </p>
          ) : (
            <p className="text-muted-foreground">No per-member budget</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
