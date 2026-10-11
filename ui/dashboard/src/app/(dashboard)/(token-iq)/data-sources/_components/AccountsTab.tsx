"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProviderConnections } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { useToolConnections } from "@/app/(dashboard)/hooks/userTools/useToolConnections";
import {
  stateBadgeVariant,
  stateLabel,
  type ConnectionState,
} from "@/app/(dashboard)/(token-iq)/provider-apis/_components/connectionState";

import { accountRows, opensRawRecords, recordsHeld, type ConnectionLike } from "./accountRows";
import RawRecordsPanel from "./RawRecordsPanel";

/** When a sync last brought anything back, in the reader's own timezone. */
function lastSync(value: string | null): string {
  if (!value) {
    return "Never";
  }
  const when = new Date(value);
  return Number.isNaN(when.getTime()) ? value : when.toLocaleString();
}

export default function AccountsTab() {
  const providers = useProviderConnections();
  const tools = useToolConnections();
  const [openFor, setOpenFor] = useState<string | null>(null);

  if (providers.isLoading || tools.isLoading) {
    return <p className="text-sm">Loading accounts...</p>;
  }
  // Each half is reported separately. Saying "could not read accounts" when only the tool half
  // failed would hide a working provider list behind the other one's outage.
  if (providers.error && tools.error) {
    return <p className="text-sm text-destructive">Could not read any accounts</p>;
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

  if (rows.length === 0) {
    return <p className="text-sm">Nothing is connected yet. Use Connect account to add the first one.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {providers.error ? (
        <p className="text-sm text-destructive">Could not read provider accounts; tool accounts are shown</p>
      ) : null}
      {tools.error ? (
        <p className="text-sm text-destructive">Could not read tool accounts; provider accounts are shown</p>
      ) : null}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Source</TableHead>
            <TableHead>Kind</TableHead>
            <TableHead>Account</TableHead>
            <TableHead>State</TableHead>
            <TableHead>Last sync</TableHead>
            {/* Records, not cost. This table lists provider accounts and tool accounts together,
                and a cost column here would be the one addition the counting rule forbids. */}
            <TableHead className="text-right">Records</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>{row.source}</TableCell>
              <TableCell>{row.kind}</TableCell>
              <TableCell>{row.account ?? <span className="text-muted-foreground">Not connected</span>}</TableCell>
              <TableCell>
                <Badge variant={stateBadgeVariant(row.state as ConnectionState)}>
                  {stateLabel(row.state as ConnectionState)}
                </Badge>
                {row.detail ? <span className="ml-2 text-xs text-muted-foreground">{row.detail}</span> : null}
              </TableCell>
              <TableCell>{lastSync(row.lastSyncAt)}</TableCell>
              <TableCell className="text-right">{row.recordsStored.toLocaleString()}</TableCell>
              <TableCell>
                {opensRawRecords(row) ? (
                  <Button
                    variant="link"
                    size="sm"
                    // Keyed on the source, not the row: `/provider/usage/raw` is scoped to a
                    // provider, so the records belong to it rather than to one of its accounts.
                    onClick={() => setOpenFor(openFor === row.sourceKey ? null : row.sourceKey)}
                    aria-expanded={openFor === row.sourceKey}
                  >
                    {openFor === row.sourceKey ? "Hide raw records" : "Raw records"}
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {openFor ? <RawRecordsPanel provider={openFor} onClose={() => setOpenFor(null)} /> : null}

      <p className="text-sm text-muted-foreground">
        {rows.length.toLocaleString()} account{rows.length === 1 ? "" : "s"}, holding{" "}
        {recordsHeld(rows).toLocaleString()} raw records. Records are what each source sent, before Token IQ priced
        or allocated anything.
      </p>
    </div>
  );
}
