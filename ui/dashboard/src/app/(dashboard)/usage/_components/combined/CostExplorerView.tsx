"use client";

import { useState } from "react";

import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useExplorer } from "@/app/(dashboard)/hooks/combined/useExplorer";
import { formatTotal } from "./comparisonDisplay";
import { DIMENSIONS, barWidths, type ExplorerDimension } from "./explorerDisplay";

const GATEWAY_COLOR = "var(--chart-gateway, #2a78d6)";
const OUTSIDE_COLOR = "var(--chart-outside, #eb6834)";

interface CostExplorerViewProps {
  days: number;
}

export default function CostExplorerView({ days }: CostExplorerViewProps) {
  const [dimension, setDimension] = useState<ExplorerDimension>("team");
  const { data, isLoading, error } = useExplorer(dimension, days);
  const widths = barWidths(data?.slices ?? []);

  return (
    <div className="flex flex-col gap-4">
      {/* Meaning before controls. And deliberately not the Source Comparison wording: there the
          provider and gateway totals must never be added, because the same request is in both.
          Here the two columns are one group&apos;s spend split by route, so they do add up, and
          saying otherwise would be as wrong as saying it the other way round. */}
      <p className="text-sm text-muted-foreground">
        Who the spend belongs to, split by how it reached the provider: through this gateway, or outside it and matched
        back by an attribution rule. For each row those two <strong>do</strong> add up to that group&apos;s spend.
        Anything that could not be matched to a group is listed separately rather than shared out, so no figure here is
        an estimate.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Label htmlFor="explorer-group-by" className="text-muted-foreground">
          Group by
        </Label>
        <Select
          items={DIMENSIONS}
          value={dimension}
          onValueChange={(next) => next !== null && setDimension(next as ExplorerDimension)}
        >
          <SelectTrigger id="explorer-group-by" aria-label="Group by" className="w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DIMENSIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Reading spend…</p>}
      {error && <p className="text-sm text-destructive">Could not read the cost explorer.</p>}

      {data && (
        <>
          <div className="flex flex-wrap gap-4 text-sm">
            <span className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3 rounded-sm"
                style={{ background: GATEWAY_COLOR }}
              />
              Through the gateway
            </span>
            <span className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3 rounded-sm"
                style={{ background: OUTSIDE_COLOR }}
              />
              Outside the gateway
            </span>
          </div>

          {data.note !== "" && <p className="text-sm text-muted-foreground">{data.note}</p>}

          {data.slices.length === 0 ? null : (
            <Card className="flex flex-col gap-4 p-4">
              {data.slices.map((slice, index) => (
                <div key={slice.key} className="flex flex-col gap-1.5">
                  <div className="flex items-baseline justify-between gap-4 text-sm">
                    <span className="flex min-w-0 items-baseline gap-2">
                      <span className="truncate font-medium">{slice.name}</span>
                      {/* The identifier stays on the page: it is what an attribution rule, a
                          filter or a support question is written against. It is only repeated
                          when it differs from the name, so an unnamed row does not read twice. */}
                      {slice.name !== slice.key && (
                        <span className="truncate text-xs text-muted-foreground">{slice.key}</span>
                      )}
                    </span>
                    <span className="whitespace-nowrap text-muted-foreground tabular-nums">
                      {formatTotal(slice.through_gateway)} through, {formatTotal(slice.outside_gateway)} outside
                    </span>
                  </div>
                  {/* The two segments stack because they are disjoint: outside-gateway spend is what
                      the provider charged BEYOND what the gateway recorded, so the bar's length is a
                      real total. Stacking the provider figure on the gateway figure would be the
                      double count the counting rule forbids; stacking the excess on it is not. */}
                  <div className="flex h-3 w-full items-stretch" role="img" aria-label={`${slice.name} spend`}>
                    <span
                      className="rounded-l-sm"
                      style={{ width: `${widths[index]?.gateway ?? 0}%`, background: GATEWAY_COLOR }}
                    />
                    {(widths[index]?.outside ?? 0) > 0 && (
                      <>
                        {/* a 2px surface gap so the two segments never read as one fill */}
                        <span className="w-[2px] bg-background" />
                        <span
                          className="rounded-r-sm"
                          style={{ width: `${widths[index]?.outside ?? 0}%`, background: OUTSIDE_COLOR }}
                        />
                      </>
                    )}
                  </div>
                </div>
              ))}
            </Card>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Through the gateway</p>
              <p className="text-xl font-semibold">{formatTotal(data.total_through_gateway)}</p>
              {data.unallocated_to_a_slice !== "0" && (
                <p className="text-sm text-muted-foreground">
                  {formatTotal(data.unallocated_to_a_slice)} of that has no {dimension} recorded, so it is in no bar
                  above.
                </p>
              )}
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Outside the gateway</p>
              <p className="text-xl font-semibold">{formatTotal(data.total_outside_gateway)}</p>
              {data.unattributable_outside_gateway !== "0" && (
                <p className="text-sm text-muted-foreground">
                  {formatTotal(data.unattributable_outside_gateway)} of that is money nobody owns.
                </p>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
