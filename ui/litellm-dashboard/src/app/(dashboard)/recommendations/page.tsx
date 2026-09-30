"use client";

import { Lightbulb } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import RecommendationTabs from "./_components/RecommendationTabs";

export default function RecommendationsPage() {
  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<Lightbulb />}
        title="Recommendations"
        subtitle="What is worth doing about this period, the evidence behind it, and what was already decided."
      />
      <RecommendationTabs />
    </main>
  );
}
