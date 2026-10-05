"use client";

import { Info } from "lucide-react";

import { useProviderConnections } from "@/app/(dashboard)/hooks/providerApis/useProviderConnections";
import type { DateRangePickerValue } from "@/components/shared/date_picker_types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { lastNDaysCoverage } from "../usagePeriod";
import RawDataView from "./RawDataView";
import UsageSummaryView from "./UsageSummaryView";

interface ProviderUsagePanelProps {
  period: DateRangePickerValue;
}

export default function ProviderUsagePanel({ period }: ProviderUsagePanelProps) {
  const { data: connections, isLoading, error } = useProviderConnections();
  // The same endpoint shape as the Combined views: days capped at 90, always meaning "the last N
  // days". This tab used to ask for a fixed 30 regardless of what the header picker said.
  const coverage = lastNDaysCoverage(period);

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
    <div className="flex flex-col gap-4">
      {/* Meaning before figures. These are the provider's own numbers, so they say how much was
          spent and never who spent it, which is the gateway's job on the other two tabs. */}
      <p className="text-sm text-muted-foreground">
        What the provider itself reported it charged, read from its own billing API. These figures say how much was
        spent, not who spent it, so nothing here is added to the gateway&apos;s own records.
      </p>

      {!coverage.exact && (
        <p role="status" className="flex items-start gap-2 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{coverage.note}</span>
        </p>
      )}

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
            <Tabs defaultValue="summary">
              <TabsList>
                <TabsTrigger value="summary">Summary</TabsTrigger>
                <TabsTrigger value="raw">Raw Data</TabsTrigger>
              </TabsList>
              <TabsContent value="summary" className="pt-6">
                <UsageSummaryView provider={connection.provider} days={coverage.days} />
              </TabsContent>
              <TabsContent value="raw" className="pt-6">
                {/* Deliberately not given the period: this view is the newest rows the provider
                    sent, keyset-paged, and says so rather than claiming a window. */}
                <RawDataView provider={connection.provider} displayName={connection.display_name} />
              </TabsContent>
            </Tabs>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
