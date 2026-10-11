"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProviderConnections } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { useToolConnections } from "@/app/(dashboard)/hooks/userTools/useToolConnections";
import { useDataQuality } from "@/app/(dashboard)/hooks/overview/useDataQuality";
import { migratedHrefIfRouted } from "@/utils/migratedPages";

import { accountRows, type ConnectionLike } from "./accountRows";
import {
  cleanChecks,
  coverageFigure,
  issueRows,
  lastDataAt,
  sourceHealth,
  sourceRollup,
  unknownChecks,
  type IssueStatus,
} from "./overviewRows";

const STATUS_BADGE: Record<IssueStatus, { label: string; variant: "default" | "secondary" | "destructive" }> = {
  needs_action: { label: "To fix", variant: "destructive" },
  clean: { label: "Clear", variant: "default" },
  unknown: { label: "Not known", variant: "secondary" },
};

function when(value: string | null): string {
  if (!value) {
    return "No data yet";
  }
  const at = new Date(value);
  return Number.isNaN(at.getTime()) ? value : at.toLocaleString();
}

function Figure({ label, figure, detail }: { label: string; figure: string; detail: string }) {
  return (
    <Card role="group" aria-label={label} className="flex flex-col gap-1 p-4">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-2xl font-semibold">{figure}</span>
      <span className="text-xs text-muted-foreground">{detail}</span>
    </Card>
  );
}

/**
 * Data Sources > Overview: can the data be trusted?
 *
 * Source health and freshness come from the same two connection endpoints the Accounts tab reads,
 * so the roll-up cannot disagree with the table it links to. Invoice coverage and the issues list
 * come from `/data-quality`, which applies the rule about what counts as a problem on the server.
 *
 * Nothing here is money. The tab lists provider sources and gateway sources together, which is
 * exactly where a grand total would be the one addition the counting rule forbids.
 */
export default function OverviewTab() {
  const providers = useProviderConnections();
  const tools = useToolConnections();
  const quality = useDataQuality();

  if (providers.isLoading || tools.isLoading || quality.isLoading) {
    return <p className="text-sm">Loading...</p>;
  }

  const rows = accountRows({
    providers: (providers.data ?? []).map(
      (p): ConnectionLike => ({
        key: p.provider,
        display_name: p.display_name,
        state: p.state,
        accounts: p.accounts.map((a) => ({ ...a, records_stored: a.facts_stored })),
      }),
    ),
    tools: (tools.data ?? []).map(
      (t): ConnectionLike => ({
        key: t.tool,
        display_name: t.display_name,
        state: t.state,
        accounts: t.accounts.map((a) => ({ ...a, records_stored: a.rows_stored })),
      }),
    ),
  });

  const health = sourceHealth(rows);
  const rollup = sourceRollup(rows);
  const issues = quality.data ? issueRows(quality.data.issues, migratedHrefIfRouted) : [];
  const coverage = quality.data ? coverageFigure(quality.data.invoice_coverage) : null;
  const accountsHref = migratedHrefIfRouted("provider-apis");

  return (
    <div className="flex flex-col gap-6">
      {providers.error || tools.error ? (
        <p className="text-sm text-destructive">
          Could not read every source, so the health figures below cover only the ones that answered
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Figure
          label="Sources healthy"
          figure={`${health.healthy} of ${health.connected}`}
          detail={
            health.connected === 0
              ? "Nothing is connected yet"
              : `${health.needsAttention} needing attention, ${health.notConnected} not connected`
          }
        />
        <Figure label="Last data" figure={when(lastDataAt(rows))} detail="The freshest sync across every source" />
        {/* No data quality score. A single number out of a hundred over four checks, one of which
            nobody can measure yet, would read the same whether that quarter was ever built. */}
        {coverage ? (
          <Figure label="Invoice coverage" figure={coverage.figure} detail={coverage.detail} />
        ) : (
          <Figure label="Invoice coverage" figure="Unavailable" detail="Could not read data quality" />
        )}
      </div>

      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold">Sources</h2>
          {accountsHref ? (
            <Link href={accountsHref} className="text-sm text-primary underline-offset-4 hover:underline">
              All accounts
            </Link>
          ) : null}
        </div>
        {rollup.length === 0 ? (
          <p className="text-sm text-muted-foreground">No source has been connected yet</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Kind</TableHead>
                <TableHead className="text-right">Connected</TableHead>
                <TableHead className="text-right">Not connected</TableHead>
                <TableHead className="text-right">Needing attention</TableHead>
                <TableHead>Last data</TableHead>
                {/* Records, not cost: this column sums provider sources and tool sources together. */}
                <TableHead className="text-right">Records</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rollup.map((row) => (
                <TableRow key={row.kind}>
                  <TableCell>{row.kind}</TableCell>
                  <TableCell className="text-right">{row.connected}</TableCell>
                  <TableCell className="text-right">{row.available}</TableCell>
                  <TableCell className="text-right">{row.needsAttention}</TableCell>
                  <TableCell>{when(row.lastDataAt)}</TableCell>
                  <TableCell className="text-right">{row.recordsStored.toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-base font-semibold">Data quality</h2>
        {quality.error ? (
          <p className="text-sm text-destructive">Could not read data quality checks</p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Check</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>What it found</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {issues.map((row) => (
                  <TableRow key={row.key}>
                    <TableCell>{row.title}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_BADGE[row.status].variant}>{STATUS_BADGE[row.status].label}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{row.detail}</TableCell>
                    <TableCell>
                      {row.fixHref ? (
                        <Link href={row.fixHref} className="text-sm text-primary underline-offset-4 hover:underline">
                          Fix
                        </Link>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="text-sm text-muted-foreground">
              {quality.data?.issues_to_fix ?? 0} to fix, {cleanChecks(issues)} clear, {unknownChecks(issues)} that
              nobody can answer yet. A check nobody can answer is not counted as a problem and is not counted as fine
              either, so this list carries it rather than leaving the tab looking settled
            </p>
          </>
        )}
      </section>
    </div>
  );
}
