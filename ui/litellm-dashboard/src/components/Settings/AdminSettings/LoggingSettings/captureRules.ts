/**
 * Per-team and per-provider rules for whether a request's prompt and response are stored.
 *
 * Three states, not two. "Follow the default" has to stay distinct from "never capture", or
 * an exclusion silently reverts to whatever the gateway default happens to be later. The
 * backend reads the same distinction: a missing key falls through, an explicit false does not.
 */

export type CaptureRule = "default" | "capture" | "exclude";

/** A rule table as it is stored in general_settings: subject -> boolean. */
export type CaptureTable = Record<string, boolean>;

export interface CaptureSubject {
  /** What the rule is written against: a team id or alias, or a provider name. */
  readonly id: string;
  /** What the operator sees. Falls back to the id when there is no friendlier name. */
  readonly label: string;
}

/** The rule currently in force for one subject. */
export const ruleFor = (table: CaptureTable | undefined, id: string): CaptureRule => {
  const stored = table?.[id];
  if (stored === true) return "capture";
  if (stored === false) return "exclude";
  return "default";
};

/**
 * The table with one subject's rule changed.
 *
 * Choosing "default" removes the key rather than storing null, so the saved config contains
 * only real decisions and reads the same as one written by hand.
 */
export const withRule = (table: CaptureTable | undefined, id: string, rule: CaptureRule): CaptureTable => {
  const next: CaptureTable = { ...(table ?? {}) };
  if (rule === "default") {
    delete next[id];
    return next;
  }
  next[id] = rule === "capture";
  return next;
};

/** Whether any explicit rule exists, so the UI can say "no overrides" honestly. */
export const hasOverrides = (table: CaptureTable | undefined): boolean => Object.keys(table ?? {}).length > 0;

/**
 * What a subject's rule resolves to once precedence is applied, for the "Effective" column.
 *
 * Mirrors the backend's order: team, then provider, then the gateway default. Kept here so
 * the screen can show the outcome rather than making someone work it out from three tables.
 */
export const effectiveForTeam = (
  teamTable: CaptureTable | undefined,
  teamId: string,
  teamAlias: string | undefined,
  globalDefault: boolean,
): boolean => {
  const byId = teamTable?.[teamId];
  if (typeof byId === "boolean") return byId;
  if (teamAlias !== undefined) {
    const byAlias = teamTable?.[teamAlias];
    if (typeof byAlias === "boolean") return byAlias;
  }
  return globalDefault;
};

export const effectiveForProvider = (
  providerTable: CaptureTable | undefined,
  provider: string,
  globalDefault: boolean,
): boolean => {
  const stored = providerTable?.[provider];
  return typeof stored === "boolean" ? stored : globalDefault;
};

/** Drop rules for subjects that no longer exist, so deleting a team does not leave a rule behind. */
export const withoutUnknownSubjects = (table: CaptureTable | undefined, knownIds: readonly string[]): CaptureTable => {
  const known = new Set(knownIds);
  return Object.fromEntries(Object.entries(table ?? {}).filter(([id]) => known.has(id)));
};

/**
 * Rows whose name contains the search text, case-insensitively.
 *
 * Filtering only hides rows. Rules live in the table rather than in what is rendered, so a
 * rule set on a team that is currently filtered out is still saved untouched.
 */
export const filterByName = <T>(items: readonly T[], nameOf: (item: T) => string, search: string): T[] => {
  const needle = search.trim().toLowerCase();
  if (needle === "") return [...items];
  return items.filter((item) => nameOf(item).toLowerCase().includes(needle));
};
