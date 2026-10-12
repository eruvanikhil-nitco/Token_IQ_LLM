"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useAddCurrencyRate,
  useCurrencyRates,
  useDeleteCurrencyRate,
} from "@/app/(dashboard)/hooks/pricing/usePricingRates";
import { unwrapProxyErrorMessage } from "@/lib/http/client";

import {
  EMPTY_CURRENCY,
  canSaveCurrency,
  currencyPayload,
  currencyPeriodProblem,
  currencyProblem,
  periodSummary,
  type CurrencyDraft,
} from "./rateSubmit";

/**
 * Administration > Pricing & Rates: the rate a period was booked at.
 *
 * One direction per row, and no inversion anywhere in this product: one divided by 1.0823 is a
 * figure nobody entered, and its last digits would be a rounding chosen on a customer's behalf. So
 * the panel says to record the direction being reported in, and a figure that cannot be converted
 * is reported per currency rather than folded into a total that looks complete.
 */
export default function CurrencyRatesPanel() {
  const { data, isLoading, error } = useCurrencyRates();
  const add = useAddCurrencyRate();
  const remove = useDeleteCurrencyRate();

  const [draft, setDraft] = useState<CurrencyDraft>(EMPTY_CURRENCY);
  const [failure, setFailure] = useState<string | null>(null);

  const problem = currencyProblem(draft) ?? currencyPeriodProblem(draft);
  const ready = canSaveCurrency(draft) && !add.isPending;

  const save = async () => {
    setFailure(null);
    try {
      await add.mutateAsync(currencyPayload(draft));
      setDraft(EMPTY_CURRENCY);
    } catch (caught) {
      setFailure(unwrapProxyErrorMessage(caught instanceof Error ? caught.message : String(caught)));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-3xl text-sm text-muted-foreground">
        The rate your finance team booked a period at, so invoices in several currencies can be reported as one
        figure. One direction per rate: a rate recorded the other way round is never inverted, because one divided by
        a rate is a figure nobody entered. A currency with no rate is reported on its own rather than folded into a
        total that would look complete and be short
      </p>

      <div className="flex flex-wrap items-end gap-3 rounded-md border p-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="currency-source">Convert from</Label>
          <Input
            id="currency-source"
            className="w-24"
            value={draft.sourceCurrency}
            onChange={(event) => setDraft({ ...draft, sourceCurrency: event.target.value.toUpperCase() })}
            placeholder="EUR"
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="currency-target">Report in</Label>
          <Input
            id="currency-target"
            className="w-24"
            value={draft.targetCurrency}
            onChange={(event) => setDraft({ ...draft, targetCurrency: event.target.value.toUpperCase() })}
            placeholder="USD"
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="currency-rate">Rate</Label>
          <Input
            id="currency-rate"
            className="w-32"
            value={draft.rate}
            onChange={(event) => setDraft({ ...draft, rate: event.target.value })}
            placeholder="1.0823"
          />
          <span className="text-xs text-muted-foreground">How many of the second one of the first buys</span>
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="currency-from">First day</Label>
          <input
            id="currency-from"
            type="date"
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={draft.effectiveFrom}
            onChange={(event) => setDraft({ ...draft, effectiveFrom: event.target.value })}
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="currency-to">Last day</Label>
          <input
            id="currency-to"
            type="date"
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={draft.effectiveTo}
            onChange={(event) => setDraft({ ...draft, effectiveTo: event.target.value })}
          />
        </div>

        <div className="flex min-w-48 flex-1 flex-col gap-1">
          <Label htmlFor="currency-source-note">Where it came from</Label>
          <Input
            id="currency-source-note"
            value={draft.source}
            onChange={(event) => setDraft({ ...draft, source: event.target.value })}
            placeholder="the rate finance booked September at"
          />
        </div>

        <Button
          disabled={!ready}
          onClick={() => {
            void save();
          }}
        >
          {add.isPending ? "Recording..." : "Record this rate"}
        </Button>
      </div>

      {problem ? <span className="text-xs text-destructive">{problem}</span> : null}
      {failure ? <span className="text-sm text-destructive">{failure}</span> : null}

      {isLoading ? <p className="text-sm">Reading the rates...</p> : null}
      {error ? <p className="text-sm text-destructive">Could not read the conversion rates</p> : null}
      {remove.isError ? (
        <p className="text-sm text-destructive">Could not remove that rate, so it is still being applied.</p>
      ) : null}

      {!isLoading && (data?.length ?? 0) === 0 ? (
        <p className="text-sm text-muted-foreground">
          No conversion rates recorded. Figures stay in the currency they were billed in, which is correct and means
          a customer billed in two currencies has two totals rather than one
        </p>
      ) : null}

      {(data?.length ?? 0) > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>From</TableHead>
              <TableHead>To</TableHead>
              <TableHead className="text-right">Rate</TableHead>
              <TableHead>Period</TableHead>
              <TableHead>Where it came from</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((rate) => (
              <TableRow key={rate.rate_id}>
                <TableCell>{rate.source_currency}</TableCell>
                <TableCell>{rate.target_currency}</TableCell>
                <TableCell className="text-right">{rate.rate}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {periodSummary(rate.effective_from, rate.effective_to)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{rate.source}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove the ${rate.source_currency} to ${rate.target_currency} rate from ${rate.effective_from}`}
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(rate.rate_id)}
                  >
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </div>
  );
}
