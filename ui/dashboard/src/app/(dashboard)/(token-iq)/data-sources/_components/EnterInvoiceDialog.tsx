"use client";

import { parseAsString, useQueryState } from "nuqs";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSaveInvoice } from "@/app/(dashboard)/hooks/ledger/useInvoices";
import { unwrapProxyErrorMessage } from "@/lib/http/client";
import type { AdjustmentKind, InvoiceProviderOption } from "@/components/networking";

import {
  ADJUSTMENT_KINDS,
  ENTER_BILL_PARAM,
  INVOICE_CURRENCIES,
  amountProblem,
  canSaveInvoice,
  invoicePayload,
  invoiceSavedMessage,
  monthOptions,
  prefilledMonth,
  prefilledProvider,
  signHint,
  type AdjustmentDraft,
} from "./invoiceSubmit";

/**
 * Data Sources > Uploads: enter a bill.
 *
 * The blueprint's own dialog is "Upload invoice", with the file read and its lines confirmed before
 * saving. Nothing here parses a PDF or a billing CSV, so the dialog asks for the figures instead of
 * pretending to read them, and says so. A file field that stored a document nobody extracts
 * anything from would leave a customer believing their bill had been understood.
 *
 * The month is one field rather than two dates, because the stored period is matched exactly when
 * that month is reconciled, and a period assembled by hand is a bill that silently fails to cover
 * the last day of its own month.
 */
interface EnterInvoiceDialogProps {
  providers: readonly InvoiceProviderOption[];
}

