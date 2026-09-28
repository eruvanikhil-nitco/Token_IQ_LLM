"use client";

import ProviderUsagePanel from "./_components/apis/ProviderUsagePanel";
import NewUsagePage from "./_components/components/UsagePageView";
import CombinedTabs from "./_components/combined/CombinedTabs";
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
      apis={<ProviderUsagePanel />}
      combined={<CombinedTabs />}
    />
  );
}
