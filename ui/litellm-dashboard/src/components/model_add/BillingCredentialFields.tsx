"use client";

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

      {provider === "bedrock" ? (
        <>
          <MountedFormField
            label="AWS access key ID"
            name="aws_access_key_id"
            required={!isEdit}
            rules={secretRules(isEdit, "AWS access key ID is required")}
          >
            {(control) => (
              <Input
                id={control.id}
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
                autoComplete="off"
              />
            )}
          </MountedFormField>
          <MountedFormField
            label="AWS secret access key"
            name="aws_secret_access_key"
            required={!isEdit}
            rules={secretRules(isEdit, "AWS secret access key is required")}
          >
            {(control) => (
              <Input
                id={control.id}
                type="password"
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
                autoComplete="off"
              />
            )}
          </MountedFormField>
          <MountedFormField label="AWS session token (optional)" name="aws_session_token">
            {(control) => (
              <Input
                id={control.id}
                type="password"
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
                autoComplete="off"
              />
            )}
          </MountedFormField>
          <MountedFormField label="Cost Explorer service name (optional)" name="service_name">
            {(control) => (
              <Input
                id={control.id}
                placeholder="Amazon Bedrock"
                value={(control.value as string | undefined) ?? ""}
                onChange={control.onChange}
                onBlur={control.onBlur}
              />
            )}
          </MountedFormField>
        </>
      ) : (
        <MountedFormField
          label="Admin API key"
          name="api_key"
          required={!isEdit}
          rules={secretRules(isEdit, "Admin API key is required")}
        >
          {(control) => (
            <Input
              id={control.id}
              type="password"
              value={(control.value as string | undefined) ?? ""}
              onChange={control.onChange}
              onBlur={control.onBlur}
              autoComplete="off"
              placeholder={ADMIN_KEY_PLACEHOLDER[provider] ?? ""}
            />
          )}
        </MountedFormField>
      )}
    </div>
  );
}
