import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConnectAccountDialog from "./ConnectAccountDialog";

/**
 * Proves the wiring the unit tests on `connectCatalogue` and `connectSubmit` cannot reach: that
 * the external ID comes from the server and is shown rather than asked for, that the name is
 * fixed once it has been issued, and that a failed test says nothing was saved.
 *
 * The shaping is asserted in those two files, which run in milliseconds. What is here is only
 * what needs a real tree.
 */

const connectionExternalIdCall = vi.fn();
const connectAccountCall = vi.fn();
const bedrockRoleTemplateCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  connectionExternalIdCall: (...args: unknown[]) => connectionExternalIdCall(...args),
  connectAccountCall: (...args: unknown[]) => connectAccountCall(...args),
  bedrockRoleTemplateCall: (...args: unknown[]) => bedrockRoleTemplateCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const openCatalogue = async () => {
  const user = userEvent.setup();
  render(<ConnectAccountDialog />);
  await user.click(screen.getByRole("button", { name: "+ Connect account" }));
  return user;
};

const openAwsConfigure = async () => {
  const user = await openCatalogue();
  await user.click(await screen.findByRole("button", { name: /AWS Bedrock/ }));
  await user.click(await screen.findByRole("tab", { name: /Configure/ }));
  return user;
};

const typeName = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  const field = screen.getByLabelText("Account name");
  await user.clear(field);
  await user.type(field, name);
  return field;
};

