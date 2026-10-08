"use client";

import { BookOpen } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import LedgerTabs from "./_components/LedgerTabs";

export default function LedgerPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<BookOpen />}
        title="Invoice Reconciliation"
        subtitle="Every cost line the providers reported, the bills they sent, and what the difference is."
      />
      <LedgerTabs />
    </main>
  );
}
