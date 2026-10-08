"use client";

import Link from "next/link";

import type { ToolConnection } from "@/app/(dashboard)/hooks/userTools/useToolConnections";
import {
  stateBadgeVariant,
  stateLabel,
  verificationBadgeVariant,
  verificationLabel,
} from "@/app/(dashboard)/(token-iq)/provider-apis/_components/connectionState";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { migratedHref } from "@/utils/migratedPages";

const whenever = (value: string | null): string => (value === null ? "Never" : new Date(value).toLocaleString());

export default function ToolConnectionTab({ connection }: { connection: ToolConnection }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={stateBadgeVariant(connection.state)}>{stateLabel(connection.state)}</Badge>
        <Badge variant={verificationBadgeVariant(connection.verified_against_real_account)}>
          {verificationLabel(connection.verified_against_real_account)}
        </Badge>
        <Badge variant="outline">Read-only</Badge>
      </div>

      {/* The limit belongs beside the state, not buried in a tab nobody opens. Two of these
          three tools cannot report what a reader assumes, and finding that out from a wrong
          total months later is the failure this line exists to prevent */}
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/40">
        <p className="text-xs font-medium uppercase text-amber-800 dark:text-amber-300">What this tool cannot tell us</p>
        <p className="text-sm">{connection.fetches.what_it_cannot_give}</p>
      </div>

      {connection.accounts.length === 0 ? (
        <p className="text-sm">
          No account is connected yet. Add a read-only key on{" "}
          <Link
            href={migratedHref("llm-provider-credentials")}
            className="text-primary underline-offset-4 hover:underline"
          >
            LLM Provider Credentials
          </Link>{" "}
          and choose User tool usage as the purpose
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
                <TableCell>{account.rows_stored}</TableCell>
                <TableCell className="text-muted-foreground">{account.detail ?? ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
