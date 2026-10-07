import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { useProviderSyncHistory } = vi.hoisted(() => ({ useProviderSyncHistory: vi.fn() }));
vi.mock("@/app/(dashboard)/hooks/providerApis/useProviderSyncHistory", () => ({ useProviderSyncHistory }));

import SyncHistoryTab from "./SyncHistoryTab";

const row = (overrides: Record<string, unknown> = {}) => ({
  provider: "openai",
  credential_name: "prod",
  started_at: "2026-09-16T09:00:00+00:00",
  finished_at: "2026-09-16T09:00:04+00:00",
  outcome: "fetched",
  facts_written: 12,
  window_start: "2026-09-15T09:00:00+00:00",
  window_end: "2026-09-16T09:00:00+00:00",
  detail: null,
  ...overrides,
});

describe("SyncHistoryTab", () => {
  it("says nothing has run yet rather than showing an empty table", () => {
    useProviderSyncHistory.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<SyncHistoryTab provider="openai" />);

    expect(screen.getByText(/no sync has run yet/i)).toBeInTheDocument();
  });

  it("shows how many rows a run brought back", () => {
    useProviderSyncHistory.mockReturnValue({ data: [row()], isLoading: false, error: null });

    render(<SyncHistoryTab provider="openai" />);

    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("prod")).toBeInTheDocument();
  });

  it("shows the reason a run failed", () => {
    // A history that records only 'failed' leaves the customer exactly as stuck as before.
    useProviderSyncHistory.mockReturnValue({
      data: [row({ outcome: "failed", facts_written: 0, detail: "openai refused credential prod" })],
      isLoading: false,
      error: null,
    });

    render(<SyncHistoryTab provider="openai" />);

    expect(screen.getByText("openai refused credential prod")).toBeInTheDocument();
  });

  it("shows an outcome it does not recognise plainly, not as a calm success", () => {
    // A build one release behind the backend can see a new outcome value. Blanking the badge or
    // colouring it like a routine fetch would hide exactly the run a human needs to notice.
    useProviderSyncHistory.mockReturnValue({
      data: [row({ outcome: "delayed_retry" })],
      isLoading: false,
      error: null,
    });

    render(<SyncHistoryTab provider="openai" />);

    const badge = screen.getByText("delayed_retry");
    expect(badge).toHaveClass("text-destructive");
  });
});
