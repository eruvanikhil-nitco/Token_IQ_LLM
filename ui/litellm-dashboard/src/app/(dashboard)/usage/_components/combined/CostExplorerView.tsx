"use client";

import { useState } from "react";

import { Card } from "@/components/ui/card";
import { useExplorer } from "@/app/(dashboard)/hooks/combined/useExplorer";
import { formatAmount } from "./comparisonDisplay";
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
      <label className="flex w-fit flex-col gap-1 text-sm">
        <span>Group by</span>
        <select
          aria-label="Group by"
          className="h-9 rounded-md border bg-background px-2"
          value={dimension}
          onChange={(event) => setDimension(event.target.value as ExplorerDimension)}
        >
          {DIMENSIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

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
            <div className="flex flex-col gap-3">
              {data.slices.map((slice, index) => (
                <div key={slice.key} className="flex flex-col gap-1">
                  <div className="flex justify-between text-sm">
                    <span className="truncate pr-4">{slice.key}</span>
                    <span className="text-muted-foreground whitespace-nowrap">
                      {formatAmount(slice.through_gateway)} through, {formatAmount(slice.outside_gateway)} outside
                    </span>
                  </div>
                  {/* The two segments stack because they are disjoint: outside-gateway spend is what
                      the provider charged BEYOND what the gateway recorded, so the bar's length is a
                      real total. Stacking the provider figure on the gateway figure would be the
                      double count the counting rule forbids; stacking the excess on it is not. */}
                  <div className="flex h-3 w-full items-stretch" role="img" aria-label={`${slice.key} spend`}>
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
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Through the gateway</p>
              <p className="text-xl font-semibold">{formatAmount(data.total_through_gateway)}</p>
              {data.unallocated_to_a_slice !== "0" && (
                <p className="text-sm text-muted-foreground">
                  {formatAmount(data.unallocated_to_a_slice)} of that has no {dimension} recorded, so it is in no bar
                  above.
                </p>
              )}
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Outside the gateway</p>
              <p className="text-xl font-semibold">{formatAmount(data.total_outside_gateway)}</p>
              {data.unattributable_outside_gateway !== "0" && (
                <p className="text-sm text-muted-foreground">
                  {formatAmount(data.unattributable_outside_gateway)} of that is money nobody owns.
                </p>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
