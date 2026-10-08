"use client";

import { Plug } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import ProviderApisPanel from "./_components/ProviderApisPanel";

export default function ProviderApisPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<Plug />}
        title="Provider APIs"
        subtitle="What each provider reports that your accounts cost, and whether we can still read it."
      />
      <ProviderApisPanel />
    </main>
  );
}
