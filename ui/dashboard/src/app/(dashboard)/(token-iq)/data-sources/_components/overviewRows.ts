/**
 * What Data Sources > Overview shows, worked out away from the rendering.
 *
 * The tab's question is "Can the data be trusted?", and the blueprint answers it with source
 * health, invoice coverage and the issues to fix. Three of those are arithmetic over the accounts
 * and one comes from `/data-quality`, so the shaping is here and the component only lays it out.
 *
 * Two figures the blueprint's mockup shows are deliberately absent. There is no data quality score,
 * because a single number out of a hundred over four checks, one of which nobody can measure yet,
 * is a figure nobody can trace back to anything: a 92 reads as reassurance on the one tab whose job
 * is to say whether the data can be trusted, and it would read 92 whether or not the unmeasurable
 * quarter was ever built. And there is no money anywhere on the tab, because it lists provider
 * sources and gateway sources in one place, which is where somebody would eventually add a total.
 */

import type { AccountRow } from "./accountRows";

/** The one account state that means somebody has to act. Mirrors the backend's own constant. */
const FAILING_STATE = "needs_attention";
const HEALTHY_STATE = "healthy";

export interface SourceHealth {
  /** Accounts that exist, which is the denominator a reader cares about. */
  connected: number;
  healthy: number;
  needsAttention: number;
  /** Supported sources with no account at all. Not a failure, but the reason cost may be missing. */
  notConnected: number;
}

/**
 * How many connected accounts are healthy, and what the rest are.
 *
 * `not_connected` stays out of the fraction and is reported beside it. Inside the denominator it
 * would make a brand new installation read "0 of 9 healthy", which describes a broken system rather
 * than an empty one, and a customer who has connected one provider deliberately is not failing
 * eight checks.
 */
export function sourceHealth(rows: readonly AccountRow[]): SourceHealth {
  const connected = rows.filter((row) => row.account !== null);
  return {
    connected: connected.length,
    healthy: connected.filter((row) => row.state === HEALTHY_STATE).length,
    needsAttention: connected.filter((row) => row.state === FAILING_STATE).length,
    notConnected: rows.length - connected.length,
  };
}

/**
 * When any source last brought data in, as the ISO string it arrived as.
 *
 * The freshest across every account, because the figure answers "is anything still arriving?".
 * How stale the slowest source is belongs to that source's own row, where there is room to say
 * which one it is.
 */
export function lastDataAt(rows: readonly AccountRow[]): string | null {
  const times = rows
    .map((row) => row.lastSyncAt)
    .filter((at): at is string => at !== null)
    .map((at) => ({ at, ms: new Date(at).getTime() }))
    .filter((entry) => !Number.isNaN(entry.ms));
  if (times.length === 0) {
    return null;
  }
  return times.reduce((freshest, entry) => (entry.ms > freshest.ms ? entry : freshest)).at;
}

export interface SourceRollupRow {
  kind: string;
  /** Sources of this kind that have at least one account. */
  connected: number;
  /** Sources of this kind that exist as connectors but have no account. */
  available: number;
  needsAttention: number;
  recordsStored: number;
  lastDataAt: string | null;
}

/**
 * One row per kind of source, which is how the blueprint's Overview summarises what Accounts lists.
 *
 * Built from the account rows rather than from a second endpoint, so the roll-up cannot disagree
 * with the table it links to. Records, never cost: this sums across provider and tool sources, and
 * the same sum over money is the one addition the counting rule forbids.
 */
export function sourceRollup(rows: readonly AccountRow[]): readonly SourceRollupRow[] {
  const kinds = [...new Set(rows.map((row) => row.kind))];
  return kinds.map((kind) => {
    const own = rows.filter((row) => row.kind === kind);
    const health = sourceHealth(own);
    return {
      kind,
      connected: health.connected,
      available: health.notConnected,
      needsAttention: health.needsAttention,
      recordsStored: own.reduce((total, row) => total + row.recordsStored, 0),
      lastDataAt: lastDataAt(own),
    };
  });
}

