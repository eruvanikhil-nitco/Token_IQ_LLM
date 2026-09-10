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
import {
  buildPatch,
  hasErrors,
  isDirty,
  isEditable,
  limitsOf,
  modelId,
  validate,
  LIMIT_FIELDS,
  type LimitField,
  type Limits,
  type ModelRow,
} from "./modelLimits";

const FIELD_LABELS: Readonly<Record<LimitField, string>> = {
  tpm: "Tokens / min",
  rpm: "Requests / min",
  timeout: "Timeout (s)",
};

const PAGE_SIZE = 100;

/**
 * Per-model rate and timeout limits.
 *
 * A table rather than a form field on Add Model, because these are operational: you set one
 * when a team starts hammering a model, not while first creating it. The backend has always
 * supported them; the only way to set one was hand-written JSON in an advanced settings box.
 *
 * Blank means no limit. Only deployments stored in the database can be edited, because the
 * API cannot patch a model declared in the config file.
 */
const ModelLimitsTab: React.FC = () => {
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();
  const [edits, setEdits] = useState<Record<string, Limits>>({});

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
    mutationFn: async ({ id, limits }: { id: string; limits: Limits }) =>
      await modelPatchCall(accessToken as string, id, buildPatch(limits)),
    onSuccess: (_result, variables) => {
      toast.success("Limits saved");
      setEdits((current) => {
        const { [variables.id]: _removed, ...rest } = current;
        return rest;
      });
      queryClient.invalidateQueries({ queryKey: ["models"] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not save the limits"),
  });

  const limitsFor = (model: ModelRow): Limits => edits[modelId(model)] ?? limitsOf(model);

  const onChange = (model: ModelRow, field: LimitField, value: string) => {
    const id = modelId(model);
    setEdits((current) => ({
      ...current,
      [id]: { ...(current[id] ?? limitsOf(model)), [field]: value },
    }));
  };

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
            {LIMIT_FIELDS.map((field) => (
              <TableHead key={field}>{FIELD_LABELS[field]}</TableHead>
            ))}
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.map((model) => {
            const id = modelId(model);
            const limits = limitsFor(model);
            const editable = isEditable(model);
            const dirty = isDirty(limits, limitsOf(model));
            const invalid = hasErrors(limits);

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
                {LIMIT_FIELDS.map((field) => {
                  const check = validate(field, limits[field]);
                  return (
                    <TableCell key={field}>
                      <Input
                        aria-label={`${FIELD_LABELS[field]} for ${model.model_name}`}
                        value={limits[field]}
                        placeholder="none"
                        disabled={!editable || save.isPending}
                        onChange={(event) => onChange(model, field, event.target.value)}
                        className="max-w-28"
                      />
                      {!check.ok && <p className="mt-1 text-xs text-destructive">{check.error}</p>}
                    </TableCell>
                  );
                })}
                <TableCell className="text-right">
                  {editable && dirty && (
                    <span className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={save.isPending}
                        onClick={() =>
                          setEdits((current) => {
                            const { [id]: _removed, ...rest } = current;
                            return rest;
                          })
                        }
                      >
                        Reset
                      </Button>
                      <Button
                        size="sm"
                        disabled={invalid || save.isPending}
                        onClick={() => save.mutate({ id, limits })}
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
        <CardTitle className="text-base">Model limits</CardTitle>
        <p className="text-sm text-muted-foreground">
          Per-model ceilings on tokens and requests per minute, and how long to wait for a response. Leave a field blank
          for no limit. These apply to the deployment, on top of any limit a key or team carries.
        </p>
      </CardHeader>
      <CardContent>{body()}</CardContent>
    </Card>
  );
};

export default ModelLimitsTab;
