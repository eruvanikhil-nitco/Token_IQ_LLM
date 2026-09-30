"use client";

import { LayoutDashboard } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import OverviewPanel from "./_components/OverviewPanel";

export default function OverviewPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<LayoutDashboard />}
        title="Overview"
        subtitle="What you spent, whether the bills matched, and what is worth doing about it."
      />
      <OverviewPanel />
    </main>
  );
}
