"use client";

import type { ReactElement } from "react";
import { Input } from "@/components/ui/input";
import { SearchSelect } from "@/components/shared/SearchSelect";
import { MountedFormField } from "../common_components/MountedFormField";
import { requiredRule } from "../common_components/formRules";
import { BILLING_PROVIDERS, type BillingProvider } from "./credential_form_helpers";

interface BillingCredentialFieldsProps {
  provider: BillingProvider;
  onProviderChange: (provider: BillingProvider) => void;
  isEdit: boolean;
}

const secretRules = (isEdit: boolean, message: string) =>
  isEdit ? undefined : { validate: { required: requiredRule(message) } };

const ADMIN_KEY_PLACEHOLDER: Partial<Record<BillingProvider, string>> = {
  openai: "sk-admin-...",
  anthropic: "sk-ant-admin...",
};

export default function BillingCredentialFields({ provider, onProviderChange, isEdit }: BillingCredentialFieldsProps) {
  return (
    <div className="flex flex-col gap-4">
      <p className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
        Read-only. This key only reads costs, is stored encrypted, and is never shown again after saving.
        {isEdit ? " Leave the key empty to keep the stored one." : ""}
      </p>

      <MountedFormField label="Billing provider" name="billing_provider" required defaultValue={provider}>
        {(control) => (
          <SearchSelect
            inputId={control.id}
            placeholder="Select a provider"
            options={BILLING_PROVIDERS.map((option) => ({ label: option.label, value: option.value }))}
            value={provider}
            disabled={isEdit}
            onValueChange={(value) => {
              control.onChange(value);
              onProviderChange(value as BillingProvider);
            }}
          />
        )}
      </MountedFormField>

      {FIELDS_BY_PROVIDER[provider](isEdit)}
    </div>
  );
}

const textField = (name: string, label: string, isEdit: boolean, opts?: { password?: boolean; placeholder?: string }) => (
  <MountedFormField key={name} label={label} name={name} required={!isEdit} rules={secretRules(isEdit, `${label} is required`)}>
    {(control) => (
      <Input
        id={control.id}
        type={opts?.password ? "password" : "text"}
        placeholder={opts?.placeholder}
        value={(control.value as string | undefined) ?? ""}
        onChange={control.onChange}
        onBlur={control.onBlur}
        autoComplete="off"
      />
    )}
  </MountedFormField>
);

const optionalTextField = (name: string, label: string, opts?: { password?: boolean; placeholder?: string }) => (
  <MountedFormField key={name} label={label} name={name}>
    {(control) => (
      <Input
        id={control.id}
        type={opts?.password ? "password" : "text"}
        placeholder={opts?.placeholder}
        value={(control.value as string | undefined) ?? ""}
        onChange={control.onChange}
        onBlur={control.onBlur}
        autoComplete="off"
      />
    )}
  </MountedFormField>
);

const FIELDS_BY_PROVIDER: Record<BillingProvider, (isEdit: boolean) => ReactElement> = {
  openai: (isEdit) => textField("api_key", "Admin API key", isEdit, { password: true, placeholder: ADMIN_KEY_PLACEHOLDER.openai }),
  anthropic: (isEdit) =>
    textField("api_key", "Admin API key", isEdit, { password: true, placeholder: ADMIN_KEY_PLACEHOLDER.anthropic }),
  openrouter: (isEdit) => textField("api_key", "Admin API key", isEdit, { password: true }),
  bedrock: (isEdit) => (
    <>
      {textField("aws_access_key_id", "AWS access key ID", isEdit)}
      {textField("aws_secret_access_key", "AWS secret access key", isEdit, { password: true })}
      {optionalTextField("aws_session_token", "AWS session token (optional)", { password: true })}
      {optionalTextField("service_name", "Cost Explorer service name (optional)", { placeholder: "Amazon Bedrock" })}
    </>
  ),
  azure: (isEdit) => textField("subscription_id", "Subscription ID", isEdit),
  vertex_ai: (isEdit) => (
    <>
      {textField("billing_project_id", "Billing project ID", isEdit)}
      {textField("billing_export_table", "Billing export table", isEdit, {
        placeholder: "project.dataset.table",
      })}
    </>
  ),
};
