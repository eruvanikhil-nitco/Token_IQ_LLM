import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UserToolsPanel from "./UserToolsPanel";
import type { ToolConnection } from "@/components/networking";

const toolConnectionsCall = vi.fn();
const syncHistoryCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  toolConnectionsCall: (...args: unknown[]) => toolConnectionsCall(...args),
  providerSyncHistoryCall: (...args: unknown[]) => syncHistoryCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const tool = (over: Partial<ToolConnection> = {}): ToolConnection => ({
  tool: "claude_code",
  display_name: "Claude Code",
  state: "not_connected",
  accounts: [],
  verified_against_real_account: false,
  fetches: {
    endpoint: "Claude Code Usage Report",
    endpoint_url: "https://api.anthropic.com/v1/organizations/usage_report/claude_code",
    what_it_gives: "Per person per day, an estimated cost and token count for each model they used.",
    what_it_cannot_give:
      "When Claude Code is billed to your Anthropic API organisation, that money is already on the Anthropic bill this product reads.",
    backfill_note: "There is no first-connection backfill yet.",
    verification_note: "This connector has never run against a real account.",
  },
  ...over,
});

const renderPanel = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <UserToolsPanel />
    </QueryClientProvider>,
  );
};

describe("UserToolsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    syncHistoryCall.mockResolvedValue({ rows: [] });
  });

  it("shows a tab per tool", async () => {
    toolConnectionsCall.mockResolvedValue({
      tools: [tool(), tool({ tool: "cursor", display_name: "Cursor" })],
    });
    renderPanel();

    expect(await screen.findByRole("tab", { name: /claude code/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /cursor/i })).toBeInTheDocument();
  });

  it("puts what a tool cannot tell us on the first screen, not buried in a tab", async () => {
    /* Two of the three tools cannot report what a reader assumes. Finding that out months
       later from a wrong total is the failure this line exists to prevent. */
    toolConnectionsCall.mockResolvedValue({ tools: [tool()] });
    renderPanel();

    expect(await screen.findByText(/already on the anthropic bill/i)).toBeInTheDocument();
  });

  it("says plainly that a tool has never met a real account", async () => {
    toolConnectionsCall.mockResolvedValue({ tools: [tool()] });
    renderPanel();

    expect(await screen.findByText(/never run against a real account/i)).toBeInTheDocument();
  });

  it("tells an admin with no credential what to do next", async () => {
    toolConnectionsCall.mockResolvedValue({ tools: [tool()] });
    renderPanel();

    expect(await screen.findByRole("link", { name: /llm provider credentials/i })).toHaveAttribute(
      "href",
      expect.stringContaining("llm-provider-credentials"),
    );
  });

  it("shows how many rows an account has actually stored", async () => {
    toolConnectionsCall.mockResolvedValue({
      tools: [
        tool({
          state: "healthy",
          verified_against_real_account: true,
          accounts: [
            {
              credential_name: "acme",
              state: "healthy",
              detail: null,
              last_sync_at: "2026-09-28T09:00:00+00:00",
              last_outcome: "fetched",
              rows_stored: 42,
            },
          ],
        }),
      ],
    });
    renderPanel();

    expect(await screen.findByText("acme")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("shows the endpoint and the limits together on What We Fetch", async () => {
    const user = userEvent.setup();
    toolConnectionsCall.mockResolvedValue({ tools: [tool()] });
    renderPanel();

    await user.click(await screen.findByRole("tab", { name: "What We Fetch" }));

    expect(await screen.findByText(/usage_report\/claude_code/)).toBeInTheDocument();
    expect(screen.getByText(/no first-connection backfill/i)).toBeInTheDocument();
  });

  it("says so when the tools cannot be read at all", async () => {
    toolConnectionsCall.mockRejectedValue(new Error("nope"));
    renderPanel();

    expect(await screen.findByText(/could not read user tool connections/i)).toBeInTheDocument();
  });
});
