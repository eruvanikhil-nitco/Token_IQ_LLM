"use client";

import { useToolConnections } from "@/app/(dashboard)/hooks/userTools/useToolConnections";
import { stateBadgeVariant, stateLabel } from "@/app/(dashboard)/(token-iq)/provider-apis/_components/connectionState";
import SyncHistoryTab from "@/app/(dashboard)/(token-iq)/provider-apis/_components/SyncHistoryTab";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ToolConnectionTab from "./ToolConnectionTab";
import ToolWhatWeFetchTab from "./ToolWhatWeFetchTab";

export default function UserToolsPanel() {
  const { data: connections, isLoading, error } = useToolConnections();

  if (isLoading) {
    return <p className="text-sm">Loading user tool connections...</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">Could not read user tool connections</p>;
  }
  if (!connections || connections.length === 0) {
    return <p className="text-sm">This build reads no user tools</p>;
  }

  return (
    <Tabs defaultValue={connections[0].tool}>
      {/* Same reason as the provider list: one more supported tool would push the last one past
          the right edge, where it cannot be clicked. */}
      <div className="-mx-1 overflow-x-auto px-1">
        <TabsList>
          {connections.map((connection) => (
            <TabsTrigger key={connection.tool} value={connection.tool}>
              <span className="flex items-center gap-2">
                {connection.display_name}
                <Badge variant={stateBadgeVariant(connection.state)}>{stateLabel(connection.state)}</Badge>
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      {connections.map((connection) => (
        <TabsContent key={connection.tool} value={connection.tool} className="pt-6">
          <Tabs defaultValue="connection">
            <TabsList>
              <TabsTrigger value="connection">Connection</TabsTrigger>
              <TabsTrigger value="what-we-fetch">What We Fetch</TabsTrigger>
              <TabsTrigger value="sync-history">Sync History</TabsTrigger>
            </TabsList>
            <TabsContent value="connection" className="pt-6">
              <ToolConnectionTab connection={connection} />
            </TabsContent>
            <TabsContent value="what-we-fetch" className="pt-6">
              <ToolWhatWeFetchTab connection={connection} />
            </TabsContent>
            <TabsContent value="sync-history" className="pt-6">
              {/* Tools record into the same sync history as providers, keyed by the tool name,
                  so this screen needs no machinery of its own */}
              <SyncHistoryTab provider={connection.tool} />
            </TabsContent>
          </Tabs>
        </TabsContent>
      ))}
    </Tabs>
  );
}
