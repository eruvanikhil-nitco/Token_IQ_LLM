"use client";

import { Card } from "@/components/ui/card";
import { useLedger } from "@/app/(dashboard)/hooks/ledger/useLedger";
import { EVIDENCE_LABEL, formatAmount } from "./ledgerDisplay";

interface CostLedgerViewProps {
  provider: string;
  periodStart: string;
  periodEnd: string;
}

export default function CostLedgerView({ provider, periodStart, periodEnd }: CostLedgerViewProps) {
  const { data, isLoading, error } = useLedger(provider, periodStart, periodEnd);

  if (isLoading) return <p className="text-sm text-muted-foreground">Reading the ledger…</p>;
  if (error) return <p className="text-sm text-destructive">Could not read the ledger.</p>;
  if (!data) return null;

  const totals = Object.entries(data.totals_by_currency);

  return (
    <div className="flex flex-col gap-4">
      {totals.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing recorded for this provider in this period.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {totals.map(([currency, amount]) => (
            <Card key={currency} className="p-4">
              <p className="text-sm text-muted-foreground">Ledger total, {currency}</p>
              <p className="text-2xl font-semibold">{formatAmount(amount, currency)}</p>
            </Card>
          ))}
        </div>
      )}

      <p className="text-sm text-muted-foreground">
        Every cost line the provider reported, with how it was arrived at and who owns the account it came from. The
        gateway&apos;s own records are not listed here: the two describe the same money, so showing both would count it
        twice.
      </p>

      {data.lines.length === 0 ? null : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Day</th>
                <th className="py-2 pr-4">Provider</th>
                <th className="py-2 pr-4">Account</th>
                <th className="py-2 pr-4">Model</th>
                <th className="py-2 pr-4">Amount</th>
                <th className="py-2 pr-4">How we know</th>
                <th className="py-2">Owner</th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line, index) => (
                <tr key={`${line.day}-${line.credential_name}-${index}`} className="border-b last:border-0">
                  <td className="py-2 pr-4 whitespace-nowrap">{line.day}</td>
                  <td className="py-2 pr-4">{line.display_name}</td>
                  <td className="py-2 pr-4">{line.credential_name}</td>
                  <td className="py-2 pr-4">{line.model ?? "—"}</td>
                  <td className="py-2 pr-4">{formatAmount(line.amount, line.currency)}</td>
                  <td className="py-2 pr-4" title={EVIDENCE_LABEL[line.evidence]}>
                    {line.evidence}
                  </td>
                  <td className="py-2">{line.owner_id === null ? "—" : `${line.owner_type}: ${line.owner_id}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.next_cursor !== null && (
        <p className="text-sm text-muted-foreground">
          Showing the newest {data.lines.length} lines. Narrow the period to see the rest.
        </p>
      )}
    </div>
  );
}
