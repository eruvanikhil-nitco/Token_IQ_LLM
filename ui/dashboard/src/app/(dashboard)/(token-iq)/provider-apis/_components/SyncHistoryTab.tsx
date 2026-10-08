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

// row.outcome is typed as ProviderSyncOutcome, but it arrives from the network unvalidated: a
// build one release behind the backend can see a fourth value here. Look it up defensively rather
// than trusting the type, and fail toward "unexpected" (visible, destructive), never toward calm.
const outcomeLabel = (outcome: ProviderSyncOutcome): string =>
  outcome in OUTCOME_LABELS ? OUTCOME_LABELS[outcome] : outcome;

const outcomeVariant = (outcome: ProviderSyncOutcome): "default" | "secondary" | "destructive" =>
  outcome in OUTCOME_VARIANTS ? OUTCOME_VARIANTS[outcome] : "destructive";

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
              <Badge variant={outcomeVariant(row.outcome)}>{outcomeLabel(row.outcome)}</Badge>
            </TableCell>
            <TableCell>{row.facts_written}</TableCell>
            <TableCell className="text-muted-foreground">{row.detail ?? ""}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
