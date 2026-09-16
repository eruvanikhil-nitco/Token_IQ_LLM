import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { chooseSelectOption } from "../../../tests/test-utils";
import { Providers } from "../provider_info_helpers";
import { CredentialItem } from "../networking";
import CredentialModal from "./CredentialModal";

vi.mock("../networking", async () => {
  const actual = await vi.importActual("../networking");
  return {
    ...actual,
    getProviderCreateMetadata: vi.fn().mockResolvedValue([
      {
        provider: "OpenAI",
        provider_display_name: Providers.OpenAI,
        litellm_provider: "openai",
        default_model_placeholder: "gpt-3.5-turbo",
        credential_fields: [
          {
            key: "api_key",
            label: "OpenAI API Key",
            field_type: "password",
            required: true,
          },
          {
            key: "api_base",
            label: "API Base",
            field_type: "text",
            placeholder: "https://api.openai.com/v1",
            default_value: "https://api.openai.com/v1",
          },
        ],
      },
      {
        provider: "Anthropic",
        provider_display_name: Providers.Anthropic,
        litellm_provider: "anthropic",
        default_model_placeholder: "claude-3-opus-20240229",
        credential_fields: [
          {
            key: "api_key",
            label: "Anthropic API Key",
            field_type: "password",
            required: true,
          },
        ],
      },
    ]),
  };
});

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

const mockCredential: CredentialItem = {
  credential_name: "test-credential",
  credential_values: {
    api_key: "test-api-key",
    api_base: "https://api.test.com",
  },
  credential_info: {
    custom_llm_provider: Providers.OpenAI,
  },
};

const renderModal = (props: Partial<React.ComponentProps<typeof CredentialModal>> = {}) =>
  render(
    <QueryClientProvider client={createQueryClient()}>
      <CredentialModal open={true} mode="add" onCancel={vi.fn()} onSubmit={vi.fn()} {...props} />
    </QueryClientProvider>,
  );

// The Provider field starts unselected regardless of the internally preselected provider, so
// the admin (and this test) must pick OpenAI, the provider with a declared api_base default
// in the mocked metadata above, before its fields appear. Each option also carries a provider
// logo whose alt text folds into its accessible name, so match on the label text itself
// rather than role name to avoid colliding with "OpenAI Text Completion" and friends.
const chooseProviderWithDefaultApiBase = async () => {
  const user = userEvent.setup();
  await user.click(screen.getByLabelText("Provider:"));
  const options = await screen.findAllByRole("option");
  const openAiOption = options.find((option) => within(option).queryByText("OpenAI", { exact: true }) !== null);
  if (!openAiOption) {
    throw new Error("OpenAI option not found in the provider list");
  }
  await user.click(openAiOption);
  await screen.findByLabelText("API Base");
};

describe("CredentialModal", () => {
  describe("add mode", () => {
    it("renders the add title and an editable credential name", () => {
      renderModal({ mode: "add" });

      expect(screen.getByText("Add New Credential")).toBeInTheDocument();
      expect(screen.getByText("Add Credential")).toBeInTheDocument();
      const nameInput = screen.getByLabelText("Credential Name:") as HTMLInputElement;
      expect(nameInput.value).toBe("");
      expect(nameInput).toBeEnabled();
    });

    it("shows provider-specific fields for the selected provider", async () => {
      renderModal({ mode: "add" });

      await waitFor(() => {
        expect(screen.getByLabelText("OpenAI API Key")).toBeInTheDocument();
        expect(screen.getByPlaceholderText("https://api.openai.com/v1")).toBeInTheDocument();
      });
    });

    it("keeps a provider text field controlled from first render through typing, clearing, and a Purpose switch", async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      renderModal({ mode: "add" });

      const apiBaseInput = (await screen.findByLabelText("API Base")) as HTMLInputElement;
      expect(apiBaseInput).toHaveValue("https://api.openai.com/v1");

      fireEvent.change(apiBaseInput, { target: { value: "https://custom.example.com/v1" } });
      expect(apiBaseInput).toHaveValue("https://custom.example.com/v1");

      fireEvent.change(apiBaseInput, { target: { value: "" } });
      expect(apiBaseInput).toHaveValue("");

      await user.click(screen.getByRole("radio", { name: /Billing access/ }));
      await user.click(screen.getByRole("radio", { name: /Model access/ }));

      // ProviderSpecificFields remounts fresh on this switch, so it reseeds the
      // provider's declared default rather than keeping the cleared value around.
      expect(await screen.findByLabelText("API Base")).toHaveValue("https://api.openai.com/v1");

      const controlledWarnings = consoleErrorSpy.mock.calls.filter((call) =>
        call.some((arg) => typeof arg === "string" && /controlled input/i.test(arg)),
      );
      expect(controlledWarnings).toHaveLength(0);

      consoleErrorSpy.mockRestore();
    });

    it("saves the provider's declared default when the admin does not change it", async () => {
      // The default is shown as if it were part of the credential. A payload without it stores a
      // credential the form implied was complete, and the admin finds out at first use.
      const onSubmit = vi.fn();
      renderModal({ onSubmit });

      await chooseProviderWithDefaultApiBase();
      fireEvent.change(screen.getByLabelText("Credential Name:"), { target: { value: "acct" } });
      fireEvent.change(screen.getByLabelText("OpenAI API Key"), { target: { value: "sk-test" } });
      fireEvent.click(screen.getByRole("button", { name: /Add Credential/ }));

      await waitFor(() =>
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ api_base: "https://api.openai.com/v1" })),
      );
    });
  });

  describe("edit mode", () => {
    it("renders the edit title and update button", () => {
      renderModal({ mode: "edit", existingCredential: mockCredential });

      expect(screen.getByText("Edit Credential")).toBeInTheDocument();
      expect(screen.getByText("Update Credential")).toBeInTheDocument();
    });

    it("prefills the credential name and disables it", async () => {
      renderModal({ mode: "edit", existingCredential: mockCredential });

      await waitFor(() => {
        const nameInput = screen.getByLabelText("Credential Name:") as HTMLInputElement;
        expect(nameInput.value).toBe("test-credential");
        expect(nameInput).toBeDisabled();
      });
    });

    it("disables the name from the mode, not the credential's name value", () => {
      renderModal({
        mode: "edit",
        existingCredential: { ...mockCredential, credential_name: "" },
      });

      expect(screen.getByLabelText("Credential Name:")).toBeDisabled();
    });
  });
});

