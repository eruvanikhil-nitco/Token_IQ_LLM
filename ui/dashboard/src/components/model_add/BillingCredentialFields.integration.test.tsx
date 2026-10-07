import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";

import {
  MountedFormProvider,
  projectMountedValues,
  useMountRegistry,
  type MountedFormValues,
} from "@/components/common_components/MountedFormField";
import BillingCredentialFields from "./BillingCredentialFields";
import type { BillingProvider } from "./credential_form_helpers";

const renderFields = (provider: BillingProvider, isEdit = false) => {
  const onSubmit = vi.fn();
  const Harness: React.FC = () => {
    const form = useForm<MountedFormValues>({ mode: "onChange" });
    const registry = useMountRegistry();
    return (
      <FormProvider {...form}>
        <MountedFormProvider value={{ control: form.control, registry }}>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit(projectMountedValues(registry, form.getValues));
            }}
          >
            <BillingCredentialFields provider={provider} onProviderChange={vi.fn()} isEdit={isEdit} />
            <button type="submit">Save</button>
          </form>
        </MountedFormProvider>
      </FormProvider>
    );
  };
  render(<Harness />);
  return onSubmit;
};

describe("BillingCredentialFields", () => {
  it("asks an Azure admin for the subscription its bill is read from and not for a key", () => {
    renderFields("azure");

    expect(screen.getByLabelText(/Subscription ID/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Admin API key/)).not.toBeInTheDocument();
  });

  it("offers the Azure service name the connector filters Cost Management on", () => {
    renderFields("azure");

    expect(screen.getByLabelText(/Cost Management service name/)).toHaveAttribute("placeholder", "Cognitive Services");
  });

  it("asks a Vertex admin for both halves of the BigQuery billing export", () => {
    renderFields("vertex_ai");

    expect(screen.getByLabelText(/Billing project ID/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Billing export table/)).toBeInTheDocument();
  });

  it("writes what a Vertex admin typed under the keys the connector reads", async () => {
    const onSubmit = renderFields("vertex_ai");

    fireEvent.change(screen.getByLabelText(/Billing project ID/), { target: { value: "my-billing-project" } });
    fireEvent.change(screen.getByLabelText(/Billing export table/), {
      target: { value: "my-billing-project.export_ds.gcp_billing" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      billing_project_id: "my-billing-project",
      billing_export_table: "my-billing-project.export_ds.gcp_billing",
    });
  });

  it("falls back to the generic key field for a stored provider this build does not know", () => {
    renderFields("a-seventh-provider" as BillingProvider);

    expect(screen.getByLabelText(/Admin API key/)).toBeInTheDocument();
  });
});
