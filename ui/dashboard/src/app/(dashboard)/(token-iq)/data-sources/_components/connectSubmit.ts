/**
 * What leaves the connect dialog and what it makes of the answer.
 *
 * Kept away from the rendering because both halves fail in the same direction. A payload carrying
 * a field the current method does not ask for stores a stale secret from a tab the customer backed
 * out of, and a result that reads a failed test as a success breaks the one promise the dialog
 * makes: nothing is saved until the test passes.
 */

import type { ConnectAccountRequest, ConnectAccountResponse } from "@/components/networking";

import { fieldProblem, missingRequiredFields, type ConnectMethod } from "./connectCatalogue";

export interface ConnectDraft {
  vendorKey: string;
  accountName: string;
  method: ConnectMethod;
  values: Readonly<Record<string, string>>;
}

/**
 * The request for this draft.
 *
 * Only the current method's own fields, trimmed, with blanks dropped. The form holds every field
 * the customer has typed across every method tab, so sending the lot would put the other tab's
 * secret into this connection's credential. The external ID is never here: the server resolves it
 * from what it minted, and a value from the browser is one the customer could have chosen.
 */
export function connectPayload(draft: ConnectDraft): ConnectAccountRequest {
  const values = Object.fromEntries(
    draft.method.fields
      .map((field) => [field.name, (draft.values[field.name] ?? "").trim()] as const)
      .filter(([, value]) => value !== ""),
  );
  return { vendor: draft.vendorKey, credential_name: draft.accountName.trim(), values };
}

/** Whether this method's sign-in rests on an external ID that has to exist first. */
export function needsExternalId(method: ConnectMethod): boolean {
  return method.kind === "role";
}

export interface SubmitReadiness {
  accountName: string;
  method: ConnectMethod;
  values: Readonly<Record<string, string>>;
  externalId: string | null;
}

/**
 * Whether there is anything worth testing yet.
 *
 * The external ID gate is the one that matters. The customer's role trusts that exact value, so
 * submitting before one has been issued stores a role ARN whose trust policy names an external ID
 * nobody holds, and every sync afterwards fails with an AccessDenied that points at nothing.
 */
export function canSubmit({ accountName, method, values, externalId }: SubmitReadiness): boolean {
  if (!method.available || accountName.trim() === "") {
    return false;
  }
  if (missingRequiredFields(method, values).length > 0) {
    return false;
  }
  if (needsExternalId(method) && externalId === null) {
    return false;
  }
  return method.fields.every((field) => fieldProblem(field, values[field.name] ?? "") === null);
}

export interface ResultMessage {
  tone: "connected" | "failed";
  text: string;
}

const OUTCOME_LEAD: Readonly<Record<string, string>> = {
  not_configured: "The connection is incomplete",
  no_connector: "This build cannot read that provider's bill",
  failed: "The provider refused the connection",
};

/**
 * What to tell the person who pressed Test and connect.
 *
 * A failure says nothing was saved, in those words. "Something went wrong" leaves somebody
 * wondering whether a half-made connection is now sitting in their provider account, and the
 * answer is always no, which is worth saying.
 */
export function resultMessage(response: ConnectAccountResponse): ResultMessage {
  if (response.kind === "connected") {
    const found =
      response.facts_found === 0
        ? "The provider answered and reported no cost in the last few days, which is normal for a new account"
        : `The provider answered with ${response.facts_found.toLocaleString()} records`;
    return { tone: "connected", text: `${response.credential_name} is connected. ${found}` };
  }
  const lead = OUTCOME_LEAD[response.outcome] ?? "The connection test did not pass";
  const detail = response.detail ? ` ${response.detail}` : "";
  return { tone: "failed", text: `${lead}, so nothing was saved.${detail}` };
}
