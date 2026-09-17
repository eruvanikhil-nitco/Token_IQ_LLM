import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ProviderRawFact, ProviderUsageRawResponse } from "@/components/networking";

const { useProviderUsageRaw } = vi.hoisted(() => ({ useProviderUsageRaw: vi.fn() }));
vi.mock("@/app/(dashboard)/hooks/providerUsage/useProviderUsageRaw", () => ({ useProviderUsageRaw }));

import RawDataView from "./RawDataView";

const row = (overrides: Partial<ProviderRawFact> = {}): ProviderRawFact => ({
  bucket_start: "2026-09-16T12:40:50.477000+00:00",
  grain: "request",
  evidence: "reconciled",
  credential_name: "openrouter-billing",
  model: "openai/gpt-4o-mini",
  provider_request_id: "gen-1789562236-kKqVw1BljrOCreiAVfES",
  provider_api_key_id: null,
  billed_cost: "0.00001365",
  billing_currency: "USD",
  input_tokens: 55,
  output_tokens: 9,
  cached_input_tokens: null,
  cache_write_tokens: null,
  raw: null,
  fetched_at: "2026-09-16T12:40:51.847000+00:00",
  ...overrides,
});

const page = (rows: ProviderRawFact[], nextBefore: string | null = null): ProviderUsageRawResponse => ({
  provider: "openrouter",
  rows,
  next_before: nextBefore,
});

describe("RawDataView", () => {
  it("shows a loading state rather than a blank panel while the request is in flight", () => {
    useProviderUsageRaw.mockReturnValue({ data: undefined, isLoading: true, error: null });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);

    expect(screen.getByText(/loading raw usage/i)).toBeInTheDocument();
  });

  it("shows an error message rather than a blank panel when the request fails", () => {
    useProviderUsageRaw.mockReturnValue({ data: undefined, isLoading: false, error: new Error("network") });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);

    expect(screen.getByText("Could not read raw usage for this provider")).toBeInTheDocument();
  });

  it("shows a meaningful empty-window message and no table when no facts have synced", () => {
    useProviderUsageRaw.mockReturnValue({ data: page([]), isLoading: false, error: null });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);

    expect(screen.getByText("No usage has synced yet for OpenRouter.", { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(
      screen.getByText("Service tier, region, and per-user attribution are not collected by this build, for any provider."),
    ).toBeInTheDocument();
  });

  it("renders one row per fact with its model, account, evidence and exact token counts", () => {
    useProviderUsageRaw.mockReturnValue({
      data: page([row({ model: "openai/gpt-4o-mini", credential_name: "openrouter-billing", evidence: "reconciled" })]),
      isLoading: false,
      error: null,
    });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);

    expect(screen.getByText("openai/gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("openrouter-billing")).toBeInTheDocument();
    expect(screen.getByText("Reconciled")).toBeInTheDocument();
    expect(screen.getByText("in 55, out 9")).toBeInTheDocument();
  });

  it("shows the billed cost as the exact digit string, never rounded or converted to a number", () => {
    useProviderUsageRaw.mockReturnValue({
      data: page([row({ billed_cost: "0.000123456789", billing_currency: "USD" })]),
      isLoading: false,
      error: null,
    });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);

    expect(screen.getByText("0.000123456789 USD")).toBeInTheDocument();
  });

  it("reveals the provider's payload verbatim, keys included, when a row expands", () => {
    useProviderUsageRaw.mockReturnValue({
      data: page([row({ raw: { id: "gen-123", usage: { prompt_tokens: 55, completion_tokens: 9 } } })]),
      isLoading: false,
      error: null,
    });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);
    fireEvent.click(screen.getByRole("button", { name: /show payload/i }));

    expect(screen.getByText(/"id": "gen-123"/)).toBeInTheDocument();
    expect(screen.getByText(/"prompt_tokens": 55/)).toBeInTheDocument();
    expect(screen.getByText(/"completion_tokens": 9/)).toBeInTheDocument();
  });

  it("says payload capture started later, not that data was lost, when a row has no stored payload", () => {
    useProviderUsageRaw.mockReturnValue({ data: page([row({ raw: null })]), isLoading: false, error: null });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);
    fireEvent.click(screen.getByRole("button", { name: /show payload/i }));

    expect(screen.getByText("No payload was stored for this row. Payload capture began after this row was fetched, so nothing was lost.")).toBeInTheDocument();
    expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/failed/i)).not.toBeInTheDocument();
  });

  it("hides the payload again on a second click of the same toggle", () => {
    useProviderUsageRaw.mockReturnValue({ data: page([row({ raw: { id: "gen-123" } })]), isLoading: false, error: null });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);
    const toggle = screen.getByRole("button", { name: /show payload/i });
    fireEvent.click(toggle);
    expect(screen.getByText(/"id": "gen-123"/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /hide payload/i }));
    expect(screen.queryByText(/"id": "gen-123"/)).not.toBeInTheDocument();
  });

  it("does not offer to load older rows when the backend reports no further page", () => {
    useProviderUsageRaw.mockReturnValue({ data: page([row()], null), isLoading: false, error: null });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);

    expect(screen.queryByRole("button", { name: /load older rows/i })).not.toBeInTheDocument();
  });

  it("loads the next page of rows on the provider's own opaque cursor when asked for older rows", async () => {
    const firstPage = page([row({ model: "openai/gpt-4o-mini" })], "cursor-1");
    const secondPage = page([row({ model: "anthropic/claude-3-haiku" })], null);
    useProviderUsageRaw.mockImplementation((_provider: string, _limit: number, before: string | null) =>
      before === null
        ? { data: firstPage, isLoading: false, error: null }
        : { data: secondPage, isLoading: false, error: null },
    );

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);
    expect(screen.getByText("openai/gpt-4o-mini")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /load older rows/i }));

    expect(await screen.findByText("anthropic/claude-3-haiku")).toBeInTheDocument();
    expect(screen.queryByText("openai/gpt-4o-mini")).not.toBeInTheDocument();
    expect(useProviderUsageRaw).toHaveBeenLastCalledWith("openrouter", 50, "cursor-1");
  });

  it("names a field this provider left unreported across every row in the current page", () => {
    const populatedExceptApiKey = { provider_api_key_id: null, cached_input_tokens: 12, cache_write_tokens: 4 };
    useProviderUsageRaw.mockReturnValue({
      data: page([row(populatedExceptApiKey), row(populatedExceptApiKey)]),
      isLoading: false,
      error: null,
    });

    render(<RawDataView provider="openrouter" displayName="OpenRouter" />);

    expect(screen.getByText("This provider did not report API key for any row in this window.")).toBeInTheDocument();
  });
});