export type IssueStatus = "needs_action" | "clean" | "unknown";

export interface IssueRow {
  key: string;
  title: string;
  status: IssueStatus;
  /** What a reader needs to know: how many, or why nobody can say. */
  detail: string;
  /** Where it is fixed, or null when this build routes nowhere for it. */
  fixHref: string | null;
}

/** The subset of the wire issue this needs, so a route map can be injected for testing. */
export interface IssueLike {
  kind: "measured" | "unmeasurable";
  key: string;
  title: string;
  fix_on: string;
  count?: number;
  reason?: string;
}

/**
 * One issue as the tab lists it: what it is, whether it needs action, and where it is fixed.
 *
 * Three statuses, not two. A measured zero is good news and an unmeasurable is not, and collapsing
 * both into "nothing shown here" would leave the tab looking identical whether the check ran or
 * nobody ever built it.
 *
 * Only a check that needs action carries a link. A clear one has nothing to go and fix, and an
 * unmeasurable one cannot be fixed yet by definition. `resolveHref` returns null on top of that for
 * a page this build does not route, because a Fix link landing on a missing page is worse than a row
 * that only states the problem.
 */
export function issueRow(issue: IssueLike, resolveHref: (page: string) => string | null): IssueRow {
  if (issue.kind === "unmeasurable") {
    return {
      key: issue.key,
      title: issue.title,
      status: "unknown",
      detail: issue.reason ?? "Cannot be measured yet",
      // No link, even though the backend names the page this will be fixed on. Nothing has measured
      // it, and the reason says why: the thing that would answer it is not built. A Fix link would
      // send somebody to a page where the fix does not exist yet, which is the dead end the raw
      // records action avoids on a row with no records.
      fixHref: null,
    };
  }
  const fixHref = resolveHref(issue.fix_on);
  const count = issue.count ?? 0;
  return {
    key: issue.key,
    title: issue.title,
    status: count > 0 ? "needs_action" : "clean",
    detail: count > 0 ? `${count.toLocaleString()} to fix` : "None found",
    // A clean check has nothing to go and fix, so it carries no link even though the page exists.
    fixHref: count > 0 ? fixHref : null,
  };
}

export function issueRows(
  issues: readonly IssueLike[],
  resolveHref: (page: string) => string | null,
): readonly IssueRow[] {
  return issues.map((issue) => issueRow(issue, resolveHref));
}

/** How many checks came back clean, which is the part a list of problems alone cannot say. */
export function cleanChecks(rows: readonly IssueRow[]): number {
  return rows.filter((row) => row.status === "clean").length;
}

/** How many questions nobody can answer yet. Neither problems nor reassurance. */
export function unknownChecks(rows: readonly IssueRow[]): number {
  return rows.filter((row) => row.status === "unknown").length;
}

export interface CoverageLike {
  kind: "covered" | "nothing_billed";
  providers_billed?: number;
  providers_invoiced?: number;
}

/**
 * Invoice coverage as the headline reads it, with the two states kept apart.
 *
 * A period in which nobody billed gets a sentence rather than a fraction, because "0 of 0" is read
 * as either perfect coverage or total failure depending on how a card renders it.
 */
export function coverageFigure(coverage: CoverageLike): { figure: string; detail: string } {
  if (coverage.kind === "nothing_billed") {
    return { figure: "Nothing billed", detail: "No provider reported a cost in this period" };
  }
  const billed = coverage.providers_billed ?? 0;
  const invoiced = coverage.providers_invoiced ?? 0;
  return {
    figure: `${invoiced} of ${billed}`,
    detail:
      invoiced === billed
        ? "Every provider that billed has an invoice covering it"
        : `${billed - invoiced} provider${billed - invoiced === 1 ? "" : "s"} billed with no invoice to check against`,
  };
}
