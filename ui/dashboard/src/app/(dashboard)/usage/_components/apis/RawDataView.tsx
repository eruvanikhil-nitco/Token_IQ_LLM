"use client";

import { Fragment, useState } from "react";

import { useProviderUsageRaw } from "@/app/(dashboard)/hooks/providerUsage/useProviderUsageRaw";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ProviderRawFact } from "@/components/networking";
import CoverageNote from "./CoverageNote";

const RAW_PAGE_SIZE = 50;

const EVIDENCE_LABEL: Record<ProviderRawFact["evidence"], string> = {
  reconciled: "Reconciled",
  priced: "Priced",
  allocated: "Allocated",
};

const tokensSummary = (row: ProviderRawFact): string => {
  const parts = [
    row.input_tokens !== null ? `in ${row.input_tokens}` : null,
    row.output_tokens !== null ? `out ${row.output_tokens}` : null,
    row.cached_input_tokens !== null ? `cached ${row.cached_input_tokens}` : null,
    row.cache_write_tokens !== null ? `write ${row.cache_write_tokens}` : null,
  ].filter((part): part is string => part !== null);
  return parts.length > 0 ? parts.join(", ") : "-";
};

export default function RawDataView({ provider, displayName }: { provider: string; displayName: string }) {
  const [before, setBefore] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const { data, isLoading, error } = useProviderUsageRaw(provider, RAW_PAGE_SIZE, before);

  const toggleExpanded = (rowKey: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(rowKey)) {
        next.delete(rowKey);
      } else {
        next.add(rowKey);
      }
      return next;
    });
  };

  if (isLoading) {
    return <p className="text-sm">Loading raw usage...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read raw usage for this provider</p>;
  }
  if (!data) {
    return null;
  }

  const nextBefore = data.next_before;

  if (data.rows.length === 0) {
    const emptyPageMessage =
      before === null
        ? `No usage has synced yet for ${displayName}. This is expected until its connector completes a first sync`
        : `You've reached the end of the rows available for ${displayName}`;
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm">{emptyPageMessage}</p>
        <CoverageNote rows={data.rows} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Account</TableHead>
            <TableHead>Evidence</TableHead>
            <TableHead>Billed cost</TableHead>
            <TableHead>Tokens</TableHead>
            <TableHead>Provider request ID</TableHead>
            <TableHead>Provider&apos;s own key ID</TableHead>
            <TableHead>
              <span className="sr-only">Payload</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rows.map((row, index) => {
            const rowKey = `${row.bucket_start}-${row.credential_name}-${row.provider_request_id ?? index}`;
            const isExpanded = expanded.has(rowKey);
            const formattedTime = new Date(row.bucket_start).toLocaleString();
            const toggleLabel = `${isExpanded ? "Hide" : "Show"} payload for the row at ${formattedTime}`;
            return (
              <Fragment key={rowKey}>
                <TableRow>
                  <TableCell>{formattedTime}</TableCell>
                  <TableCell>{row.model ?? "Unknown model"}</TableCell>
                  <TableCell>{row.credential_name}</TableCell>
                  <TableCell>{EVIDENCE_LABEL[row.evidence]}</TableCell>
                  <TableCell>
                    {row.billed_cost} {row.billing_currency}
                  </TableCell>
                  <TableCell>{tokensSummary(row)}</TableCell>
                  <TableCell>{row.provider_request_id ?? "-"}</TableCell>
                  <TableCell>{row.provider_api_key_id ?? "-"}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" aria-expanded={isExpanded} onClick={() => toggleExpanded(rowKey)}>
                      {toggleLabel}
                    </Button>
                  </TableCell>
                </TableRow>
                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={9}>
                      {row.raw ? (
                        <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(row.raw, null, 2)}</pre>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          No payload was stored for this row. This is usually because payload capture began after
                          this row was fetched.
                        </p>
                      )}
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
      </Table>

      <CoverageNote rows={data.rows} />

      {nextBefore !== null && (
        <Button variant="outline" size="sm" className="w-fit" onClick={() => setBefore(nextBefore)}>
          Load older rows
        </Button>
      )}
    </div>
  );
}
