import { describe, expect, it } from "vitest";

import { accountRows, recordsHeld, type ConnectionLike } from "./accountRows";

/**
 * The Accounts tab is the first screen to list provider accounts and tool accounts together, which
 * is where the counting rule gets broken by accident. It is safe here only because neither endpoint
 * returns money: an account carries its health, when it last synced and how many records are
 * stored. `recordsHeld` therefore totals records, and the label has to say so, because a number on
 * this page that reads as money would be the two kinds added together.
 */

const provider = (over: Partial<ConnectionLike> = {}): ConnectionLike => ({
  key: "openai",
  display_name: "OpenAI",
  state: "healthy",
  accounts: [
    { credential_name: "acme-live", state: "healthy", detail: null, last_sync_at: "2026-10-10T09:00:00Z", last_outcome: "fetched", records_stored: 120 },
  ],
  ...over,
});

const tool = (over: Partial<ConnectionLike> = {}): ConnectionLike => ({
  key: "claude_code",
  display_name: "Claude Code",
  state: "healthy",
  accounts: [
    { credential_name: "acme-cc", state: "healthy", detail: null, last_sync_at: "2026-10-10T08:00:00Z", last_outcome: "fetched", records_stored: 30 },
  ],
  ...over,
});

describe("one table over both kinds of account", () => {
  it("gives every account its own row", () => {
    const rows = accountRows({ providers: [provider()], tools: [tool()] });

    expect(rows).toHaveLength(2);
  });

  it("says which kind each row is, because the two mean different things", () => {
    // A provider account's records come off a bill. A tool account's do not, and nothing on this
    // page should let the two be read as the same sort of number.
    const rows = accountRows({ providers: [provider()], tools: [tool()] });

    expect(rows.map((r) => r.kind)).toEqual(["AI provider", "AI tool"]);
  });

  it("carries the source and the account name separately", () => {
    const [row] = accountRows({ providers: [provider()], tools: [] });

    expect(row.source).toBe("OpenAI");
    expect(row.account).toBe("acme-live");
  });

  it("lists a connection with several accounts once per account", () => {
    const two = provider({
      accounts: [
        { credential_name: "acme-live", state: "healthy", detail: null, last_sync_at: null, last_outcome: null, records_stored: 1 },
        { credential_name: "acme-sandbox", state: "needs_attention", detail: "401", last_sync_at: null, last_outcome: null, records_stored: 0 },
      ],
    });

    expect(accountRows({ providers: [two], tools: [] }).map((r) => r.account)).toEqual([
      "acme-live",
      "acme-sandbox",
    ]);
  });

  it("still lists a connection that has no account yet", () => {
    // A provider supported but not connected is the row a customer needs most: it is the one
    // telling them cost is missing. Dropping it would make an unconnected provider invisible.
    const rows = accountRows({ providers: [provider({ accounts: [] })], tools: [] });

    expect(rows).toHaveLength(1);
    expect(rows[0].account).toBeNull();
    expect(rows[0].source).toBe("OpenAI");
  });

  it("keeps each account's own state rather than the connection's", () => {
    const mixed = provider({
      state: "healthy",
      accounts: [
        { credential_name: "a", state: "needs_attention", detail: "401", last_sync_at: null, last_outcome: null, records_stored: 0 },
      ],
    });

    expect(accountRows({ providers: [mixed], tools: [] })[0].state).toBe("needs_attention");
  });

  it("falls back to the connection's state for a row that has no account", () => {
    const rows = accountRows({ providers: [provider({ state: "not_connected", accounts: [] })], tools: [] });

    expect(rows[0].state).toBe("not_connected");
  });

  it("puts providers before tools, so the two kinds do not interleave", () => {
    const rows = accountRows({ providers: [provider()], tools: [tool(), tool({ key: "cursor", display_name: "Cursor" })] });

    expect(rows.map((r) => r.kind)).toEqual(["AI provider", "AI tool", "AI tool"]);
  });

  it("returns nothing when nothing is connected or supported", () => {
    expect(accountRows({ providers: [], tools: [] })).toEqual([]);
  });
});

describe("the only total on the tab", () => {
  it("counts records, not money", () => {
    // 120 provider records and 30 tool records. Adding them is safe precisely because they are
    // records; the same sum over billed cost and attributed cost would be the counting-rule break.
    expect(recordsHeld(accountRows({ providers: [provider()], tools: [tool()] }))).toBe(150);
  });

  it("treats a connection with no account as holding nothing", () => {
    expect(recordsHeld(accountRows({ providers: [provider({ accounts: [] })], tools: [] }))).toBe(0);
  });

  it("is zero when there is nothing to count", () => {
    expect(recordsHeld([])).toBe(0);
  });
});
