"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerOverviewCall } from "@/components/networking";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ProviderModelsTable from "./_components/ProviderModelsTable";
import ProvidersOverview from "./_components/ProvidersOverview";
import type { ProviderOverviewResponse } from "./_components/types";

const ALL_PROVIDERS = "__all__";

const ProvidersPage = () => {
  const { accessToken } = useAuthorized();
  const [selectedProvider, setSelectedProvider] = useState<string>(ALL_PROVIDERS);

  // The filter offers the providers actually configured here, so it cannot select a
  // provider with nothing behind it. Sourced from the overview because that is the
  // same list the Overview table renders.
  const { data: overview } = useQuery<ProviderOverviewResponse>({
    queryKey: ["providers", "overview"],
    queryFn: () => providerOverviewCall(accessToken as string),
    enabled: Boolean(accessToken),
  });

  const provider = selectedProvider === ALL_PROVIDERS ? null : selectedProvider;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Providers</h1>
          <p className="text-sm text-muted-foreground">
            What each provider serves, what it costs, and which of its models this gateway is configured for.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Provider</span>
          <select
            aria-label="Filter by provider"
            className="rounded-md border border-border bg-background px-2 py-1 text-sm"
            value={selectedProvider}
            onChange={(event) => setSelectedProvider(event.target.value)}
          >
            <option value={ALL_PROVIDERS}>All providers</option>
            {overview?.providers.map((row) => (
              <option key={row.provider} value={row.provider}>
                {row.provider}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <ProvidersOverview accessToken={accessToken} selectedProvider={provider} />
        </TabsContent>
        <TabsContent value="models">
          <ProviderModelsTable accessToken={accessToken} selectedProvider={provider} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ProvidersPage;
