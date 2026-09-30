"use client";

import Link from "next/link";
import { useState } from "react";

import { useOverview } from "@/app/(dashboard)/hooks/overview/useOverview";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { migratedHref } from "@/utils/migratedPages";
import {
  MATCH_LABEL,
  MATCH_TONE,
  changeDirection,
  changeLabel,
  formatAmount,
  formatShare,
  formatSynced,
} from "./overviewDisplay";

/** The month so far, which is the period someone opening this page is asking about. */
const defaultPeriod = (): { start: string; end: string } => {
  const now = new Date();
  const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  return { start: first.toISOString().slice(0, 10), end: now.toISOString().slice(0, 10) };
};

const TONE_BADGE = {
  good: "secondary",
  warning: "destructive",
  neutral: "outline",
} as const;

const CHANGE_CLASS = {
  up: "text-amber-700 dark:text-amber-400",
  down: "text-green-700 dark:text-green-400",
  unknown: "text-muted-foreground",
} as const;

function Stat({ label, value, note }: { label: string; value: string; note?: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      {note}
    </Card>
  );
}

export default function OverviewPanel() {
  const period = defaultPeriod();
  const [periodStart, setPeriodStart] = useState(period.start);
  const [periodEnd, setPeriodEnd] = useState(period.end);

  const { data, isLoading, error } = useOverview(periodStart, periodEnd);

  if (isLoading) return <p className="text-sm">Working out where the money went...</p>;
  if (error) return <p className="text-sm text-destructive">Could not read the overview</p>;
  if (!data) return null;

  const nothingYet = data.total === null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span>Period start</span>
          <input
            aria-label="Period start"
            type="date"
            className="h-9 rounded-md border bg-background px-2"
            value={periodStart}
            onChange={(event) => setPeriodStart(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Period end</span>
          <input
            aria-label="Period end"
            type="date"
            className="h-9 rounded-md border bg-background px-2"
            value={periodEnd}
            onChange={(event) => setPeriodEnd(event.target.value)}
          />
        </label>
      </div>

      {nothingYet ? (
        <Card className="p-6">
          <p className="text-base font-medium">Nothing has been recorded for this period yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            This is not the same as spending nothing. Connect a provider on{" "}
            <Link href={migratedHref("provider-apis")} className="text-primary underline-offset-4 hover:underline">
              Provider APIs
            </Link>{" "}
            and its costs appear here once the first sync completes
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label={`Total spend, ${data.currency}`}
            value={formatAmount(data.total)}
            note={
              <p className={`text-xs ${CHANGE_CLASS[changeDirection(data.change)]}`}>{changeLabel(data.change)}</p>
            }
          />
          <Stat
            label="Attributed through the gateway"
            value={formatAmount(data.attributed)}
            note={
              <p className="text-xs text-muted-foreground">
                Who spent it, not how much was spent. Never added to the total
              </p>
            }
          />
          <Stat
            label="Nobody owns"
            value={formatAmount(data.unallocated)}
            note={<p className="text-xs text-muted-foreground">{formatShare(data.unallocated_share)} of what providers billed</p>}
          />
          <Stat
            label="Providers billing"
            value={String(data.providers.length)}
            note={<p className="text-xs text-muted-foreground">Reporting cost in this period</p>}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col gap-3 p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-base font-semibold">Does the bill match</h2>
            <Link href={migratedHref("ledger")} className="text-sm text-primary underline-offset-4 hover:underline">
              Ledger
            </Link>
          </div>
          {data.providers.length === 0 ? (
            <p className="text-sm text-muted-foreground">No provider reported a cost in this period</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Billed</TableHead>
                  <TableHead>Gateway</TableHead>
                  <TableHead>Standing</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.providers.map((entry) => (
                  <TableRow key={entry.provider}>
                    <TableCell className="font-medium">{entry.provider}</TableCell>
                    <TableCell className="tabular-nums">{formatAmount(entry.billed)}</TableCell>
                    <TableCell className="tabular-nums">{formatAmount(entry.recorded)}</TableCell>
                    <TableCell>
                      <Badge variant={TONE_BADGE[MATCH_TONE[entry.status]]}>{MATCH_LABEL[entry.status]}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>

        <Card className="flex flex-col gap-3 p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-base font-semibold">Worth doing</h2>
            <Link
              href={migratedHref("recommendations")}
              className="text-sm text-primary underline-offset-4 hover:underline"
            >
              All recommendations
            </Link>
          </div>
          {data.recommendations.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing needs attention for this period</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {data.recommendations.map((card) => (
                <li key={card.rule_id} className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium">{card.title}</p>
                    <p className="text-xs uppercase text-muted-foreground">{card.kind}</p>
                  </div>
                  {/* No figure at all when there is nothing honest to show, rather than a zero */}
                  {card.figure !== null && (
                    <p className="whitespace-nowrap text-sm tabular-nums">{formatAmount(card.figure)}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="flex flex-col gap-3 p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold">How fresh this is</h2>
          <Link
            href={migratedHref("provider-apis")}
            className="text-sm text-primary underline-offset-4 hover:underline"
          >
            Provider APIs
          </Link>
        </div>
        {data.freshness.length === 0 ? (
          <p className="text-sm text-muted-foreground">No source has reported yet</p>
        ) : (
          <div className="flex flex-wrap gap-x-8 gap-y-2">
            {data.freshness.map((entry) => (
              <p key={entry.source} className="text-sm">
                <span className="text-muted-foreground">{entry.source}: </span>
                {formatSynced(entry.last_sync_at)}
              </p>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
