"use client";

import { useProviderUsageSummary } from "@/app/(dashboard)/hooks/providerUsage/useProviderUsageSummary";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { evidenceRows, hasUsage, tokenRows } from "./usageSummaryDisplay";

export default function UsageSummaryView({ provider, days }: { provider: string; days: number }) {
  const { data: summary, isLoading, error } = useProviderUsageSummary(provider, days);

  if (isLoading) {
    return <p className="text-sm">Loading usage...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read usage for this provider</p>;
  }
  if (!summary) {
    return null;
  }

  if (!hasUsage(summary)) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm">
          No usage has synced yet for {summary.display_name} in the last {summary.days} days. This is expected until
          its connector completes a first sync
        </p>
        <div className="flex flex-col gap-2 text-sm text-muted-foreground">
          <p>{summary.delay_note}</p>
          <p>{summary.settling_note}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div role="group" aria-label={`Total spend, last ${summary.days} days`}>
        <p className="text-sm text-muted-foreground">Total spend, last {summary.days} days</p>
        <p className="text-2xl font-semibold">${summary.total_cost}</p>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">Spend by model</p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead>Billed cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {summary.by_model.map((row) => (
              <TableRow key={row.model ?? "unknown"}>
                <TableCell>{row.model ?? "Unknown model"}</TableCell>
                <TableCell>${row.billed_cost}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">Spend by account</p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Account</TableHead>
              <TableHead>Billed cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {summary.by_account.map((row) => (
              <TableRow key={row.credential_name}>
                <TableCell>{row.credential_name}</TableCell>
                <TableCell>${row.billed_cost}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">Tokens</p>
        <Table>
          <TableBody>
            {tokenRows(summary.tokens).map((row) => (
              <TableRow key={row.label}>
                <TableCell className="w-56 font-medium">{row.label}</TableCell>
                <TableCell>{row.value.toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">Cost by evidence</p>
        <Table>
          <TableBody>
            {evidenceRows(summary.by_evidence).map((row) => (
              <TableRow key={row.level}>
                <TableCell className="w-64">
                  <div className="flex flex-col">
                    <span className="font-medium">{row.label}</span>
                    <span className="text-xs text-muted-foreground">{row.description}</span>
                  </div>
                </TableCell>
                <TableCell>${row.cost}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-2 text-sm text-muted-foreground">
        <p>{summary.delay_note}</p>
        <p>{summary.settling_note}</p>
      </div>
    </div>
  );
}
