import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen, testQueryClient } from "../../../../../tests/test-utils";
import ModelPricingTab from "./ModelPricingTab";

const mockModelPatchCall = vi.hoisted(() => vi.fn());
const mockUseModelsInfo = vi.hoisted(() => vi.fn());

vi.mock("@/components/networking", () => ({
  modelPatchCall: mockModelPatchCall,
}));

vi.mock("../../hooks/models/useModels", () => ({
  useModelsInfo: mockUseModelsInfo,
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "tok", userRole: "Admin", userId: "u1" }),
}));

/** Priced by the built-in list, editable because it lives in the database. */
const mapPriced = {
  model_name: "openrouter/openai/gpt-4o-mini",
  model_info: { id: "m1", db_model: true, input_cost_per_token: 0.00000015, output_cost_per_token: 0.0000006 },
  litellm_params: {},
};

/** Overridden in the config file, so read-only through the API. */
const configPriced = {
  model_name: "anthropic-haiku-4-5",
  model_info: { id: "m2", db_model: false },
  litellm_params: { input_cost_per_token: 0.000001, output_cost_per_token: 0.000005 },
};

const loaded = (models: object[] = [mapPriced, configPriced]) => ({
  data: { data: models },
  isLoading: false,
  isError: false,
});

const inputFor = (model: string) => screen.getByLabelText(`Input / 1M for ${model}`);

describe("ModelPricingTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testQueryClient.clear();
    mockUseModelsInfo.mockReturnValue(loaded());
    mockModelPatchCall.mockResolvedValue({ status: "ok" });
  });

  it("shows every model's rates side by side, which is the point of the screen", () => {
    renderWithProviders(<ModelPricingTab />);

    expect(inputFor("openrouter/openai/gpt-4o-mini")).toHaveValue("0.15");
    expect(inputFor("anthropic-haiku-4-5")).toHaveValue("1");
  });

  it("shows rates per million tokens rather than the per-token value stored", () => {
    renderWithProviders(<ModelPricingTab />);

    // Stored as 0.0000006, which is unreadable as a price.
    expect(screen.getByLabelText("Output / 1M for openrouter/openai/gpt-4o-mini")).toHaveValue("0.6");
  });

  it("marks a rate that comes from the built-in list rather than from you", () => {
    renderWithProviders(<ModelPricingTab />);

    expect(screen.getAllByText("from price list").length).toBeGreaterThan(0);
  });

  it("does not mark a rate the deployment sets itself", () => {
    mockUseModelsInfo.mockReturnValue(loaded([configPriced]));
    renderWithProviders(<ModelPricingTab />);

    expect(screen.queryByText("from price list")).not.toBeInTheDocument();
  });

  it("leaves a rate nobody sets blank rather than showing a zero", () => {
    renderWithProviders(<ModelPricingTab />);

    // A zero would read as free, which is a real and very different setting.
    expect(screen.getByLabelText("Cache write / 1M for openrouter/openai/gpt-4o-mini")).toHaveValue("");
  });

  it("disables a config file model, because the API cannot patch it", () => {
    renderWithProviders(<ModelPricingTab />);

    expect(inputFor("anthropic-haiku-4-5")).toBeDisabled();
    expect(screen.getByText("config file")).toBeInTheDocument();
  });

  it("offers no save until something changes", () => {
    renderWithProviders(<ModelPricingTab />);

    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("sends the per-token value the backend stores, not the figure shown", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ModelPricingTab />);

    fireEvent.change(inputFor("openrouter/openai/gpt-4o-mini"), { target: { value: "2" } });
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(mockModelPatchCall).toHaveBeenCalledWith("tok", "m1", {
      litellm_params: { input_cost_per_token: 0.000002, cache_read_input_token_cost: 0.000002 },
    });
  });

  it("leaves rates the user did not touch out of the save", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ModelPricingTab />);

    fireEvent.change(inputFor("openrouter/openai/gpt-4o-mini"), { target: { value: "2" } });
    await user.click(screen.getByRole("button", { name: "Save" }));

    const [, , patch] = mockModelPatchCall.mock.calls[0];
    expect(patch.litellm_params).not.toHaveProperty("output_cost_per_token");
  });

  it("clears an override by sending an explicit null", async () => {
    const user = userEvent.setup();
    mockUseModelsInfo.mockReturnValue(loaded([{ ...mapPriced, litellm_params: { output_cost_per_token: 0.000005 } }]));
    renderWithProviders(<ModelPricingTab />);

    fireEvent.change(screen.getByLabelText("Output / 1M for openrouter/openai/gpt-4o-mini"), {
      target: { value: "" },
    });
    await user.click(screen.getByRole("button", { name: "Save" }));

    const [, , patch] = mockModelPatchCall.mock.calls[0];
    expect(patch.litellm_params.output_cost_per_token).toBeNull();
  });

  it("refuses to save a rate that is not a number", () => {
    renderWithProviders(<ModelPricingTab />);

    fireEvent.change(inputFor("openrouter/openai/gpt-4o-mini"), { target: { value: "cheap" } });

    expect(screen.getByText("Must be a number")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("refuses a usage rate on a PTU deployment, which already paid for throughput", () => {
    // No rates of its own, so only the one typed below can conflict.
    mockUseModelsInfo.mockReturnValue(
      loaded([{ ...mapPriced, model_info: { id: "m1", db_model: true, ptu_count: 15 }, litellm_params: {} }]),
    );
    renderWithProviders(<ModelPricingTab />);

    fireEvent.change(inputFor("openrouter/openai/gpt-4o-mini"), { target: { value: "3" } });

    expect(
      screen.getByText("A PTU deployment bills by reserved capacity, so this cost must be 0 or blank"),
    ).toBeInTheDocument();
  });

  it("puts an edit back the way it was on reset", () => {
    renderWithProviders(<ModelPricingTab />);

    const input = inputFor("openrouter/openai/gpt-4o-mini");
    fireEvent.change(input, { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    expect(input).toHaveValue("0.15");
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("edits one model without disturbing another", () => {
    mockUseModelsInfo.mockReturnValue(
      loaded([mapPriced, { ...mapPriced, model_name: "second", model_info: { id: "m9", db_model: true } }]),
    );
    renderWithProviders(<ModelPricingTab />);

    fireEvent.change(inputFor("second"), { target: { value: "7" } });

    expect(inputFor("openrouter/openai/gpt-4o-mini")).toHaveValue("0.15");
    expect(screen.getAllByRole("button", { name: "Save" })).toHaveLength(1);
  });

  it("says so when the models cannot be loaded", () => {
    mockUseModelsInfo.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    renderWithProviders(<ModelPricingTab />);

    expect(screen.getByText("Could not load the models.")).toBeInTheDocument();
  });

  it("says so when there are no models rather than showing an empty table", () => {
    mockUseModelsInfo.mockReturnValue(loaded([]));
    renderWithProviders(<ModelPricingTab />);

    expect(screen.getByText("No models configured.")).toBeInTheDocument();
  });
});
