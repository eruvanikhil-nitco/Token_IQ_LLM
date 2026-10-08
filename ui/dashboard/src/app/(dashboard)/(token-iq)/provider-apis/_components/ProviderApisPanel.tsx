"use client";

import { useProviderConnections } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ConnectionTab from "./ConnectionTab";
import SyncHistoryTab from "./SyncHistoryTab";
import WhatWeFetchTab from "./WhatWeFetchTab";
import { stateBadgeVariant, stateLabel } from "./connectionState";

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
      {/* The provider list grows every time one is supported, and a fixed row silently puts the
          last of them past the right edge where it cannot be clicked. Scrolling keeps every
          provider reachable however many there are. */}
      <div className="-mx-1 overflow-x-auto px-1">
        <TabsList>
          {connections.map((connection) => (
            <TabsTrigger key={connection.provider} value={connection.provider}>
              <span className="flex items-center gap-2">
                {connection.display_name}
                <Badge variant={stateBadgeVariant(connection.state)}>{stateLabel(connection.state)}</Badge>
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      {connections.map((connection) => (
        <TabsContent key={connection.provider} value={connection.provider} className="pt-6">
          <Tabs defaultValue="connection">
            <TabsList>
              <TabsTrigger value="connection">Connection</TabsTrigger>
              <TabsTrigger value="what-we-fetch">What We Fetch</TabsTrigger>
              <TabsTrigger value="sync-history">Sync History</TabsTrigger>
            </TabsList>
            <TabsContent value="connection" className="pt-6">
              <ConnectionTab connection={connection} />
            </TabsContent>
            <TabsContent value="what-we-fetch" className="pt-6">
              <WhatWeFetchTab fetches={connection.fetches} />
            </TabsContent>
            <TabsContent value="sync-history" className="pt-6">
              <SyncHistoryTab provider={connection.provider} />
            </TabsContent>
          </Tabs>
        </TabsContent>
      ))}
    </Tabs>
  );
}
