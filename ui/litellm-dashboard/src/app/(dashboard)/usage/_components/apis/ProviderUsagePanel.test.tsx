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

    render(<ProviderUsagePanel />);

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

    render(<ProviderUsagePanel />);

    expect(screen.getByText("Summary for openai over 30 days")).toBeInTheDocument();
  });

  it("switches the summary to the provider chosen in the picker", async () => {
    const user = userEvent.setup();
    useProviderConnections.mockReturnValue({
      data: [connection("openai", "OpenAI"), connection("anthropic", "Anthropic")],
      isLoading: false,
      error: null,
    });

    render(<ProviderUsagePanel />);
    await user.click(screen.getByRole("tab", { name: "Anthropic" }));

    expect(await screen.findByText("Summary for anthropic over 30 days")).toBeInTheDocument();
  });

  it("shows a plain message rather than an empty picker when this build has no provider connector yet", () => {
    useProviderConnections.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<ProviderUsagePanel />);

    expect(screen.getByText("This build reads no provider billing APIs")).toBeInTheDocument();
  });

  it("shows an error message rather than a blank picker when the provider list fails to load", () => {
    useProviderConnections.mockReturnValue({ data: undefined, isLoading: false, error: new Error("network") });

    render(<ProviderUsagePanel />);

    expect(screen.getByText("Could not read the provider list")).toBeInTheDocument();
  });
});
