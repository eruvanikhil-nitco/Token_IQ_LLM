import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
