"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useAddProviderRate,
  useDeleteProviderRate,
  useProviderRates,
} from "@/app/(dashboard)/hooks/pricing/usePricingRates";
import { BILLING_PROVIDERS } from "@/components/model_add/credential_form_helpers";
import { unwrapProxyErrorMessage } from "@/lib/http/client";

import {
  EMPTY_RATE,
  PRICE_FIELDS,
  canSaveRate,
  periodProblem,
  periodSummary,
  ratePayload,
  rateProblem,
  rateSummary,
  type RateDraft,
} from "./rateSubmit";

/**
 * Administration > Pricing & Rates: what this customer actually pays.
 *
 * The blueprint's "contracted discounts and the effective price per model". Two shapes, because
 * they are not variants of one: a percentage off list follows list price when the provider changes
 * it, and a committed price per million replaces list entirely.
 *
 * Every rate carries the period it applies to and where it came from. The period is what lets a
 * closed month re-price at the rate that applied then, and the source is how somebody later dares
 * to correct a figure rather than leaving one nobody can trace.
 */
export default function ContractedRatesPanel() {
  const { data, isLoading, error } = useProviderRates();
  const add = useAddProviderRate();
  const remove = useDeleteProviderRate();

  const [draft, setDraft] = useState<RateDraft>(EMPTY_RATE);
  const [failure, setFailure] = useState<string | null>(null);

  const problem = rateProblem(draft) ?? periodProblem(draft);
  const ready = canSaveRate(draft) && !add.isPending;

  const save = async () => {
    setFailure(null);
    try {
      await add.mutateAsync(ratePayload(draft));
      setDraft(EMPTY_RATE);
    } catch (caught) {
      setFailure(unwrapProxyErrorMessage(caught instanceof Error ? caught.message : String(caught)));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-3xl text-sm text-muted-foreground">
        What your contracts say you pay, as opposed to what a model costs at list. A discount follows the list price
        when a provider changes it; a committed price replaces it. Nothing is applied outside the period you give,
        because a closed month has to price at the rate that applied then
      </p>

      <div className="flex flex-col gap-3 rounded-md border p-4">
        <div className="flex flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="rate-provider">Provider</Label>
            <select
              id="rate-provider"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={draft.provider}
              onChange={(event) => setDraft({ ...draft, provider: event.target.value })}
            >
              <option value="">Choose a provider</option>
              {BILLING_PROVIDERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="rate-basis">What the contract says</Label>
            <select
              id="rate-basis"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={draft.basis}
              onChange={(event) => setDraft({ ...draft, basis: event.target.value as RateDraft["basis"] })}
            >
              <option value="discount">A percentage off list</option>
              <option value="unit_price">A committed price per million</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="rate-amount">{draft.basis === "discount" ? "Per cent off" : "Price per million"}</Label>
            <Input
              id="rate-amount"
              className="w-36"
              value={draft.amount}
              onChange={(event) => setDraft({ ...draft, amount: event.target.value })}
              placeholder={draft.basis === "discount" ? "20" : "2.50"}
            />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="rate-model">Model</Label>
            <Input
              id="rate-model"
              className="w-56"
              value={draft.model}
              onChange={(event) => setDraft({ ...draft, model: event.target.value })}
              placeholder={draft.basis === "discount" ? "every model" : "claude-sonnet-4-5"}
            />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="rate-field">Meter</Label>
            <select
              id="rate-field"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={draft.field}
              onChange={(event) => setDraft({ ...draft, field: event.target.value })}
            >
              <option value="">Every meter</option>
              {PRICE_FIELDS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="rate-from">First day it applies</Label>
            <input
              id="rate-from"
              type="date"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={draft.effectiveFrom}
              onChange={(event) => setDraft({ ...draft, effectiveFrom: event.target.value })}
            />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="rate-to">Last day it applies</Label>
            <input
              id="rate-to"
              type="date"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={draft.effectiveTo}
              onChange={(event) => setDraft({ ...draft, effectiveTo: event.target.value })}
            />
            <span className="text-xs text-muted-foreground">Leave empty while it is still in force</span>
          </div>

          <div className="flex flex-1 flex-col gap-1">
            <Label htmlFor="rate-source">Where it came from</Label>
            <Input
              id="rate-source"
              value={draft.source}
              onChange={(event) => setDraft({ ...draft, source: event.target.value })}
              placeholder="the enterprise agreement signed in August"
            />
          </div>
        </div>

        {problem ? <span className="text-xs text-destructive">{problem}</span> : null}
        {failure ? <span className="text-sm text-destructive">{failure}</span> : null}

        <div className="flex justify-end">
          <Button
            disabled={!ready}
            onClick={() => {
              void save();
            }}
          >
            {add.isPending ? "Recording..." : "Record this rate"}
          </Button>
        </div>
      </div>

      {isLoading ? <p className="text-sm">Reading the rates...</p> : null}
      {error ? <p className="text-sm text-destructive">Could not read the rates</p> : null}
      {remove.isError ? (
        <p className="text-sm text-destructive">Could not remove that rate, so it is still being applied.</p>
      ) : null}

      {!isLoading && (data?.length ?? 0) === 0 ? (
        <p className="text-sm text-muted-foreground">
          No rates recorded, so every figure Token IQ works out for itself uses the public price list. If you have
          negotiated anything, that figure is wrong by exactly what you negotiated
        </p>
      ) : null}

      {(data?.length ?? 0) > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Provider</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Meter</TableHead>
              <TableHead>What you pay</TableHead>
              <TableHead>Period</TableHead>
              <TableHead>Where it came from</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((rate) => (
              <TableRow key={rate.rate_id}>
                <TableCell>{rate.provider}</TableCell>
                <TableCell>{rate.model ?? <span className="text-muted-foreground">every model</span>}</TableCell>
                <TableCell>{rate.field ?? <span className="text-muted-foreground">every meter</span>}</TableCell>
                <TableCell>{rateSummary(rate)}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {periodSummary(rate.effective_from, rate.effective_to)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{rate.source}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove the ${rate.provider} rate from ${rate.effective_from}`}
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
