import { describe, expect, it } from "vitest";

import { methodsFor } from "./connectCatalogue";
import { canSubmit, connectPayload, needsExternalId, resultMessage } from "./connectSubmit";
import type { ConnectAccountResponse } from "@/components/networking";

/**
 * What leaves the dialog and what comes back.
 *
 * The payload is where a field the server would drop, or a field the server must never accept,
 * would slip through. The result is where a failed test could read as a success, which is the one
 * failure that matters: the dialog's whole promise is that nothing is saved until the test passes,
 * so a dialog that says "connected" when it did not is the promise broken in the only place a
 * customer can see it.
 */

const ROLE = methodsFor("aws")[0];
const KEYS = methodsFor("aws")[1];
const ADMIN_KEY = methodsFor("claudeall")[0];

describe("what the dialog sends", () => {
  it("sends the vendor key, not the provider", () => {
    // The server owns that translation. A dialog that guessed it would be the second mapping,
    // and the two would drift.
    const draft = {
      vendorKey: "aws",
      accountName: "aws-main",
      method: ROLE,
      values: { role_arn: "arn:aws:iam::123456789012:role/token-iq-read-only" },
    };
    const payload = connectPayload(draft);

    expect(payload.vendor).toBe("aws");
    expect(payload.credential_name).toBe("aws-main");
  });

  it("sends only the fields this method asks for", () => {
    // Switching method tabs leaves the other tab's values in form state. Sent, they would be a
    // field the server has to drop, and a provider credential carrying a stale secret.
    const draft = {
      vendorKey: "aws",
      accountName: "aws-main",
      method: ROLE,
      values: { role_arn: "arn:aws:iam::123456789012:role/x", aws_secret_access_key: "left over" },
    };
    const payload = connectPayload(draft);

    expect(Object.keys(payload.values ?? {})).toEqual(["role_arn"]);
  });

  it("never sends an external ID, even if one is in the form state", () => {
    const draft = {
      vendorKey: "aws",
      accountName: "aws-main",
      method: ROLE,
      values: { role_arn: "arn:aws:iam::123456789012:role/x", external_id: "tiq-mine" },
    };
    const payload = connectPayload(draft);

    expect(payload.values).not.toHaveProperty("external_id");
  });

  it("trims what was pasted", () => {
    // A key copied out of a console arrives with a trailing newline, and the provider answers a
    // key with a newline in it the same way it answers a wrong key.
    const draft = {
      vendorKey: "claudeall",
      accountName: "anthropic-main",
      method: ADMIN_KEY,
      values: { api_key: "  sk-ant-admin01-x\n" },
    };
    const payload = connectPayload(draft);

    expect(payload.values?.api_key).toBe("sk-ant-admin01-x");
  });

  it("drops an optional field left empty rather than sending a blank", () => {
    const draft = {
      vendorKey: "aws",
      accountName: "aws-main",
      method: KEYS,
      values: { aws_access_key_id: "AKIA", aws_secret_access_key: "s", service_name: "   " },
    };
    const payload = connectPayload(draft);

    expect(payload.values).not.toHaveProperty("service_name");
  });

  it("trims the account name, which becomes the stored name", () => {
    const draft = { vendorKey: "aws", accountName: " aws-main ", method: ROLE, values: {} };
    const payload = connectPayload(draft);

    expect(payload.credential_name).toBe("aws-main");
  });
});

