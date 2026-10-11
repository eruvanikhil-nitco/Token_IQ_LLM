import { describe, expect, it } from "vitest";

import {
  cleanChecks,
  coverageFigure,
  issueRow,
  issueRows,
  lastDataAt,
  sourceHealth,
  sourceRollup,
  unknownChecks,
  type CoverageLike,
  type IssueLike,
} from "./overviewRows";
import type { AccountRow } from "./accountRows";

/**
 * Data Sources > Overview answers "Can the data be trusted?", so every figure here fails in the
 * same direction when it is wrong: towards reassurance. A fraction that counts unconnected sources
 * as failures, a clean check that cannot be told apart from one nobody ran, a Fix link to a page
 * this build does not have. Those are what these assert.
 */

const row = (over: Partial<AccountRow> = {}): AccountRow => ({
  id: "AI provider:openai:acme-live",
  kind: "AI provider",
  source: "OpenAI",
  sourceKey: "openai",
  account: "acme-live",
  state: "healthy",
  detail: null,
  lastSyncAt: "2026-10-10T09:00:00Z",
  lastOutcome: "fetched",
  recordsStored: 120,
  ...over,
});

const NO_ACCOUNT: Partial<AccountRow> = { account: null, state: "not_connected", lastSyncAt: null, recordsStored: 0 };

const unconnected = (over: Partial<AccountRow> = {}): AccountRow => row({ ...NO_ACCOUNT, ...over });

describe("how healthy the sources are", () => {
  it("counts the healthy accounts out of the connected ones", () => {
    const health = sourceHealth([row(), row({ id: "b", state: "needs_attention" }), row({ id: "c" })]);

    const expected = { connected: 3, healthy: 2, needsAttention: 1, notConnected: 0 };

    expect(health).toEqual(expected);
  });

  it("keeps a source nobody connected out of the fraction", () => {
    // Inside the denominator, a new installation with one working provider reads "1 of 9 healthy",
    // which describes a broken system rather than an empty one.
    const health = sourceHealth([row(), unconnected({ id: "b" }), unconnected({ id: "c" })]);

    expect(health.connected).toBe(1);
    expect(health.healthy).toBe(1);
    expect(health.notConnected).toBe(2);
  });

  it("does not count a source waiting for its first data as needing attention", () => {
    const health = sourceHealth([row({ state: "waiting_for_first_data" })]);

    expect(health.needsAttention).toBe(0);
    expect(health.healthy).toBe(0);
  });

  it("reads zero connected when nothing is connected at all", () => {
    const health = sourceHealth([unconnected()]);

    expect(health.connected).toBe(0);
    expect(health.healthy).toBe(0);
  });
});

describe("when data last arrived", () => {
  it("takes the freshest sync across every source", () => {
    const at = lastDataAt([
      row({ lastSyncAt: "2026-10-01T09:00:00Z" }),
      row({ id: "b", lastSyncAt: "2026-10-10T09:00:00Z" }),
      row({ id: "c", lastSyncAt: "2026-10-05T09:00:00Z" }),
    ]);

    expect(at).toBe("2026-10-10T09:00:00Z");
  });

  it("ignores a source that has never synced rather than reporting it as the freshest", () => {
    expect(lastDataAt([row({ lastSyncAt: null }), row({ id: "b", lastSyncAt: "2026-10-02T09:00:00Z" })])).toBe(
      "2026-10-02T09:00:00Z",
    );
  });

  it("says nothing has arrived when nothing has", () => {
    expect(lastDataAt([row({ lastSyncAt: null }), unconnected({ id: "b" })])).toBeNull();
  });

  it("ignores a timestamp it cannot read instead of returning it as the answer", () => {
    // A NaN date sorts as neither greater nor smaller, so without the filter it can win by
    // position and the card then shows the raw string as the time data last arrived.
    expect(lastDataAt([row({ lastSyncAt: "not a date" }), row({ id: "b", lastSyncAt: "2026-10-04T09:00:00Z" })])).toBe(
      "2026-10-04T09:00:00Z",
    );
  });
});

describe("the roll-up by kind", () => {
  it("summarises each kind separately", () => {
    const failingProvider: Partial<AccountRow> = {
      id: "b",
      state: "needs_attention",
      recordsStored: 50,
      lastSyncAt: "2026-10-11T09:00:00Z",
    };
    const claudeCode: Partial<AccountRow> = {
      id: "c",
      kind: "AI tool",
      source: "Claude Code",
      recordsStored: 30,
      lastSyncAt: "2026-10-09T09:00:00Z",
    };
    const expected = [
      {
        kind: "AI provider",
        connected: 2,
        available: 0,
        needsAttention: 1,
        recordsStored: 170,
        lastDataAt: "2026-10-11T09:00:00Z",
      },
      {
        kind: "AI tool",
        connected: 1,
        available: 0,
        needsAttention: 0,
        recordsStored: 30,
        lastDataAt: "2026-10-09T09:00:00Z",
      },
    ];

    expect(sourceRollup([row(), row(failingProvider), row(claudeCode)])).toEqual(expected);
  });

  it("does not invent a kind nothing in the data mentions", () => {
    // Agent platforms, cloud billing exports and custom sources are in the blueprint and have no
    // connector yet. A row saying "Agent platforms: not connected" implies one could be connected.
    const kinds = sourceRollup([row()]).map((entry) => entry.kind);

    expect(kinds).toEqual(["AI provider"]);
  });

  it("counts a supported source with no account as available rather than connected", () => {
    const [providers] = sourceRollup([row(), unconnected({ id: "b" })]);

    expect(providers.connected).toBe(1);
    expect(providers.available).toBe(1);
  });

  it("gives an empty list when there are no rows at all", () => {
    expect(sourceRollup([])).toEqual([]);
  });
});

