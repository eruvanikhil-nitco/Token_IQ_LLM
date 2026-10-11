"use client";

import { Database } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import DataSourcesTabs from "./_components/DataSourcesTabs";

export default function DataSourcesPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<Database />}
        title="Data Sources"
        subtitle="Every place Token IQ gets usage and cost data from, whether it is arriving, and the records exactly as received."
      />
      <DataSourcesTabs />
    </main>
  );
}
