import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, testQueryClient } from "../../../../../tests/test-utils";
import ProviderModelsTable from "./ProviderModelsTable";

const mockModelHubCall = vi.hoisted(() => vi.fn());
const mockProviderModelUsageCall = vi.hoisted(() => vi.fn());

vi.mock("@/components/networking", () => ({
  modelHubCall: mockModelHubCall,
  providerModelUsageCall: mockProviderModelUsageCall,
  getProxyBaseUrl: vi.fn(() => "http://localhost:4000"),
}));

const models = [
  {
    model_group: "openrouter/openai/gpt-4o",
    providers: ["openrouter"],
    mode: "chat",
    max_input_tokens: 128000,
    input_cost_per_token: 2.5e-6,
    output_cost_per_token: 1e-5,
    supports_vision: true,
    supports_function_calling: true,
    supports_parallel_function_calling: false,
    is_public_model_group: false,
  },
  {
    model_group: "anthropic/claude-haiku",
    providers: ["anthropic"],
    mode: "chat",
    max_input_tokens: 200000,
    input_cost_per_token: 2.5e-7,
    output_cost_per_token: 1.25e-6,
    supports_vision: false,
    supports_function_calling: true,
    supports_parallel_function_calling: false,
    is_public_model_group: false,
  },
];

const usage = {
  range: "week",
  days: 7,
  start_date: "2026-09-02",
  usage: [
    {
      model_group: "openrouter/openai/gpt-4o",
      providers: ["openrouter"],
      requests: 17,
      tokens: 1313,
      spend: 0.0057425,
    },
    // Real case: requests with no spend, because only the provider prices this model.
    { model_group: "anthropic/claude-haiku", providers: ["anthropic"], requests: 0, tokens: 0, spend: 0 },
  ],
};

describe("ProviderModelsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // testQueryClient is a module-level singleton with staleTime Infinity, so a later
    // test would otherwise read the previous test's cached response.
    testQueryClient.clear();
    mockModelHubCall.mockResolvedValue({ data: models });
    mockProviderModelUsageCall.mockResolvedValue(usage);
  });

  it("lists every model when no provider is selected", async () => {
    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider={null} />);

    expect(await screen.findByText("openrouter/openai/gpt-4o")).toBeInTheDocument();
    expect(screen.getByText("anthropic/claude-haiku")).toBeInTheDocument();
  });

  it("narrows to the selected provider", async () => {
    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider="anthropic" />);

    expect(await screen.findByText("anthropic/claude-haiku")).toBeInTheDocument();
    expect(screen.queryByText("openrouter/openai/gpt-4o")).not.toBeInTheDocument();
  });

  it("shows requests, tokens and spend for a model with traffic", async () => {
    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider="openrouter" />);

    expect(await screen.findByText("17 req")).toBeInTheDocument();
    expect(screen.getByText(/1,313 tokens/)).toBeInTheDocument();
  });

  it("shows a dash, not zeros, for a model with no traffic in the range", async () => {
    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider="anthropic" />);

    await screen.findByText("anthropic/claude-haiku");
    expect(screen.queryByText("0 req")).not.toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("defaults the range to this week and asks the API for it", async () => {
    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider={null} />);

    await screen.findByText("openrouter/openai/gpt-4o");
    expect(mockProviderModelUsageCall).toHaveBeenCalledWith("tok", "week");
  });

  it("refetches usage for the range the operator picks", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider={null} />);

    await screen.findByText("openrouter/openai/gpt-4o");
    await user.selectOptions(screen.getByLabelText("Usage range"), "month");

    expect(mockProviderModelUsageCall).toHaveBeenCalledWith("tok", "month");
  });

  it("offers only whole-day ranges, never a rolling 24 hours", async () => {
    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider={null} />);

    await screen.findByText("openrouter/openai/gpt-4o");
    const options = screen.getByLabelText("Usage range").textContent ?? "";
    expect(options).toContain("Today");
    expect(options).toContain("This week");
    expect(options).toContain("This month");
    expect(options).not.toMatch(/24/);
  });

  it("still renders the table when usage cannot be fetched", async () => {
    mockProviderModelUsageCall.mockRejectedValue(new Error("usage down"));

    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider={null} />);

    // The model list is the point of the table; a usage outage must not blank it.
    expect(await screen.findByText("openrouter/openai/gpt-4o")).toBeInTheDocument();
  });

  it("lists a model that recorded traffic but is no longer configured", async () => {
    mockProviderModelUsageCall.mockResolvedValue({
      ...usage,
      usage: [
        ...usage.usage,
        {
          model_group: "openrouter/openai/gpt-4o-mini",
          providers: ["openrouter"],
          requests: 3,
          tokens: 40,
          spend: 0.0001,
        },
      ],
    });

    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider={null} />);

    // It is absent from the configured model list, so the old table fetched its usage and
    // then threw the row away, hiding spend that really happened.
    expect(await screen.findByText("openrouter/openai/gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText("3 req")).toBeInTheDocument();
  });

  it("files an unconfigured model under the provider that served it", async () => {
    mockProviderModelUsageCall.mockResolvedValue({
      ...usage,
      usage: [
        {
          model_group: "openrouter/openai/gpt-4o-mini",
          providers: ["openrouter"],
          requests: 3,
          tokens: 40,
          spend: 0.0001,
        },
      ],
    });

    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider="anthropic" />);

    await screen.findByText("anthropic/claude-haiku");
    expect(screen.queryByText("openrouter/openai/gpt-4o-mini")).not.toBeInTheDocument();
  });

  it("names the filtered provider when it has no models", async () => {
    mockModelHubCall.mockResolvedValue({ data: [] });

    renderWithProviders(<ProviderModelsTable accessToken="tok" selectedProvider="bedrock" />);

    expect(await screen.findByText("No models configured for bedrock, and none recorded traffic.")).toBeInTheDocument();
  });
});
