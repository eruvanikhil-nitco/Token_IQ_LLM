"use client";

import { Button } from "@/components/ui/button";
import { useDeleteInvoice, useInvoices } from "@/app/(dashboard)/hooks/ledger/useInvoices";
import {
  enterBillHref,
  monthOfPeriod,
} from "@/app/(dashboard)/(token-iq)/data-sources/_components/invoiceSubmit";
import { ADJUSTMENT_LABEL, formatAmount } from "./ledgerDisplay";

interface InvoicesViewProps {
  /** What the page is reconciling, so the link opens the dialog on that bill. */
  provider: string;
  periodStart: string;
}

/**
 * The bills entered, listed where they are compared against the ledger.
 *
 * Entering one happens on Data Sources > Uploads, which is where the blueprint puts it and what
 * Invoice Reconciliation's own "not here" line says. This tab had a second form for the same
 * endpoint; two forms writing one table drift, and the one here knew nothing about the months a
 * provider has billed for without a bill, which is the part worth acting on.
 *
 * The list stays, and so does removing a bill: this is the screen where a wrong figure shows up,
 * as a difference the ledger cannot explain.
 */
export default function InvoicesView({ provider, periodStart }: InvoicesViewProps) {
  const { data, isLoading, error } = useInvoices();
  const remove = useDeleteInvoice();

  // The same reading of a period the reconciliation link uses, so a period that is not a date
  // asks the dialog for no month rather than for a month nobody can read.
  const month = monthOfPeriod(periodStart);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-3xl text-sm text-muted-foreground">
          Every bill an administrator has entered, which is what reconciliation compares the ledger against. Almost no
          provider publishes invoices through an API, so each one is read off the real bill and typed in on Data
          Sources, where the months that have billed without one are listed too.
        </p>
        <Button nativeButton={false} render={<a href={enterBillHref({ provider, month })} />}>
          Enter a bill on Data Sources
        </Button>
      </div>

      {remove.isError && (
        <p className="text-sm text-destructive">Could not remove that bill, so it is still being compared.</p>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Reading the bills…</p>}
      {error && <p className="text-sm text-destructive">Could not read the bills.</p>}

      {!isLoading && (data?.invoices.length ?? 0) === 0 && (
        <p className="text-sm text-muted-foreground">
          No bills entered yet, so nothing can be reconciled against the ledger. Enter the first one on Data Sources,
          as the provider wrote it.
        </p>
      )}

      {(data?.invoices.length ?? 0) > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Provider</th>
                <th className="py-2 pr-4">Period</th>
                <th className="py-2 pr-4">Total</th>
                <th className="py-2 pr-4">Adjustments</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {(data?.invoices ?? []).map((invoice) => (
                <tr key={invoice.invoice_id} className="border-b last:border-0">
                  <td className="py-2 pr-4">{invoice.provider}</td>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {invoice.period_start} to {invoice.period_end}
                  </td>
                  <td className="py-2 pr-4">{formatAmount(invoice.total, invoice.currency)}</td>
                  <td className="py-2 pr-4">
                    {invoice.adjustments.length === 0
                      ? "—"
                      : invoice.adjustments
                          .map((a) => `${ADJUSTMENT_LABEL[a.kind]} ${formatAmount(a.amount, invoice.currency)}`)
                          .join(", ")}
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      variant="ghost"
                      aria-label={`Remove the bill for ${invoice.provider}, ${invoice.period_start}`}
                      onClick={() => remove.mutate(invoice.invoice_id)}
                      disabled={remove.isPending}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