describe("CredentialModal purpose", () => {
  it("shows only the billing key field when Billing access is chosen", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole("radio", { name: /Billing access/ }));

    expect(screen.getByText(/Read-only/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Admin API key/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/OpenAI API Key/)).not.toBeInTheDocument();
  });

  it("sends the billing values in the shape the panel builds from", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderModal({ onSubmit });

    fireEvent.change(screen.getByLabelText(/Credential Name/), { target: { value: "openai-costs" } });
    await user.click(screen.getByRole("radio", { name: /Billing access/ }));
    fireEvent.change(screen.getByLabelText(/Admin API key/), { target: { value: "sk-admin-test-not-real" } });
    await user.click(screen.getByRole("button", { name: /Add Credential/ }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        credential_name: "openai-costs",
        purpose: "billing_access",
        billing_provider: "openai",
        api_key: "sk-admin-test-not-real",
      }),
    );
  });

  it("asks for the two AWS keys when the billing provider is Amazon Bedrock", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole("radio", { name: /Billing access/ }));
    await chooseSelectOption(user, screen.getByLabelText(/Billing provider/), /Amazon Bedrock/);

    expect(screen.getByLabelText(/AWS access key ID/)).toBeInTheDocument();
    expect(screen.getByLabelText(/AWS secret access key/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Admin API key/)).not.toBeInTheDocument();
  });

  it("clears a typed admin key when switching from one billing provider to another", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole("radio", { name: /Billing access/ }));
    fireEvent.change(screen.getByLabelText(/Admin API key/), { target: { value: "sk-admin-test-not-real" } });

    await chooseSelectOption(user, screen.getByLabelText(/Billing provider/), /Anthropic/);

    expect((screen.getByLabelText(/Admin API key/) as HTMLInputElement).value).toBe("");
  });

  it("clears a model-access key typed before switching to Billing access", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderModal({ onSubmit });

    await waitFor(() => {
      expect(screen.getByLabelText("OpenAI API Key")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText("Credential Name:"), { target: { value: "openai-costs" } });
    fireEvent.change(screen.getByLabelText("OpenAI API Key"), { target: { value: "sk-model-serving-key" } });

    await user.click(screen.getByRole("radio", { name: /Billing access/ }));

    expect((screen.getByLabelText(/Admin API key/) as HTMLInputElement).value).toBe("");

    fireEvent.change(screen.getByLabelText(/Admin API key/), { target: { value: "sk-admin-test-not-real" } });
    await user.click(screen.getByRole("button", { name: /Add Credential/ }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        credential_name: "openai-costs",
        purpose: "billing_access",
        billing_provider: "openai",
        api_key: "sk-admin-test-not-real",
      }),
    );
  });

  it("clears a billing key typed before switching back to Model access", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderModal({ onSubmit });

    await user.click(screen.getByRole("radio", { name: /Billing access/ }));
    fireEvent.change(screen.getByLabelText(/Admin API key/), { target: { value: "sk-admin-test-not-real" } });

    await user.click(screen.getByRole("radio", { name: /Model access/ }));

    await waitFor(() => {
      expect((screen.getByLabelText("OpenAI API Key") as HTMLInputElement).value).toBe("");
    });

    fireEvent.change(screen.getByLabelText("Credential Name:"), { target: { value: "openai-key" } });
    fireEvent.change(screen.getByLabelText("OpenAI API Key"), { target: { value: "sk-model-serving-key" } });
    await user.click(screen.getByRole("button", { name: /Add Credential/ }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    const values = onSubmit.mock.calls[0][0];
    expect(values.api_key).toBe("sk-model-serving-key");
    expect(values).not.toHaveProperty("billing_provider");
  });

  it("opens an existing billing credential without offering to change its purpose or provider", () => {
    renderModal({
      mode: "edit",
      existingCredential: {
        credential_name: "openai-costs",
        credential_values: {},
        credential_info: { purpose: "billing_ingestion", provider: "openai" },
      },
    });

    expect(screen.queryByRole("radio", { name: /Model access/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Leave the key empty to keep the stored one/)).toBeInTheDocument();
  });
});