export default function EnterInvoiceDialog({ providers }: EnterInvoiceDialogProps) {
  const save = useSaveInvoice();
  const months = monthOptions(new Date());

  // A link from another screen can say which bill it meant, and ask for the dialog to be open on
  // arrival. Both values are checked rather than trusted: they came from a URL.
  const [askedToEnter, setAskedToEnter] = useQueryState(ENTER_BILL_PARAM, parseAsString);
  const [providerParam] = useQueryState("provider", parseAsString);
  const [monthParam] = useQueryState("month", parseAsString);

  const [open, setOpen] = useState(askedToEnter === "1");
  const [provider, setProvider] = useState(prefilledProvider(providerParam, providers));
  const [month, setMonth] = useState(prefilledMonth(monthParam, new Date()));
  const [currency, setCurrency] = useState<string>(INVOICE_CURRENCIES[0]);
  const [total, setTotal] = useState("");
  const [note, setNote] = useState("");
  const [adjustments, setAdjustments] = useState<readonly AdjustmentDraft[]>([]);
  const [saved, setSaved] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const draft = { provider, month, currency, total, note, adjustments };
  const ready = canSaveInvoice(draft) && !save.isPending;
  const totalProblem = amountProblem(total);
  const providerName = providers.find((option) => option.provider === provider)?.display_name ?? provider;

  const reset = () => {
    setTotal("");
    setNote("");
    setAdjustments([]);
    setSaved(null);
    setFailure(null);
  };

  const submit = async () => {
    const payload = invoicePayload(draft);
    if (payload === null) {
      return;
    }
    setFailure(null);
    setSaved(null);
    try {
      const stored = await save.mutateAsync(payload);
      setSaved(invoiceSavedMessage(stored, providerName));
      setTotal("");
      setNote("");
      setAdjustments([]);
    } catch (error) {
      setFailure(unwrapProxyErrorMessage(error instanceof Error ? error.message : String(error)));
    }
  };

  const changeAdjustment = (index: number, next: Partial<AdjustmentDraft>) => {
    setAdjustments(adjustments.map((entry, at) => (at === index ? { ...entry, ...next } : entry)));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          reset();
          // Cleared so a reload does not reopen a dialog the reader has closed.
          void setAskedToEnter(null);
        }
      }}
    >
      <DialogTrigger render={<Button />}>Enter a bill</DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Enter a bill</DialogTitle>
          <DialogDescription>
            Type the figures from a provider bill so the month can be reconciled against recorded usage. The figures
            are typed rather than read from the document, because nothing here parses a PDF or a billing CSV yet
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Label htmlFor="invoice-provider">Provider</Label>
            <select
              id="invoice-provider"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              {providers.map((option) => (
                <option key={option.provider} value={option.provider}>
                  {option.display_name}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted-foreground">The provider that issued the bill</span>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="invoice-month">Billing period</Label>
            <select
              id="invoice-month"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={month}
              onChange={(event) => setMonth(event.target.value)}
            >
              {months.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted-foreground">
              The whole month the bill covers. Reconciliation compares it against that month&apos;s usage, so entering
              the wrong month compares a real bill against usage it has nothing to do with
            </span>
          </div>

          <div className="flex flex-wrap gap-4">
            <div className="flex flex-col gap-1">
              <Label htmlFor="invoice-total">Bill total</Label>
              <Input
                id="invoice-total"
                required
                value={total}
                onChange={(event) => setTotal(event.target.value)}
                placeholder="48210.07"
              />
              {totalProblem ? <span className="text-xs text-destructive">{totalProblem}</span> : null}
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="invoice-currency">Currency</Label>
              <select
                id="invoice-currency"
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
              >
                {INVOICE_CURRENCIES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              <span className="text-xs text-muted-foreground">
                As the bill was written. Nothing is converted, because a rate nobody chose looks authoritative and is
                not
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-2 rounded-md border p-3">
            <span className="text-sm font-medium">Adjustments</span>
            <span className="text-xs text-muted-foreground">
              The reasons a bill legitimately differs from the usage behind it. Left out, each one shows up later as a
              difference nothing explains
            </span>

            {adjustments.map((adjustment, index) => {
              const problem = amountProblem(adjustment.amount);
              const hint = signHint(adjustment.kind, adjustment.amount);
              const spec = ADJUSTMENT_KINDS.find((candidate) => candidate.kind === adjustment.kind);
              return (
                <div key={index} className="flex flex-col gap-1 border-t pt-2 first:border-t-0 first:pt-0">
                  <div className="flex flex-wrap items-end gap-2">
                    <select
                      aria-label={`Adjustment ${index + 1} kind`}
                      className="h-9 rounded-md border bg-background px-2 text-sm"
                      value={adjustment.kind}
                      onChange={(event) => changeAdjustment(index, { kind: event.target.value as AdjustmentKind })}
                    >
                      {ADJUSTMENT_KINDS.map((option) => (
                        <option key={option.kind} value={option.kind}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <Input
                      aria-label={`Adjustment ${index + 1} amount`}
                      className="w-32"
                      value={adjustment.amount}
                      onChange={(event) => changeAdjustment(index, { amount: event.target.value })}
                      placeholder="-400.00"
                    />
                    <Input
                      aria-label={`Adjustment ${index + 1} note`}
                      className="w-48"
                      value={adjustment.note}
                      onChange={(event) => changeAdjustment(index, { note: event.target.value })}
                      placeholder="what it was for"
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove adjustment ${index + 1}`}
                      onClick={() => setAdjustments(adjustments.filter((_, at) => at !== index))}
                    >
                      Remove
                    </Button>
                  </div>
                  {spec ? <span className="text-xs text-muted-foreground">{spec.explanation}</span> : null}
                  {problem ? <span className="text-xs text-destructive">{problem}</span> : null}
                  {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
                </div>
              );
            })}

            <div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAdjustments([...adjustments, { kind: "commitment", amount: "", note: "" }])}
              >
                Add an adjustment
              </Button>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="invoice-note">Note</Label>
            <Input
              id="invoice-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="where this bill came from, or who to ask about it"
            />
          </div>

          {failure ? <p className="text-sm text-destructive">{failure}</p> : null}
          {saved ? <p className="text-sm">{saved}</p> : null}

          <div className="flex justify-end">
            <Button
              onClick={() => {
                void submit();
              }}
              disabled={!ready}
            >
              {save.isPending ? "Saving..." : "Save the bill"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
