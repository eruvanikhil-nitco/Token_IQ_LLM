"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useReconciliation } from "@/app/(dashboard)/hooks/ledger/useReconciliation";
import { ADJUSTMENT_LABEL, OUTCOME_LABEL, formatAmount, hasRemainder, remainderDirection } from "./ledgerDisplay";

interface BillReconciliationViewProps {
  /** Takes the reader to the form that enters a bill.
   *
   * The outcome "No bill entered" used to be the whole message, while the form that fixes it sat
   * in a different tab. A dead end that names no way out is worse than an error. */
  onEnterBill?: () => void;
  provider: string;
  periodStart: string;
  periodEnd: string;
}

export default function BillReconciliationView({
  provider,
  periodStart,
  periodEnd,
  onEnterBill,
}: BillReconciliationViewProps) {
  const { data, isLoading, error } = useReconciliation(provider, periodStart, periodEnd);

  if (isLoading) return <p className="text-sm text-muted-foreground">Comparing the bill against the ledger…</p>;
  if (error) return <p className="text-sm text-destructive">Could not read the reconciliation.</p>;
  if (!data) return null;

  const direction = remainderDirection(data.unexplained);

  return (
    <div className="flex flex-col gap-4">
      {/* Meaning first, and the same rule as Source Comparison: the bill and the ledger are two
          accounts of the same spend, so their sum means nothing. Only the gap between them does. */}
      <p className="text-sm text-muted-foreground">
        What this provider invoiced for the period, against what the ledger recorded for it.
        <strong> These two are never added together:</strong> they are two accounts of the same spend, and only
        the difference between them is worth reading. Credits, tax and commitments explain part of it; whatever
        is left is unexplained and needs a person.
      </p>
      <Card className="p-4">
        <p className="text-sm text-muted-foreground">Outcome</p>
        <p className="text-xl font-semibold">{OUTCOME_LABEL[data.outcome]}</p>
        <p className="pt-1 text-sm text-muted-foreground">{data.note}</p>
        {data.outcome === "no_invoice" && onEnterBill !== undefined && (
          <Button className="mt-3" onClick={onEnterBill}>
            Enter this bill
          </Button>
        )}
      </Card>

      {data.outcome !== "no_invoice" && data.outcome !== "currency_mismatch" && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">The bill says</p>
              <p className="text-2xl font-semibold">{formatAmount(data.invoice_total, data.currency)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">The ledger says</p>
              <p className="text-2xl font-semibold">{formatAmount(data.ledger_total, data.currency)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Unexplained</p>
              <p className="text-2xl font-semibold">{formatAmount(data.unexplained, data.currency)}</p>
              {direction === "over" && (
                <p className="pt-1 text-sm text-muted-foreground">
                  The bill is larger than the ledger by this much, and nothing on it says why.
                </p>
              )}
              {direction === "under" && (
                <p className="pt-1 text-sm text-muted-foreground">
                  The ledger is larger than the bill by this much, which can mean usage the provider has not billed yet.
                </p>
              )}
            </Card>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">What accounts for the difference</p>
            {data.explained.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nothing on the bill explains any of the difference. Credits, discounts, tax and commitments are entered
                on the Invoices tab.
              </p>
            ) : (
              <table className="w-full max-w-lg text-sm">
                <tbody>
                  {data.explained.map((adjustment, index) => (
                    <tr key={`${adjustment.kind}-${index}`} className="border-b last:border-0">
                      <td className="py-2 pr-4">{ADJUSTMENT_LABEL[adjustment.kind]}</td>
                      <td className="py-2 pr-4">{formatAmount(adjustment.amount, data.currency)}</td>
                      <td className="py-2 text-muted-foreground">{adjustment.note ?? ""}</td>
                    </tr>
                  ))}
                  <tr>
                    <td className="py-2 pr-4 font-medium">Accounted for</td>
                    <td className="py-2 pr-4 font-medium">{formatAmount(data.explained_total, data.currency)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            )}
          </div>

          {!hasRemainder(data.unexplained) && (
            <p className="text-sm text-muted-foreground">
              Nothing is left over. Every part of the difference between the bill and the ledger is accounted for.
            </p>
          )}
        </>
      )}
    </div>
  );
}
