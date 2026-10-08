"use client";

import { Card } from "@/components/ui/card";
import { useUserCost } from "@/app/(dashboard)/hooks/seats/useUserCosts";
import { formatAmount } from "@/app/(dashboard)/(token-iq)/ledger/_components/ledgerDisplay";
import { hasNoSeats, isIncomplete } from "@/app/(dashboard)/(token-iq)/ledger/_components/seatsDisplay";

/** The calendar month, which is the period a subscription is usually billed for. */
const thisMonth = (): { start: string; end: string } => {
  const now = new Date();
  const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const last = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0));
  return { start: first.toISOString().slice(0, 10), end: last.toISOString().slice(0, 10) };
};

interface UserSeatsTabProps {
  userId: string;
}

export default function UserSeatsTab({ userId }: UserSeatsTabProps) {
  const period = thisMonth();
  const { data, isLoading, error } = useUserCost(userId, period.start, period.end, "USD");

  if (isLoading) return <p className="text-sm text-muted-foreground">Working out what this person costs…</p>;
  if (error) return <p className="text-sm text-destructive">Could not read this person&apos;s cost.</p>;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Through the gateway</p>
          <p className="text-2xl font-semibold">{formatAmount(data.gateway, data.currency)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Subscriptions</p>
          <p className="text-2xl font-semibold">{formatAmount(data.seats, data.currency)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">
            Total, {data.period_start} to {data.period_end}
          </p>
          <p className="text-2xl font-semibold">{formatAmount(data.total, data.currency)}</p>
        </Card>
      </div>

      {isIncomplete(data) && <p className="text-sm text-muted-foreground">{data.note}</p>}

      {hasNoSeats(data) ? (
        <p className="text-sm text-muted-foreground">No subscriptions assigned to this person.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full max-w-lg text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Tool</th>
                <th className="py-2">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.seat_lines.map((line, index) => (
                <tr key={`${line.tool}-${index}`} className="border-b last:border-0">
                  <td className="py-2 pr-4">{line.tool}</td>
                  <td className="py-2">{formatAmount(line.amount, line.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
