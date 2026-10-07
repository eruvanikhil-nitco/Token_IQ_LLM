"use client";

import { Card } from "@/components/ui/card";
import { useComparison } from "@/app/(dashboard)/hooks/combined/useComparison";
import { STATUS_EXPLANATION, STATUS_LABEL, formatAmount, ownerOf } from "./comparisonDisplay";

interface SourceComparisonViewProps {
  days: number;
}

export default function SourceComparisonView({ days }: SourceComparisonViewProps) {
  const { data, isLoading, error } = useComparison(days);

  if (isLoading) return <p className="text-sm text-muted-foreground">Comparing the bills…</p>;
  if (error) return <p className="text-sm text-destructive">Could not read the comparison.</p>;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-4">
      {/* The meaning comes before the figures. A reader who meets three money totals first
          has already decided what they add up to by the time any footnote reaches them. */}
      <p className="text-sm text-muted-foreground">
        What each provider invoiced, against what this gateway recorded, for the same days. <strong>These
        figures are never added together:</strong> the provider says how much was spent and the gateway says
        who spent it, so the same request appears in both. The difference is spend that did not go through
        the gateway, and the last column says who owns it.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Providers billed</p>
          <p className="text-2xl font-semibold">{formatAmount(data.total_provider)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Gateway recorded</p>
          <p className="text-2xl font-semibold">{formatAmount(data.total_gateway)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Bypassed the gateway</p>
          <p className="text-2xl font-semibold">{formatAmount(data.total_gap)}</p>
        </Card>
      </div>

      {data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No provider has reported anything in this window.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Day</th>
                <th className="py-2 pr-4">Provider</th>
                <th className="py-2 pr-4">Account</th>
                <th className="py-2 pr-4">Provider billed</th>
                <th className="py-2 pr-4">Gateway recorded</th>
                <th className="py-2 pr-4">Difference</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2">Owner</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={`${row.day}-${row.provider}-${row.credential_name}`} className="border-b last:border-0">
                  <td className="py-2 pr-4 whitespace-nowrap">{row.day}</td>
                  <td className="py-2 pr-4">{row.display_name}</td>
                  <td className="py-2 pr-4">{row.credential_name}</td>
                  <td className="py-2 pr-4">{formatAmount(row.provider_cost)}</td>
                  <td className="py-2 pr-4">{formatAmount(row.gateway_cost)}</td>
                  <td className="py-2 pr-4">{formatAmount(row.gap)}</td>
                  <td className="py-2 pr-4" title={STATUS_EXPLANATION[row.status]}>
                    {STATUS_LABEL[row.status]}
                  </td>
                  <td className="py-2">{ownerOf(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
