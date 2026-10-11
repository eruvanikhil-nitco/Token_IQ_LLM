/**
 * Every connected account as one list, whichever kind it is.
 *
 * The blueprint's Accounts tab is "every connected account: AI providers, AI tools, agent
 * platforms, cloud billing exports and custom sources", each row opening its raw records. Providers
 * and tools are what exists today and their two endpoints return the same shape under different
 * names, so this is where they meet.
 *
 * Neither endpoint returns money, which is why one table over both is safe: an account carries its
 * health, when it last synced, and how many records are stored. The only total on the tab is a
 * record count, and it is named as one.
 */

export type AccountKind = "AI provider" | "AI tool";

export interface AccountLike {
  credential_name: string;
  state: string;
  detail: string | null;
  last_sync_at: string | null;
  last_outcome: string | null;
  rows_stored: number;
}

/** What `/provider/connections` and `/tool/connections` have in common, with the key renamed. */
export interface ConnectionLike {
  key: string;
  display_name: string;
  state: string;
  accounts: readonly AccountLike[];
}

export interface AccountRow {
  id: string;
  kind: AccountKind;
  source: string;
  sourceKey: string;
  /** Null for a source that is supported but has no account yet. */
  account: string | null;
  state: string;
  detail: string | null;
  lastSyncAt: string | null;
  lastOutcome: string | null;
  recordsStored: number;
}

function rowsFor(connection: ConnectionLike, kind: AccountKind): readonly AccountRow[] {
  if (connection.accounts.length === 0) {
    // A supported source with nothing connected is the row a customer most needs to see: it is the
    // one saying this provider's cost is missing. Dropping it would hide that.
    return [
      {
        id: `${kind}:${connection.key}`,
        kind,
        source: connection.display_name,
        sourceKey: connection.key,
        account: null,
        state: connection.state,
        detail: null,
        lastSyncAt: null,
        lastOutcome: null,
        recordsStored: 0,
      },
    ];
  }
  return connection.accounts.map((account) => ({
    id: `${kind}:${connection.key}:${account.credential_name}`,
    kind,
    source: connection.display_name,
    sourceKey: connection.key,
    account: account.credential_name,
    // The account's own state, not the connection's: one failing account among three healthy ones
    // is the thing worth seeing, and the connection's roll-up hides it.
    state: account.state,
    detail: account.detail,
    lastSyncAt: account.last_sync_at,
    lastOutcome: account.last_outcome,
    recordsStored: account.rows_stored,
  }));
}

export function accountRows(sources: {
  providers: readonly ConnectionLike[];
  tools: readonly ConnectionLike[];
}): readonly AccountRow[] {
  return [
    ...sources.providers.flatMap((connection) => rowsFor(connection, "AI provider")),
    ...sources.tools.flatMap((connection) => rowsFor(connection, "AI tool")),
  ];
}

/**
 * How many raw records are held across these rows.
 *
 * Records, deliberately, and the column and any summary built on it must say "records". A total
 * across provider and tool rows is only safe because this counts stored rows; the same sum over a
 * provider's billed cost and the gateway's attributed cost is the one addition the counting rule
 * forbids.
 */
export function recordsHeld(rows: readonly AccountRow[]): number {
  return rows.reduce((total, row) => total + row.recordsStored, 0);
}
