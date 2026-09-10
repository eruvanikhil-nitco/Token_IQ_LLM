import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen, testQueryClient } from "../../../../../tests/test-utils";
import ModelLimitsTab from "./ModelLimitsTab";

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

const dbModel = {
  model_name: "openrouter/openai/gpt-4o-mini",
  model_info: { id: "m1", db_model: true },
  litellm_params: { model: "openrouter/openai/gpt-4o-mini", rpm: 60 },
};

const configModel = {
  model_name: "anthropic-haiku-4-5",
  model_info: { id: "m2", db_model: false },
  litellm_params: { model: "anthropic/claude-haiku-4-5" },
};

const loaded = (models: object[] = [dbModel, configModel]) => ({
  data: { data: models },
  isLoading: false,
  isError: false,
});

describe("ModelLimitsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testQueryClient.clear();
    mockUseModelsInfo.mockReturnValue(loaded());
    mockModelPatchCall.mockResolvedValue({ status: "ok" });
  });

  it("shows each model with its current limits", () => {
    renderWithProviders(<ModelLimitsTab />);

    expect(screen.getByText("openrouter/openai/gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByLabelText("Requests / min for openrouter/openai/gpt-4o-mini")).toHaveValue("60");
  });

  it("leaves an unset limit blank rather than showing a zero", () => {
    renderWithProviders(<ModelLimitsTab />);

    // Blank means no limit; a 0 would mean a limit nobody can satisfy.
    expect(screen.getByLabelText("Tokens / min for openrouter/openai/gpt-4o-mini")).toHaveValue("");
  });

  it("disables a config file model, because the API cannot patch it", () => {
    renderWithProviders(<ModelLimitsTab />);

    expect(screen.getByLabelText("Requests / min for anthropic-haiku-4-5")).toBeDisabled();
    expect(screen.getByText("config file")).toBeInTheDocument();
  });

  it("offers no save until something actually changes", () => {
    renderWithProviders(<ModelLimitsTab />);

    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("offers save once a limit is edited", () => {
    renderWithProviders(<ModelLimitsTab />);

    fireEvent.change(screen.getByLabelText("Tokens / min for openrouter/openai/gpt-4o-mini"), {
      target: { value: "100000" },
    });

    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("sends numbers rather than the strings the inputs hold", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ModelLimitsTab />);

    fireEvent.change(screen.getByLabelText("Tokens / min for openrouter/openai/gpt-4o-mini"), {
      target: { value: "100000" },
    });
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(mockModelPatchCall).toHaveBeenCalledWith("tok", "m1", {
      litellm_params: { tpm: 100000, rpm: 60, timeout: null },
    });
  });

  it("sends a cleared limit as null, so clearing one actually clears it", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ModelLimitsTab />);

    fireEvent.change(screen.getByLabelText("Requests / min for openrouter/openai/gpt-4o-mini"), {
      target: { value: "" },
    });
    await user.click(screen.getByRole("button", { name: "Save" }));

    // Omitting it would mean "leave as is" under PATCH, and the limit would survive.
    expect(mockModelPatchCall).toHaveBeenCalledWith("tok", "m1", {
      litellm_params: { tpm: null, rpm: null, timeout: null },
    });
  });

  it("refuses to save a value that is not a number", () => {
    renderWithProviders(<ModelLimitsTab />);

    fireEvent.change(screen.getByLabelText("Requests / min for openrouter/openai/gpt-4o-mini"), {
      target: { value: "sixty" },
    });

    expect(screen.getByText("Must be a number")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("refuses a fractional request limit but allows a fractional timeout", () => {
    renderWithProviders(<ModelLimitsTab />);

    fireEvent.change(screen.getByLabelText("Requests / min for openrouter/openai/gpt-4o-mini"), {
      target: { value: "1.5" },
    });
    expect(screen.getByText("Must be a whole number")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Requests / min for openrouter/openai/gpt-4o-mini"), {
      target: { value: "60" },
    });
    fireEvent.change(screen.getByLabelText("Timeout (s) for openrouter/openai/gpt-4o-mini"), {
      target: { value: "2.5" },
    });

    expect(screen.queryByText("Must be a whole number")).not.toBeInTheDocument();
  });

  it("puts an edit back the way it was on reset", () => {
    renderWithProviders(<ModelLimitsTab />);

    const rpm = screen.getByLabelText("Requests / min for openrouter/openai/gpt-4o-mini");
    fireEvent.change(rpm, { target: { value: "999" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    expect(rpm).toHaveValue("60");
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("edits one model without disturbing another", () => {
    mockUseModelsInfo.mockReturnValue(
      loaded([dbModel, { ...dbModel, model_name: "second", model_info: { id: "m9", db_model: true } }]),
    );
    renderWithProviders(<ModelLimitsTab />);

    fireEvent.change(screen.getByLabelText("Tokens / min for second"), { target: { value: "5" } });

    expect(screen.getByLabelText("Tokens / min for openrouter/openai/gpt-4o-mini")).toHaveValue("");
    expect(screen.getAllByRole("button", { name: "Save" })).toHaveLength(1);
  });

  it("says so when the models cannot be loaded", () => {
    mockUseModelsInfo.mockReturnValue({ data: undefined, isLoading: false, isError: true });

    renderWithProviders(<ModelLimitsTab />);

    expect(screen.getByText("Could not load the models.")).toBeInTheDocument();
  });

  it("says so when there are no models rather than showing an empty table", () => {
    mockUseModelsInfo.mockReturnValue(loaded([]));

    renderWithProviders(<ModelLimitsTab />);

    expect(screen.getByText("No models configured.")).toBeInTheDocument();
  });
});
