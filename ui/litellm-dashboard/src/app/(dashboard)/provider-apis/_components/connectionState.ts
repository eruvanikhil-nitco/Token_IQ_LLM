import type { ProviderConnectionState } from "@/components/networking";

export type ConnectionState = ProviderConnectionState;

const STATE_LABELS: Record<ConnectionState, string> = {
  not_connected: "Not connected",
  waiting_for_first_data: "Waiting for first data",
  healthy: "Healthy",
  needs_attention: "Needs attention",
};

const STATE_VARIANTS: Record<ConnectionState, "default" | "secondary" | "destructive" | "outline"> = {
  not_connected: "outline",
  waiting_for_first_data: "secondary",
  healthy: "default",
  needs_attention: "destructive",
};

// state is typed as ConnectionState, but it arrives from the network unvalidated: a build one
// release behind the backend can see a value outside this union. Look it up defensively rather
// than trusting the type, and fail toward "unexpected" (visible, destructive), never toward calm.
export const stateLabel = (state: ConnectionState): string => (state in STATE_LABELS ? STATE_LABELS[state] : state);

export const stateBadgeVariant = (state: ConnectionState): "default" | "secondary" | "destructive" | "outline" =>
  state in STATE_VARIANTS ? STATE_VARIANTS[state] : "destructive";

/**
 * Whether this connector has ever been proved against a live account.
 *
 * Deliberately separate from the health state. A connector can be "Waiting for first data"
 * because nobody has connected a key yet, or because it has never worked anywhere, and those
 * are different problems for whoever has to act. A connector written from a vendor's
 * documentation can be wrong about what that vendor really sends, and only stored rows from a
 * real account settle it.
 */
export const verificationLabel = (verified: boolean): string =>
  verified ? "Proved against a real account" : "Never run against a real account";

export const verificationBadgeVariant = (verified: boolean): "secondary" | "outline" =>
  verified ? "secondary" : "outline";