describe("one data quality check as a row", () => {
  const routed = (page: string) => (page === "ledger" ? "/ui/ledger" : null);

  const measured = (count: number): IssueLike => ({
    kind: "measured",
    key: "missing_invoices",
    title: "Periods with no invoice",
    fix_on: "ledger",
    count,
  });

  it("asks for action when the count is above zero, and says how many", () => {
    const result = issueRow(measured(3), routed);

    expect(result.status).toBe("needs_action");
    expect(result.detail).toContain("3");
    expect(result.fixHref).toBe("/ui/ledger");
  });

  it("calls a measured zero clear rather than hiding it", () => {
    // A check that ran and found nothing is the good news on this tab. Dropped from the list, the
    // tab looks identical whether the check ran or was never built.
    const result = issueRow(measured(0), routed);

    expect(result.status).toBe("clean");
    expect(result.detail).toBe("None found");
  });

  it("offers no Fix link on a clear check, because there is nothing to go and fix", () => {
    expect(issueRow(measured(0), routed).fixHref).toBeNull();
  });

  it("keeps an unmeasurable check apart from a clear one and carries its reason", () => {
    const unmatchedPeople: IssueLike = {
      kind: "unmeasurable",
      key: "unmatched_people",
      title: "People not matched across accounts",
      fix_on: "ledger",
      reason: "Needs directory sync, which is not built yet",
    };

    const result = issueRow(unmatchedPeople, routed);

    expect(result.status).toBe("unknown");
    expect(result.status).not.toBe("clean");
    expect(result.detail).toContain("directory sync");
  });

  it("offers no Fix link on an unmeasurable check, even when the page it names exists", () => {
    // The reason says the thing that would answer it is not built. A Fix link to a page where that
    // fix does not exist yet is the dead end the raw records action avoids on an empty row.
    const unmatchedPeople: IssueLike = {
      kind: "unmeasurable",
      key: "unmatched_people",
      title: "People not matched across accounts",
      fix_on: "ledger",
      reason: "Needs directory sync, which is not built yet",
    };

    expect(issueRow(unmatchedPeople, routed).fixHref).toBeNull();
  });

  it("offers no Fix link to a page this build does not route", () => {
    // The backend names the page that fixes each issue. A link to one that does not exist lands the
    // reader on a missing page, which is worse than a row that only states the problem.
    const result = issueRow({ ...measured(2), fix_on: "a-page-that-does-not-exist" }, routed);

    expect(result.status).toBe("needs_action");
    expect(result.fixHref).toBeNull();
  });

  it("keeps the order the backend sent, so the list does not reshuffle as counts change", () => {
    const sent: IssueLike[] = [measured(0), { ...measured(1), key: "second" }, { ...measured(2), key: "third" }];

    expect(issueRows(sent, routed).map((entry) => entry.key)).toEqual(["missing_invoices", "second", "third"]);
  });
});

describe("what the checks add up to", () => {
  const routed = () => "/ui/ledger";
  const checks = issueRows(
    [
      { kind: "measured", key: "a", title: "A", fix_on: "ledger", count: 2 },
      { kind: "measured", key: "b", title: "B", fix_on: "ledger", count: 0 },
      { kind: "measured", key: "c", title: "C", fix_on: "ledger", count: 0 },
      { kind: "unmeasurable", key: "d", title: "D", fix_on: "ledger", reason: "No directory yet" },
    ],
    routed,
  );

  it("counts the checks that came back clear", () => {
    expect(cleanChecks(checks)).toBe(2);
  });

  it("counts the ones nobody can answer separately from both", () => {
    // Not a problem and not reassurance. Folded into either, the tab stops being honest about the
    // part of the question nothing has looked at.
    expect(unknownChecks(checks)).toBe(1);
    expect(cleanChecks(checks) + unknownChecks(checks)).toBe(3);
  });
});

describe("the invoice coverage figure", () => {
  const covered = (billed: number, invoiced: number): CoverageLike => ({
    kind: "covered",
    providers_billed: billed,
    providers_invoiced: invoiced,
  });

  it("reads as a fraction of the providers that billed", () => {
    expect(coverageFigure(covered(6, 5)).figure).toBe("5 of 6");
  });

  it("says every provider is covered when none is missing", () => {
    const result = coverageFigure(covered(3, 3));

    expect(result.figure).toBe("3 of 3");
    expect(result.detail).toContain("Every provider");
  });

  it("names how many billed with nothing to check against", () => {
    expect(coverageFigure(covered(6, 4)).detail).toContain("2 providers");
  });

  it("says it in the singular for one", () => {
    expect(coverageFigure(covered(1, 0)).detail).toContain("1 provider billed");
  });

  it("gives a period nobody billed in a sentence rather than a fraction", () => {
    // "0 of 0" reads as perfect coverage or as total failure depending on the card, and a period in
    // which nobody billed is neither.
    const result = coverageFigure({ kind: "nothing_billed" });

    expect(result.figure).not.toContain("0 of 0");
    expect(result.figure).toBe("Nothing billed");
  });
});
