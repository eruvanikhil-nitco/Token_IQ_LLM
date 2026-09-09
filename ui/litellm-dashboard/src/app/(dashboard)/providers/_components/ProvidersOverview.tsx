"use client";

import { useQuery } from "@tanstack/react-query";
import { providerOverviewCall } from "@/components/networking";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { filterProviderRows, usageWindowLabel } from "./selectors";
import type { ProviderOverviewResponse } from "./types";

const StatBlock: React.FC<{ label: string; value: string; hint?: string }> = ({ label, value, hint }) => (
  // The labels collide with table headers ("Requests", "Cost"), so the block carries its
  // own hook rather than making callers write positional queries.
  <Card className="p-4" data-testid={`stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
    <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">{label}</p>
    <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
    {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
  </Card>
);

interface ProvidersOverviewProps {
  accessToken: string | null;
  selectedProvider: string | null;
}

const ProvidersOverview: React.FC<ProvidersOverviewProps> = ({ accessToken, selectedProvider }) => {
  const { data, isLoading, isError } = useQuery<ProviderOverviewResponse>({
    queryKey: ["providers", "overview"],
    queryFn: () => providerOverviewCall(accessToken as string),
    enabled: Boolean(accessToken),
  });

  if (isLoading) return <p className="p-4 text-sm text-muted-foreground">Loading providers…</p>;
  if (isError || !data) return <p className="p-4 text-sm text-destructive">Could not load provider overview.</p>;

  const rows = filterProviderRows(data.providers, selectedProvider);

  const window = usageWindowLabel(data.rollup_days);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatBlock label="Total Providers" value={String(data.total_providers)} />
        <StatBlock label="Total Models" value={String(data.total_models)} hint="configured on this gateway" />
        <StatBlock label="Requests" value={data.total_requests.toLocaleString()} hint={window} />
        <StatBlock label="Cost" value={`$${data.total_spend.toFixed(6)}`} hint={window} />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Provider</TableHead>
            <TableHead className="text-right">Models configured</TableHead>
            <TableHead className="text-right">Models in catalogue</TableHead>
            <TableHead>Credentials</TableHead>
            <TableHead className="text-right">Requests</TableHead>
            <TableHead className="text-right">Cost</TableHead>
            <TableHead>Last used</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-sm text-muted-foreground">
                No providers configured, and none recorded any traffic.
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row) => (
              <TableRow key={row.provider}>
                <TableCell className="font-medium">
                  <span className="flex items-center gap-2">
                    {row.provider}
                    {!row.is_configured && (
                      <Badge
                        variant="outline"
                        title="Traffic recorded, but no deployment is configured for it any more"
                      >
                        Not configured
                      </Badge>
                    )}
                  </span>
                </TableCell>
                <TableCell className="text-right">{row.models_configured}</TableCell>
                <TableCell className="text-right text-muted-foreground">{row.models_in_catalogue}</TableCell>
                <TableCell>
                  {row.has_credentials ? (
                    <Badge variant="secondary">Present</Badge>
                  ) : (
                    <Badge variant="outline">Missing</Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">{row.requests.toLocaleString()}</TableCell>
                <TableCell className="text-right">${row.spend.toFixed(6)}</TableCell>
                <TableCell className="text-muted-foreground">{row.last_used ?? "—"}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
};

export default ProvidersOverview;
