import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ConnectionTab from "./ConnectionTab";
import type { ProviderConnection } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";

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
  it("tells an admin with no credential what to do next", () => {
    render(<ConnectionTab connection={connection({ state: "not_connected", accounts: [] })} />);

    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /llm provider credentials/i })).toHaveAttribute(
      "href",
      expect.stringContaining("llm-provider-credentials"),
    );
  });

  it("shows the provider's own reason on a failing account", () => {
    // Without the reason the customer knows only that something is wrong, which is the state
    // they were already in before this page existed.
    render(
      <ConnectionTab
        connection={connection({
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
        })}
      />,
    );

    expect(screen.getByText("openai refused credential staging")).toBeInTheDocument();
  });

  it("lists every account separately", () => {
    render(
      <ConnectionTab
        connection={connection({
          accounts: [
            { credential_name: "prod", state: "healthy", detail: null, last_sync_at: null, last_outcome: null, facts_stored: 42 },
            { credential_name: "staging", state: "healthy", detail: null, last_sync_at: null, last_outcome: null, facts_stored: 7 },
          ],
        })}
      />,
    );

    expect(screen.getByText("prod")).toBeInTheDocument();
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("says the keys are only ever read from", () => {
    render(<ConnectionTab connection={connection()} />);

    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
  });
});
