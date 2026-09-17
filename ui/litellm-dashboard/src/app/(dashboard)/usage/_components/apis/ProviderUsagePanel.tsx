"use client";

import { useProviderConnections } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import UsageSummaryView from "./UsageSummaryView";

const USAGE_WINDOW_DAYS = 30;

export default function ProviderUsagePanel() {
  const { data: connections, isLoading, error } = useProviderConnections();

  if (isLoading) {
    return <p className="text-sm">Loading providers...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read the provider list</p>;
  }
  if (!connections || connections.length === 0) {
    return <p className="text-sm">This build reads no provider billing APIs</p>;
  }

  return (
    <Tabs defaultValue={connections[0].provider}>
      <TabsList>
        {connections.map((connection) => (
          <TabsTrigger key={connection.provider} value={connection.provider}>
            {connection.display_name}
          </TabsTrigger>
        ))}
      </TabsList>
      {connections.map((connection) => (
        <TabsContent key={connection.provider} value={connection.provider} className="pt-6">
          <UsageSummaryView provider={connection.provider} days={USAGE_WINDOW_DAYS} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
