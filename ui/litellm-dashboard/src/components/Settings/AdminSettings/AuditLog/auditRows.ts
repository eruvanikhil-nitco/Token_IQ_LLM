/**
 * Presentation helpers for the audit trail.
 *
 * The endpoint already does the hard part: it returns which fields changed, with secrets
 * redacted, rather than two raw row snapshots. What is left is naming things the way an
 * operator thinks about them.
 */

export interface FieldChange {
  readonly field: string;
  readonly before: string | null;
  readonly after: string | null;
}

export interface AuditEntry {
  readonly id: string;
  readonly changed_at: string;
  readonly action: string;
  readonly table_name: string;
  readonly object_id: string;
  readonly changed_by: string;
  readonly summary: string;
  readonly changes: readonly FieldChange[];
}

/**
 * Database table names, as the people reading this page would say them.
 *
 * The rows carry `LiteLLM_VerificationToken`, which is accurate and means nothing to someone
 * asking who deleted a key.
 */
const OBJECT_LABELS: Readonly<Record<string, string>> = {
  LiteLLM_VerificationToken: "Virtual key",
  LiteLLM_TeamTable: "Team",
  LiteLLM_UserTable: "User",
  LiteLLM_ProxyModelTable: "Model",
  LiteLLM_OrganizationTable: "Organization",
  LiteLLM_TeamMembership: "Team member",
  LiteLLM_CredentialsTable: "Credential",
};

export const objectLabel = (tableName: string): string => OBJECT_LABELS[tableName] ?? tableName;

/** The distinct object kinds present, for the filter, labelled and sorted. */
export const objectKindOptions = (
  entries: readonly AuditEntry[],
): readonly { readonly value: string; readonly label: string }[] =>
  [...new Set(entries.map((entry) => entry.table_name))]
    .map((tableName) => ({ value: tableName, label: objectLabel(tableName) }))
    .sort((a, b) => a.label.localeCompare(b.label));

/**
 * An id shortened for a table cell.
 *
 * Key ids are 64 character hashes and team ids are uuids; neither is readable in full and
 * both are recognisable from their start.
 */
export const shortId = (objectId: string, length = 12): string =>
  objectId.length <= length ? objectId : `${objectId.slice(0, length)}…`;

/** Whether a change is worth expanding, so a row with nothing to show is not clickable. */
export const hasDetail = (entry: AuditEntry): boolean => entry.changes.length > 0;

/** How a value reads when the field did not exist on that side of the change. */
export const renderValue = (value: string | null, action: string): string => {
  if (value !== null) return value;
  return action === "created" ? "not set" : "removed";
};
