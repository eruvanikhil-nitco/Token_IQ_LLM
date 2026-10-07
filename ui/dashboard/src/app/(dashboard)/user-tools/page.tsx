"use client";

import { Wrench } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import UserToolsPanel from "./_components/UserToolsPanel";

export default function UserToolsPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<Wrench />}
        title="User Tools"
        subtitle="What each coding tool reports your people spent, and what it cannot tell us."
      />
      <UserToolsPanel />
    </main>
  );
}
