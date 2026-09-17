"use client";

import Link from "next/link";

import type { ProviderConnection } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { migratedHref } from "@/utils/migratedPages";
import { stateBadgeVariant, stateLabel } from "./connectionState";

const whenever = (value: string | null): string => (value === null ? "Never" : new Date(value).toLocaleString());

export default function ConnectionTab({ connection }: { connection: ProviderConnection }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={stateBadgeVariant(connection.state)}>{stateLabel(connection.state)}</Badge>
        <Badge variant="outline">Read-only</Badge>
        <p className="text-sm text-muted-foreground">
          {connection.display_name} keys stored here are only ever used to read cost reports. They cannot send
          traffic or spend money
        </p>
      </div>

      {connection.accounts.length === 0 ? (
        <p className="text-sm">
          No account is connected yet. Add a read-only billing key on{" "}
          <Link href={migratedHref("llm-provider-credentials")} className="text-primary underline-offset-4 hover:underline">
            LLM Provider Credentials
          </Link>{" "}
          and choose Billing access as the purpose
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Account</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Last sync</TableHead>
              <TableHead>Rows stored</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {connection.accounts.map((account) => (
              <TableRow key={account.credential_name}>
                <TableCell>{account.credential_name}</TableCell>
                <TableCell>
                  <Badge variant={stateBadgeVariant(account.state)}>{stateLabel(account.state)}</Badge>
                </TableCell>
                <TableCell>{whenever(account.last_sync_at)}</TableCell>
                <TableCell>{account.facts_stored}</TableCell>
                <TableCell className="text-muted-foreground">{account.detail ?? ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
