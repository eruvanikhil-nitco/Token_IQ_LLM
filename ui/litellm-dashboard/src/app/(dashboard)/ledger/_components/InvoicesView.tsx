"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDeleteInvoice, useInvoices, useSaveInvoice } from "@/app/(dashboard)/hooks/ledger/useInvoices";
import { ADJUSTMENT_LABEL, formatAmount } from "./ledgerDisplay";
import type { AdjustmentKind } from "@/components/networking";

const KINDS: readonly AdjustmentKind[] = ["credit", "discount", "tax", "commitment"] as const;

interface InvoicesViewProps {
  provider: string;
  periodStart: string;
  periodEnd: string;
}

export default function InvoicesView({ provider, periodStart, periodEnd }: InvoicesViewProps) {
  const { data, isLoading, error } = useInvoices();
  const save = useSaveInvoice();
  const remove = useDeleteInvoice();

  const [total, setTotal] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [kind, setKind] = useState<AdjustmentKind>("credit");
  const [adjustment, setAdjustment] = useState("");

  const canSave = total.trim() !== "" && !save.isPending;

  const onSave = async () => {
    const adjustments = adjustment.trim() === "" ? [] : [{ kind, amount: adjustment.trim(), note: null }];
    const draft = {
      provider,
      period_start: periodStart,
      period_end: periodEnd,
      currency,
      total: total.trim(),
      adjustments,
    };
    await save.mutateAsync(draft);
    setTotal("");
    setAdjustment("");
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Enter the bill as the provider wrote it, in the currency it was written in. Almost no provider publishes
        invoices through an API, so this is read off the real bill. Adjustments are the reasons a bill legitimately
        differs from usage: a credit or discount makes the bill smaller, tax or a commitment charge makes it larger.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span>Invoice total</span>
          <Input
            aria-label="Invoice total"
            value={total}
            onChange={(event) => setTotal(event.target.value)}
            placeholder="as written on the bill"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Currency</span>
          <Input
            aria-label="Currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Adjustment</span>
          <select
            aria-label="Adjustment kind"
            className="h-9 rounded-md border bg-background px-2"
            value={kind}
            onChange={(event) => setKind(event.target.value as AdjustmentKind)}
          >
            {KINDS.map((option) => (
              <option key={option} value={option}>
                {ADJUSTMENT_LABEL[option]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Adjustment amount</span>
          <Input
            aria-label="Adjustment amount"
            value={adjustment}
            onChange={(event) => setAdjustment(event.target.value)}
            placeholder="negative reduces the bill"
          />
        </label>
        <Button onClick={onSave} disabled={!canSave}>
          {save.isPending ? "Saving…" : "Save invoice"}
        </Button>
      </div>

      {save.isError && <p className="text-sm text-destructive">Could not save that bill.</p>}
      {remove.isError && (
        <p className="text-sm text-destructive">Could not remove that bill, so it is still being compared.</p>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Reading the bills…</p>}
      {error && <p className="text-sm text-destructive">Could not read the bills.</p>}

      {!isLoading && (data?.invoices.length ?? 0) === 0 && (
        <p className="text-sm text-muted-foreground">
          No bills entered yet, so nothing can be reconciled against the ledger.
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