describe("the connect dialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    connectionExternalIdCall.mockResolvedValue({ kind: "minted", external_id: "tiq-abc123", provider: "bedrock" });
    const connected = { kind: "connected", provider: "bedrock", credential_name: "aws-main", facts_found: 7 };
    connectAccountCall.mockResolvedValue(connected);
    bedrockRoleTemplateCall.mockResolvedValue({ filename: "token-iq-bedrock-role.yaml", template: "Resources: {}" });
  });

  it("offers a tile only for a vendor this build can connect", async () => {
    await openCatalogue();

    expect(await screen.findByRole("button", { name: /AWS Bedrock/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Anthropic/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /GitHub Copilot/ })).not.toBeInTheDocument();
  });

  it("keeps a category with no connector visible, saying why, with nothing to click", async () => {
    // Dropped, the dialog has no answer to "where do I connect Copilot?". Given a tile, it leads
    // to a form whose save cannot succeed.
    await openCatalogue();

    expect(await screen.findByText("AI tool")).toBeInTheDocument();
    expect(screen.getByText(/arrives through the tool connectors/)).toBeInTheDocument();
  });

  it("opens on the Setup guide, which explains each field before the form", async () => {
    const user = await openCatalogue();
    await user.click(await screen.findByRole("button", { name: /AWS Bedrock/ }));

    expect(await screen.findByRole("tab", { name: /Setup guide/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/Each field explained/)).toBeInTheDocument();
  });

  it("opens AWS on the role method rather than on access keys", async () => {
    // The blueprint's recommended method, and the one that stores no secret. Opening on keys
    // would make the least safe option the default.
    const user = await openCatalogue();
    await user.click(await screen.findByRole("button", { name: /AWS Bedrock/ }));

    expect(await screen.findByRole("tab", { name: /IAM role/ })).toHaveAttribute("aria-selected", "true");
  });

  it("names an unbuilt sign-in rather than hiding it", async () => {
    // Hidden, the dialog silently recommends a service principal as though it were the best way
    // in. Named, the reader learns Azure offers better and this build has not got there.
    const user = await openCatalogue();
    await user.click(await screen.findByRole("button", { name: /Microsoft Azure OpenAI/ }));

    const signIn = await screen.findByRole("tab", { name: /Sign in with Microsoft/ });

    expect(signIn).toHaveTextContent("Not built yet");
    expect(signIn).toHaveAttribute("aria-selected", "false");

    await user.click(signIn);

    expect(await screen.findByText(/no sign-in flow yet/)).toBeInTheDocument();
  });

  it("asks the server for the external ID rather than offering a field for it", async () => {
    // The whole security property. A field would let somebody present a value they chose, which
    // is exactly what the external ID exists to prevent.
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");

    expect(screen.queryByLabelText(/External ID/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Get the external ID/ }));

    expect(await screen.findByText("tiq-abc123")).toBeInTheDocument();
    expect(connectionExternalIdCall).toHaveBeenCalledWith("sk-test", "aws", "aws-main");
  });

  it("fixes the account name once an external ID has been issued for it", async () => {
    // The role in the customer's account trusts that exact value, and the value is stored against
    // this name. Renaming afterwards would test a different connection and leave the role they
    // already created pointing at nothing.
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");
    await user.click(screen.getByRole("button", { name: /Get the external ID/ }));

    await screen.findByText("tiq-abc123");

    expect(screen.getByLabelText("Account name")).toBeDisabled();
  });

  it("says when an external ID was issued earlier, so nothing is redone in AWS", async () => {
    const reissued = {
      kind: "already_issued",
      external_id: "tiq-earlier",
      provider: "bedrock",
      issued_at: "2026-10-01T09:00:00+00:00",
    };
    connectionExternalIdCall.mockResolvedValue(reissued);
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");
    await user.click(screen.getByRole("button", { name: /Get the external ID/ }));

    expect(await screen.findByText(/already had an external ID/)).toBeInTheDocument();
  });

  it("will not test a role connection before an external ID exists", async () => {
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");
    await user.type(screen.getByLabelText("Role ARN"), "arn:aws:iam::123456789012:role/token-iq-read-only");

    expect(screen.getByRole("button", { name: "Test and connect" })).toBeDisabled();
  });

  it("sends the vendor key and never an external ID", async () => {
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");
    await user.click(screen.getByRole("button", { name: /Get the external ID/ }));
    await screen.findByText("tiq-abc123");
    await user.type(screen.getByLabelText("Role ARN"), "arn:aws:iam::123456789012:role/token-iq-read-only");
    await user.click(screen.getByRole("button", { name: "Test and connect" }));

    await waitFor(() => {
      expect(connectAccountCall).toHaveBeenCalledWith("sk-test", {
        vendor: "aws",
        credential_name: "aws-main",
        values: { role_arn: "arn:aws:iam::123456789012:role/token-iq-read-only" },
      });
    });
  });

  it("says nothing was saved when the connection test fails", async () => {
    // The promise the dialog makes. Anything vaguer leaves somebody wondering whether a half-made
    // connection is now sitting in their provider account.
    const refused = {
      kind: "test_failed",
      provider: "bedrock",
      credential_name: "aws-main",
      outcome: "failed",
      detail: "cost explorer: AccessDenied",
    };
    connectAccountCall.mockResolvedValue(refused);
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");
    await user.click(screen.getByRole("button", { name: /Get the external ID/ }));
    await screen.findByText("tiq-abc123");
    await user.type(screen.getByLabelText("Role ARN"), "arn:aws:iam::123456789012:role/token-iq-read-only");
    await user.click(screen.getByRole("button", { name: "Test and connect" }));

    expect(await screen.findByText(/nothing was saved/)).toBeInTheDocument();
    expect(screen.getByText(/AccessDenied/)).toBeInTheDocument();
    expect(screen.queryByText(/is connected/)).not.toBeInTheDocument();
  });

  it("says the account is connected when the test passes", async () => {
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");
    await user.click(screen.getByRole("button", { name: /Get the external ID/ }));
    await screen.findByText("tiq-abc123");
    await user.type(screen.getByLabelText("Role ARN"), "arn:aws:iam::123456789012:role/token-iq-read-only");
    await user.click(screen.getByRole("button", { name: "Test and connect" }));

    expect(await screen.findByText(/aws-main is connected/)).toBeInTheDocument();
  });

  it("warns that a key is not an admin key before spending a provider call on it", async () => {
    const user = await openCatalogue();
    await user.click(await screen.findByRole("button", { name: /Anthropic/ }));
    await user.click(await screen.findByRole("tab", { name: /Configure/ }));
    await typeName(user, "anthropic-main");
    await user.type(screen.getByLabelText("Admin key"), "sk-ant-api03-ordinary");

    expect(await screen.findByText(/need an organisation admin key/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test and connect" })).toBeDisabled();
  });

  it("reports a refused request without claiming the account connected", async () => {
    connectAccountCall.mockRejectedValue(new Error("An account named aws-main already exists."));
    const user = await openAwsConfigure();
    await typeName(user, "aws-main");
    await user.click(screen.getByRole("button", { name: /Get the external ID/ }));
    await screen.findByText("tiq-abc123");
    await user.type(screen.getByLabelText("Role ARN"), "arn:aws:iam::123456789012:role/token-iq-read-only");
    await user.click(screen.getByRole("button", { name: "Test and connect" }));

    expect(await screen.findByText(/already exists/)).toBeInTheDocument();
    expect(screen.queryByText(/is connected/)).not.toBeInTheDocument();
  });

  it("offers the template the role method's first step asks for", async () => {
    // Without it the dialog names a template and gives no way to get it, which is the dead end a
    // step one that cannot be followed always is.
    const user = await openAwsConfigure();
    await user.click(screen.getByRole("button", { name: /Download the CloudFormation template/ }));

    await waitFor(() => {
      expect(bedrockRoleTemplateCall).toHaveBeenCalledWith("sk-test");
    });
  });

  it("asks a method with no external ID for nothing but its own fields", async () => {
    const user = await openCatalogue();
    await user.click(await screen.findByRole("button", { name: /OpenRouter/ }));
    await user.click(await screen.findByRole("tab", { name: /Configure/ }));

    const configure = screen.getByRole("tab", { name: /Configure/ });

    expect(configure).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText(/Get the external ID/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("API key")).toBeInTheDocument();
  });

  it("lets a reader jump from a field to its explanation", async () => {
    // The blueprint's "What is this?" link. A form field whose explanation is a tab away is a
    // field somebody fills by guessing.
    const user = await openAwsConfigure();

    await user.click(screen.getByRole("button", { name: "What is Role ARN?" }));

    expect(screen.getByRole("tab", { name: /Setup guide/ })).toHaveAttribute("aria-selected", "true");
  });
});
