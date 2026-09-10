"use client";

import React, { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { modelPatchCall } from "@/components/networking";
import { useModelsInfo } from "../../hooks/models/useModels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { UiLoadingSpinner } from "@/components/ui/ui-loading-spinner";
import { toast } from "@/lib/toast";
import { PRICING_FIELDS, RATE_ERROR_TEXT, type PricingField } from "@/lib/pricing/modelPricing";
import {
  buildRowPatch,
  errorsOf,
  hasErrors,
  isDirty,
  isEditable,
  isFromPriceList,
  modelId,
  ptuCountOf,
  ratesOf,
  type ModelRow,
  type RateText,
} from "./pricingRows";

const COLUMN_LABELS: Readonly<Record<PricingField, string>> = {
  input: "Input / 1M",
  output: "Output / 1M",
  cacheRead: "Cache read / 1M",
  cacheWrite: "Cache write / 1M",
};

const PAGE_SIZE = 100;

/**
 * Every model's rates, side by side.
 *
 * The two existing pricing screens each answer "what does this one model cost". Neither can
 * answer "what are we paying across everything, and did a rate move", which is the question a
 * bill actually raises. That is what a table gives you that a form cannot.
 *
 * Rates shown are per million tokens. A rate the deployment does not override is still shown,
 * taken from the built-in price map and marked as such, because a blank there would suggest the
 * model is free rather than priced elsewhere.
 */
const ModelPricingTab: React.FC = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();
  const [edits, setEdits] = useState<Record<string, RateText>>({});

  const { data, isLoading, isError } = useModelsInfo(
    1,
    PAGE_SIZE,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    true,
    undefined,
    true,
  );

  const models: readonly ModelRow[] = useMemo(() => data?.data ?? [], [data]);

  const save = useMutation({
    mutationFn: async ({ id, current, original }: { id: string; current: RateText; original: RateText }) =>
      await modelPatchCall(accessToken as string, id, buildRowPatch(current, original)),
    onSuccess: (_result, variables) => {
      toast.success("Pricing saved");
      setEdits((state) => {
        const { [variables.id]: _saved, ...rest } = state;
        return rest;
      });
      queryClient.invalidateQueries({ queryKey: ["models"] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not save the pricing"),
  });

  const ratesFor = (model: ModelRow): RateText => edits[modelId(model)] ?? ratesOf(model);

  const onChange = (model: ModelRow, field: PricingField, value: string) => {
    const id = modelId(model);
    setEdits((state) => ({ ...state, [id]: { ...(state[id] ?? ratesOf(model)), [field]: value } }));
  };

  const reset = (id: string) =>
    setEdits((state) => {
      const { [id]: _discarded, ...rest } = state;
      return rest;
    });

  const body = () => {
    if (isLoading) {
      return (
        <div className="flex justify-center py-8">
          <UiLoadingSpinner />
        </div>
      );
    }
    if (isError) {
      return <p className="py-6 text-sm text-muted-foreground">Could not load the models.</p>;
    }
    if (models.length === 0) {
      return <p className="py-6 text-sm text-muted-foreground">No models configured.</p>;
    }

    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead>
            {PRICING_FIELDS.map((field) => (
              <TableHead key={field}>{COLUMN_LABELS[field]}</TableHead>
            ))}
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.map((model) => {
            const id = modelId(model);
            const rates = ratesFor(model);
            const original = ratesOf(model);
            const editable = isEditable(model);
            const ptuCount = ptuCountOf(model);
            const errors = errorsOf(rates, ptuCount);
            const dirty = isDirty(rates, original);

            return (
              <TableRow key={id || model.model_name}>
                <TableCell className="font-medium">
                  {model.model_name}
                  {!editable && (
                    <Badge
                      variant="outline"
                      className="ml-2"
                      title="Declared in the config file, so it cannot be edited here"
                    >
                      config file
                    </Badge>
                  )}
                </TableCell>
                {PRICING_FIELDS.map((field) => {
                  const error = errors[field];
                  return (
                    <TableCell key={field}>
                      <Input
                        aria-label={`${COLUMN_LABELS[field]} for ${model.model_name}`}
                        value={rates[field]}
                        placeholder="none"
                        disabled={!editable || save.isPending}
                        onChange={(event) => onChange(model, field, event.target.value)}
                        className="max-w-28"
                      />
                      {error && <p className="mt-1 text-xs text-destructive">{RATE_ERROR_TEXT[error]}</p>}
                      {!error && isFromPriceList(model, field, rates) && (
                        <p className="mt-1 text-xs text-muted-foreground">from price list</p>
                      )}
                    </TableCell>
                  );
                })}
                <TableCell className="text-right">
                  {editable && dirty && (
                    <span className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" disabled={save.isPending} onClick={() => reset(id)}>
                        Reset
                      </Button>
                      <Button
                        size="sm"
                        disabled={hasErrors(rates, ptuCount) || save.isPending}
                        onClick={() => save.mutate({ id, current: rates, original })}
                      >
                        Save
                      </Button>
                    </span>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Model pricing</CardTitle>
        <p className="text-sm text-muted-foreground">
          What each model costs, in dollars per million tokens. A rate marked &ldquo;from price list&rdquo; is the
          built-in rate for that model rather than one you set; type over it to override it, or clear a rate to go back
          to the built-in one. Leave cache rates blank to charge them at the input rate.
        </p>
      </CardHeader>
      <CardContent>{body()}</CardContent>
    </Card>
  );
};

export default ModelPricingTab;
