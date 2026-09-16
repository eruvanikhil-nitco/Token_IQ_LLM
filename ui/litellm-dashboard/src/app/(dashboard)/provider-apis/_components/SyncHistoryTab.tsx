"use client";

import { useProviderSyncHistory } from "@/app/(dashboard)/hooks/providerApis/useProviderSyncHistory";
import type { ProviderSyncOutcome } from "@/components/networking";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const OUTCOME_LABELS: Record<ProviderSyncOutcome, string> = {
  fetched: "Fetched",
  not_configured: "Cannot be used",
  failed: "Failed",
};

const OUTCOME_VARIANTS: Record<ProviderSyncOutcome, "default" | "secondary" | "destructive"> = {
  fetched: "default",
  not_configured: "secondary",
  failed: "destructive",
};

export default function SyncHistoryTab({ provider }: { provider: string }) {
  const { data: rows, isLoading, error } = useProviderSyncHistory(provider);

  if (isLoading) {
    return <p className="text-sm">Loading sync history...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read the sync history</p>;
  }
  if (!rows || rows.length === 0) {
    return <p className="text-sm">No sync has run yet for this provider</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Started</TableHead>
          <TableHead>Account</TableHead>
          <TableHead>Outcome</TableHead>
          <TableHead>Rows</TableHead>
          <TableHead>Detail</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.credential_name}-${row.started_at}`}>
            <TableCell>{new Date(row.started_at).toLocaleString()}</TableCell>
            <TableCell>{row.credential_name}</TableCell>
            <TableCell>
              <Badge variant={OUTCOME_VARIANTS[row.outcome]}>{OUTCOME_LABELS[row.outcome]}</Badge>
            </TableCell>
            <TableCell>{row.facts_written}</TableCell>
            <TableCell className="text-muted-foreground">{row.detail ?? ""}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