describe("whether the dialog can submit yet", () => {
  const filledRole = { role_arn: "arn:aws:iam::123456789012:role/token-iq-read-only" };

  it("can once the name, the required fields and the external ID are all there", () => {
    const readiness = { accountName: "aws-main", method: ROLE, values: filledRole, externalId: "tiq-x" };

    expect(canSubmit(readiness)).toBe(true);
  });

  it("cannot without an account name", () => {
    const readiness = { accountName: "", method: ROLE, values: filledRole, externalId: "tiq-x" };

    expect(canSubmit(readiness)).toBe(false);
  });

  it("cannot with a required field empty", () => {
    const readiness = { accountName: "aws-main", method: ROLE, values: {}, externalId: "tiq-x" };

    expect(canSubmit(readiness)).toBe(false);
  });

  it("cannot before the external ID has been issued", () => {
    // The role has to be created against that exact value first. Submitting earlier stores a role
    // ARN whose trust policy names an external ID nobody has, and every sync then fails.
    const readiness = { accountName: "aws-main", method: ROLE, values: filledRole, externalId: null };

    expect(canSubmit(readiness)).toBe(false);
  });

  it("does not wait for an external ID on a method that has none", () => {
    const readiness = {
      accountName: "anthropic-main",
      method: ADMIN_KEY,
      values: { api_key: "sk-ant-admin01-x" },
      externalId: null,
    };

    expect(canSubmit(readiness)).toBe(true);
  });

  it("cannot while a field carries a value the provider would refuse", () => {
    // Knowable here, so the dialog does not spend a live provider call on a key it can already
    // see is the wrong kind.
    const readiness = {
      accountName: "anthropic-main",
      method: ADMIN_KEY,
      values: { api_key: "sk-ant-api03-ordinary" },
      externalId: null,
    };

    expect(canSubmit(readiness)).toBe(false);
  });

  it("cannot on a method this build does not offer", () => {
    const signIn = methodsFor("azure").find((method) => !method.available)!;

    const readiness = { accountName: "azure-main", method: signIn, values: {}, externalId: null };

    expect(canSubmit(readiness)).toBe(false);
  });
});

describe("which methods need an external ID first", () => {
  it("the role method does", () => {
    expect(needsExternalId(ROLE)).toBe(true);
  });

  it("the access keys method does not", () => {
    expect(needsExternalId(KEYS)).toBe(false);
  });

  it("an admin key does not", () => {
    expect(needsExternalId(ADMIN_KEY)).toBe(false);
  });
});

describe("what the dialog says came back", () => {
  it("reports a stored account as connected", () => {
    const response: ConnectAccountResponse = {
      kind: "connected",
      provider: "bedrock",
      credential_name: "aws-main",
      facts_found: 12,
    };

    const message = resultMessage(response);

    expect(message.tone).toBe("connected");
    expect(message.text).toContain("12");
  });

  it("says a connection that answered with nothing is still connected", () => {
    // It is. A new account with no spend in the window has a working connection, and calling it
    // a failure would send somebody to debug a key that works.
    const response: ConnectAccountResponse = {
      kind: "connected",
      provider: "bedrock",
      credential_name: "aws-main",
      facts_found: 0,
    };

    const message = resultMessage(response);

    expect(message.tone).toBe("connected");
    expect(message.text).toMatch(/nothing|no cost/i);
  });

  it("reports a failed test as not saved, in those words", () => {
    // The promise the dialog made. "Something went wrong" leaves somebody wondering whether a
    // half-made connection is now sitting in their account.
    const response: ConnectAccountResponse = {
      kind: "test_failed",
      provider: "bedrock",
      credential_name: "aws-main",
      outcome: "failed",
      detail: "cost explorer: AccessDenied",
    };

    const message = resultMessage(response);

    expect(message.tone).toBe("failed");
    expect(message.text).toMatch(/not saved|nothing was saved/i);
  });

  it("carries the provider's own words, which name the field that is wrong", () => {
    const response: ConnectAccountResponse = {
      kind: "test_failed",
      provider: "bedrock",
      credential_name: "aws-main",
      outcome: "failed",
      detail: "cost explorer: AccessDenied",
    };

    expect(resultMessage(response).text).toContain("AccessDenied");
  });

  it("still says what happened when the provider said nothing", () => {
    const response: ConnectAccountResponse = {
      kind: "test_failed",
      provider: "bedrock",
      credential_name: "aws-main",
      outcome: "failed",
      detail: null,
    };

    const message = resultMessage(response);

    expect(message.tone).toBe("failed");
    expect(message.text.length).toBeGreaterThan(0);
  });

  it("is never readable as connected when the test failed", () => {
    const response: ConnectAccountResponse = {
      kind: "test_failed",
      provider: "bedrock",
      credential_name: "aws-main",
      outcome: "no_connector",
      detail: null,
    };

    expect(resultMessage(response).tone).not.toBe("connected");
  });
});
