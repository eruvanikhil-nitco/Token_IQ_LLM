"use client";

import NewUsagePage from "./_components/components/UsagePageView";
import UsageTabs from "./_components/UsageTabs";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { useTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
import { useOrganizations } from "@/app/(dashboard)/hooks/organizations/useOrganizations";

export default function UsagePage() {
  useAuthorized();
  const { data: teams } = useTeams();
  const { data: organizations } = useOrganizations();
  return (
    <UsageTabs
      gateway={<NewUsagePage teams={teams ?? []} organizations={organizations ?? []} />}
      apis={<p className="text-sm text-muted-foreground">APIs usage is coming soon.</p>}
    />
  );
}
