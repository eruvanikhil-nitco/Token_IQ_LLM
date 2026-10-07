import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const { useProviderConnections } = vi.hoisted(() => ({ useProviderConnections: vi.fn() }));
vi.mock("@/app/(dashboard)/hooks/providerApis/useProviderConnections", () => ({ useProviderConnections }));

vi.mock("./UsageSummaryView", () => ({
  default: ({ provider, days }: { provider: string; days: number }) => (
    <p>
      Summary for {provider} over {days} days
    </p>
  ),
}));

import ProviderUsagePanel from "./ProviderUsagePanel";

const period = (days: number, endingToday = true) => ({
  from: new Date(Date.now() - days * 24 * 60 * 60 * 1000),
  to: endingToday ? new Date() : new Date("2026-06-30T12:00:00.000Z"),
});

const connection = (provider: string, display_name: string) => ({
  provider,
  display_name,
  state: "healthy",
  accounts: [],
  fetches: {
    endpoint: "",
    endpoint_url: "",
    grain: "request",
    refresh_seconds: 3600,
    window_hours: 24,
    delay_note: "",
    history_note: "",
  },
});

describe("ProviderUsagePanel", () => {
  it("lists only the providers this build can read, and none it cannot", () => {
    useProviderConnections.mockReturnValue({
      data: [
        connection("openai", "OpenAI"),
        connection("anthropic", "Anthropic"),
        connection("bedrock", "Amazon Bedrock"),
        connection("openrouter", "OpenRouter"),
      ],
      isLoading: false,
      error: null,
    });

    render(<ProviderUsagePanel period={period(30)} />);

    expect(screen.getByRole("tab", { name: "OpenAI" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Anthropic" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Amazon Bedrock" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "OpenRouter" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Azure" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Vertex AI" })).not.toBeInTheDocument();
  });

  it("opens on the first provider the backend returns and shows its summary", () => {
    useProviderConnections.mockReturnValue({
      data: [connection("openai", "OpenAI"), connection("anthropic", "Anthropic")],
      isLoading: false,
      error: null,
    });

    render(<ProviderUsagePanel period={period(30)} />);

    expect(screen.getByText("Summary for openai over 30 days")).toBeInTheDocument();
  });

  it("switches the summary to the provider chosen in the picker", async () => {
    const user = userEvent.setup();
    useProviderConnections.mockReturnValue({
      data: [connection("openai", "OpenAI"), connection("anthropic", "Anthropic")],
      isLoading: false,
      error: null,
    });

    render(<ProviderUsagePanel period={period(30)} />);
    await user.click(screen.getByRole("tab", { name: "Anthropic" }));

    expect(await screen.findByText("Summary for anthropic over 30 days")).toBeInTheDocument();
  });

  it("shows a plain message rather than an empty picker when this build has no provider connector yet", () => {
    useProviderConnections.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<ProviderUsagePanel period={period(30)} />);

    expect(screen.getByText("This build reads no provider billing APIs")).toBeInTheDocument();
  });

  it("shows an error message rather than a blank picker when the provider list fails to load", () => {
    useProviderConnections.mockReturnValue({ data: undefined, isLoading: false, error: new Error("network") });

    render(<ProviderUsagePanel period={period(30)} />);

    expect(screen.getByText("Could not read the provider list")).toBeInTheDocument();
  });

  it("reads the period the page chose rather than a window of its own", async () => {
    // The panel asked for a fixed 30 days while the header picker said something else, so the
    // figures on this tab belonged to dates the reader had not asked for and nothing said so.
    useProviderConnections.mockReturnValue({
      data: [connection("openai", "OpenAI")],
      isLoading: false,
      error: null,
    });

    render(<ProviderUsagePanel period={period(7)} />);

    expect(screen.getByText("Summary for openai over 7 days")).toBeInTheDocument();
  });

  it("says so rather than silently serving a window it can reach instead", async () => {
    // This endpoint caps days at 90 and always means "the last N days", exactly like the
    // combined ones, so a longer period or one that does not end today cannot be served.
    useProviderConnections.mockReturnValue({
      data: [connection("openai", "OpenAI")],
      isLoading: false,
      error: null,
    });

    render(<ProviderUsagePanel period={period(200)} />);

    expect(screen.getByRole("status")).toHaveTextContent("90 days");
    expect(screen.getByText("Summary for openai over 90 days")).toBeInTheDocument();
  });

  it("leads with what the figures on this tab are, before any of them", async () => {
    useProviderConnections.mockReturnValue({
      data: [connection("openai", "OpenAI")],
      isLoading: false,
      error: null,
    });

    render(<ProviderUsagePanel period={period(30)} />);

    const claim = screen.getByText(/what the provider itself reported/i);
    const summary = screen.getByText("Summary for openai over 30 days");
    // DOCUMENT_POSITION_FOLLOWING: the claim comes first in the document.
    expect(claim.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
