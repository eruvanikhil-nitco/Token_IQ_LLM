"use client";

import { Card } from "@/components/ui/card";
import { useUnallocated } from "@/app/(dashboard)/hooks/attribution/useUnallocated";
import { STATE_EXPLANATION, STATE_LABEL, formatAmount } from "./gapDisplay";

interface UnmatchedPanelProps {
  provider: string;
  days: number;
}

export default function UnmatchedPanel({ provider, days }: UnmatchedPanelProps) {
  const { data, isLoading, error } = useUnallocated(provider, days);

  if (isLoading) return <p className="text-sm text-muted-foreground">Comparing the provider&apos;s bill…</p>;
  if (error) return <p className="text-sm text-destructive">Could not read this provider&apos;s spend.</p>;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Nobody owns this</p>
          <p className="text-2xl font-semibold">{formatAmount(data.total_unallocated)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Assigned by a rule</p>
          <p className="text-2xl font-semibold">{formatAmount(data.total_owned)}</p>
        </Card>
      </div>

      <p className="text-sm text-muted-foreground">
        For each day the provider billed for, what it charged against what the gateway recorded. The difference is spend
        that reached the provider without passing through the gateway.
      </p>

      {data.lines.length === 0 ? (
        <p className="text-sm text-muted-foreground">This provider has reported nothing in the last {days} days.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Day</th>
                <th className="py-2 pr-4">Account</th>
                <th className="py-2 pr-4">Provider billed</th>
                <th className="py-2 pr-4">Gateway recorded</th>
                <th className="py-2 pr-4">Difference</th>
                <th className="py-2 pr-4">State</th>
                <th className="py-2">Owner</th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line) => (
                <tr key={`${line.day}-${line.credential_name}`} className="border-b last:border-0">
                  <td className="py-2 pr-4 whitespace-nowrap">{line.day}</td>
                  <td className="py-2 pr-4">{line.credential_name}</td>
                  <td className="py-2 pr-4">{formatAmount(line.provider_cost)}</td>
                  <td className="py-2 pr-4">{formatAmount(line.gateway_cost)}</td>
                  <td className="py-2 pr-4">{formatAmount(line.gap)}</td>
                  <td className="py-2 pr-4" title={STATE_EXPLANATION[line.state]}>
                    {STATE_LABEL[line.state]}
                  </td>
                  <td className="py-2">{line.owner_id === null ? "—" : `${line.owner_type}: ${line.owner_id}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
