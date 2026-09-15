"use client";

import { LockKeyhole } from "lucide-react";

import CredentialsPanel from "@/components/model_add/CredentialsPanel";
import { PageHeader } from "@/components/shared/PageHeader";

export default function LlmProviderCredentialsPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<LockKeyhole />}
        title="LLM Provider Credentials"
        subtitle="Keys for serving models and read-only keys for reading provider costs."
      />
      <CredentialsPanel />
    </main>
  );
}
