import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConnectionTab from "./ConnectionTab";
import type { ProviderConnection } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";

const probeCall = vi.fn();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  probeProviderBillingCall: (...args: unknown[]) => probeCall(...args),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "sk-test", userRole: "proxy_admin" }),
}));

const renderTab = (value: ProviderConnection) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConnectionTab connection={value} />
    </QueryClientProvider>,
  );
};

const connection = (overrides: Partial<ProviderConnection> = {}): ProviderConnection => ({
  provider: "openai",
  display_name: "OpenAI",
  state: "healthy",
  accounts: [
    {
      credential_name: "prod",
      state: "healthy",
      detail: null,
      last_sync_at: "2026-09-16T09:00:00+00:00",
      last_outcome: "fetched",
      facts_stored: 42,
    },
  ],
  fetches: {
    endpoint: "Organization Costs",
    endpoint_url: "https://api.openai.com/v1/organization/costs",
    grain: "day",
    refresh_seconds: 300,
    window_hours: 24,
    delay_note: "Recent days can still change.",
    history_note: "There is no first-connection backfill yet.",
  },
  ...overrides,
});

describe("ConnectionTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("tells an admin with no credential what to do next", () => {
    renderTab(connection({ state: "not_connected", accounts: [] }));

    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /llm provider credentials/i })).toHaveAttribute(
      "href",
      expect.stringContaining("llm-provider-credentials"),
    );
  });

  it("shows the provider's own reason on a failing account", () => {
    // Without the reason the customer knows only that something is wrong, which is the state
    // they were already in before this page existed.
    renderTab(
      connection({
        state: "needs_attention",
        accounts: [
          {
            credential_name: "staging",
            state: "needs_attention",
            detail: "openai refused credential staging",
            last_sync_at: "2026-09-16T09:00:00+00:00",
            last_outcome: "failed",
            facts_stored: 0,
          },
        ],
      }),
    );

    expect(screen.getByText("openai refused credential staging")).toBeInTheDocument();
  });

  it("lists every account separately", () => {
    renderTab(
      connection({
        accounts: [
          { credential_name: "prod", state: "healthy", detail: null, last_sync_at: null, last_outcome: null, facts_stored: 42 },
          { credential_name: "staging", state: "healthy", detail: null, last_sync_at: null, last_outcome: null, facts_stored: 7 },
        ],
      }),
    );

    expect(screen.getByText("prod")).toBeInTheDocument();
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("says the keys are only ever read from", () => {
    renderTab(connection());

    expect(screen.getByText("Read-only")).toBeInTheDocument();
    // Pin the substantive clause, not just the word "read-only": a copy regression that reversed
    // the sentence's meaning would still contain "read-only" and pass a looser assertion.
    expect(screen.getByText(/keys stored here/i)).toHaveTextContent("cannot send traffic or spend money");
  });
});

describe("ConnectionTab, testing a connection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not call the provider until an admin asks it to", () => {
    renderTab(connection());

    expect(probeCall).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /test the openai connection/i })).toBeInTheDocument();
  });

  it("probes the provider whose tab this is", async () => {
    const user = userEvent.setup();
    probeCall.mockResolvedValue({
      provider: "openai",
      credential_name: "prod",
      outcome: "fetched",
      facts_found: 4,
      sample_cost: "0.42",
      detail: null,
    });
    renderTab(connection());

    await user.click(screen.getByRole("button", { name: /test the openai connection/i }));

    expect(probeCall).toHaveBeenCalledWith("sk-test", "openai");
    expect(await screen.findByText(/4 cost rows/)).toBeInTheDocument();
    expect(screen.getByText(/0\.42/)).toBeInTheDocument();
  });

  it("repeats the provider's own reason rather than a generic failure", async () => {
    /* The point of this button is telling someone which of a wrong key, a missing entitlement
       or an outage they have. A generic message throws that away. */
    const user = userEvent.setup();
    probeCall.mockResolvedValue({
      provider: "openai",
      credential_name: "prod",
      outcome: "failed",
      facts_found: 0,
      sample_cost: null,
      detail: "openai refused credential prod (retryable=False)",
    });
    renderTab(connection());

    await user.click(screen.getByRole("button", { name: /test the openai connection/i }));

    expect(await screen.findByText("openai refused credential prod (retryable=False)")).toBeInTheDocument();
  });

  it("separates a key that works but has no spend from a key that does not work", async () => {
    const user = userEvent.setup();
    probeCall.mockResolvedValue({
      provider: "openai",
      credential_name: "prod",
      outcome: "fetched",
      facts_found: 0,
      sample_cost: null,
      detail: "The provider answered but reported nothing in this window.",
    });
    renderTab(connection());

    await user.click(screen.getByRole("button", { name: /test the openai connection/i }));

    expect(await screen.findByText(/reported no cost in this window/i)).toBeInTheDocument();
  });

  it("says the test itself could not run when the request fails", async () => {
    const user = userEvent.setup();
    probeCall.mockRejectedValue(new Error("network down"));
    renderTab(connection());

    await user.click(screen.getByRole("button", { name: /test the openai connection/i }));

    expect(await screen.findByText(/could not be run/i)).toBeInTheDocument();
  });
});
