"use client";

import Link from "next/link";

import { useBillingProbe } from "@/app/(dashboard)/hooks/providerApis/useBillingProbe";
import type { ProviderConnection } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { migratedHref } from "@/utils/migratedPages";
import { stateBadgeVariant, stateLabel } from "./connectionState";
import { probeHeadline, probeTone } from "./probeResult";

const whenever = (value: string | null): string => (value === null ? "Never" : new Date(value).toLocaleString());

const TONE_CLASS = {
  good: "text-green-700 dark:text-green-400",
  warning: "text-amber-700 dark:text-amber-400",
  bad: "text-destructive",
} as const;

export default function ConnectionTab({ connection }: { connection: ProviderConnection }) {
  const probe = useBillingProbe();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={stateBadgeVariant(connection.state)}>{stateLabel(connection.state)}</Badge>
        <Badge variant="outline">Read-only</Badge>
        <p className="text-sm text-muted-foreground">
          {connection.display_name} keys stored here are only ever used to read cost reports. They cannot send traffic
          or spend money
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            disabled={probe.isPending}
            aria-label={`Test the ${connection.display_name} connection`}
            onClick={() => probe.mutate(connection.provider)}
          >
            {probe.isPending ? "Testing..." : "Test connection"}
          </Button>
          <p className="text-sm text-muted-foreground">
            Reads a few days of cost from {connection.display_name} now and reports what came back. Nothing is stored
          </p>
        </div>

        {probe.isError && <p className="text-sm text-destructive">The test could not be run: {probe.error.message}</p>}

        {probe.data && (
          <div className="flex flex-col gap-1 rounded-md border p-3">
            <p className={`text-sm font-medium ${TONE_CLASS[probeTone(probe.data)]}`}>{probeHeadline(probe.data)}</p>
            {probe.data.credential_name && (
              <p className="text-xs text-muted-foreground">Using credential {probe.data.credential_name}</p>
            )}
            {/* Verbatim, never folded into a generic message: naming which of a wrong key, a
                missing entitlement or an outage this is, is the whole point of the button */}
            {probe.data.detail && <p className="text-xs text-muted-foreground">{probe.data.detail}</p>}
            {probe.data.sample_cost && (
              <p className="text-xs text-muted-foreground">First cost returned: {probe.data.sample_cost}</p>
            )}
          </div>
        )}
      </div>

      {connection.accounts.length === 0 ? (
        <p className="text-sm">
          No account is connected yet. Add a read-only billing key on{" "}
          <Link
            href={migratedHref("llm-provider-credentials")}
            className="text-primary underline-offset-4 hover:underline"
          >
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
