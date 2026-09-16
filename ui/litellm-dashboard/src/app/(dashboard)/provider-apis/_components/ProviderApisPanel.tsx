"use client";

import { useProviderConnections } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ConnectionTab from "./ConnectionTab";
import { STATE_LABELS, stateBadgeVariant } from "./connectionState";

export default function ProviderApisPanel() {
  const { data: connections, isLoading, error } = useProviderConnections();

  if (isLoading) {
    return <p className="text-sm">Loading provider connections...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read provider connections</p>;
  }
  if (!connections || connections.length === 0) {
    return <p className="text-sm">This build reads no provider billing APIs</p>;
  }

  return (
    <Tabs defaultValue={connections[0].provider}>
      <TabsList>
        {connections.map((connection) => (
          <TabsTrigger key={connection.provider} value={connection.provider}>
            <span className="flex items-center gap-2">
              {connection.display_name}
              <Badge variant={stateBadgeVariant(connection.state)}>{STATE_LABELS[connection.state]}</Badge>
            </span>
          </TabsTrigger>
        ))}
      </TabsList>
      {connections.map((connection) => (
        <TabsContent key={connection.provider} value={connection.provider} className="pt-6">
          <ConnectionTab connection={connection} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
