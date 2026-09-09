"use client";

import { useMemo, useState } from "react";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { getModelHubTableColumns, type ModelHubData } from "@/components/AIHub/ModelHubTableColumns";
import { DataTable, DataTableSortHeader } from "@/components/shared/DataTable";
import { modelHubCall, providerModelUsageCall, providerOverviewCall } from "@/components/networking";
import ModelHubDetailsDialog from "@/components/AIHub/ModelHubDetailsDialog";
import { Badge } from "@/components/ui/badge";
import { filterModelsByVisibleProviders, isObservedOnly } from "@/utils/providerVisibility";
import {
  filterModelsByProvider,
  hasUsage,
  indexUsageByModel,
  observedOnlyModels,
  type ModelUsageRow,
} from "./selectors";
import type { ProviderOverviewResponse } from "./types";

interface ProviderModelsTableProps {
  accessToken: string | null;
  /** Page-level provider filter. Null shows every provider. */
  selectedProvider: string | null;
}

interface ModelUsageResponse {
  range: string;
  days: number;
  start_date: string;
  usage: ModelUsageRow[];
}

/** Whole UTC days, because the daily rollup buckets by day and cannot answer a rolling
 *  window. "Today" is today's bucket, not the last 24 hours. */
const USAGE_RANGES = [
  { value: "day", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
] as const;

/**
 * The AI Hub's model table on its own, plus a Usage column.
 *
 * Only the table: none of the AI Hub page around it, which also carries Agents, MCP and
 * Skills sections, a search box and the useful-links panel. The columns and the details
 * dialog are imported from the same source AI Hub uses, so the two cannot drift.
 */
const ProviderModelsTable: React.FC<ProviderModelsTableProps> = ({ accessToken, selectedProvider }) => {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [selectedModel, setSelectedModel] = useState<ModelHubData | null>(null);
  const [usageRange, setUsageRange] = useState<string>("week");

  const { data, isLoading } = useQuery<ModelHubData[]>({
    queryKey: ["providers", "model-hub"],
    queryFn: async () => (await modelHubCall(accessToken as string)).data,
    enabled: Boolean(accessToken),
  });

  // Same query key as the Overview tab and the page filter, so this reads their cache
  // rather than fetching a third time.
  const { data: overview } = useQuery<ProviderOverviewResponse>({
    queryKey: ["providers", "overview"],
    queryFn: () => providerOverviewCall(accessToken as string),
    enabled: Boolean(accessToken),
  });

  const { data: usage } = useQuery<ModelUsageResponse>({
    queryKey: ["providers", "model-usage", usageRange],
    queryFn: () => providerModelUsageCall(accessToken as string, usageRange),
    enabled: Boolean(accessToken),
  });

  const usageByModel = useMemo(() => indexUsageByModel(usage?.usage ?? []), [usage]);

  const columns = useMemo<ColumnDef<ModelHubData>[]>(() => {
    const usageColumn: ColumnDef<ModelHubData> = {
      id: "usage",
      header: ({ column }) => <DataTableSortHeader column={column} title="Usage" />,
      // Sorts on request count, which is what the cell leads with.
      accessorFn: (model) => usageByModel.get(model.model_group)?.requests ?? 0,
      cell: ({ row }) => {
        const rowUsage = usageByModel.get(row.original.model_group);
        if (!hasUsage(rowUsage)) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <span className="flex flex-col leading-tight">
            <span>{rowUsage.requests.toLocaleString()} req</span>
            <span className="text-xs text-muted-foreground">
              {rowUsage.tokens.toLocaleString()} tokens · ${rowUsage.spend.toFixed(6)}
            </span>
          </span>
        );
      },
    };
    const statusColumn: ColumnDef<ModelHubData> = {
      id: "status",
      header: "Status",
      cell: ({ row }) =>
        isObservedOnly(row.original) ? (
          <Badge variant="outline" title="Traffic recorded, but no deployment is configured for it any more">
            Not configured
          </Badge>
        ) : (
          <span className="text-muted-foreground">Configured</span>
        ),
    };

    return [...getModelHubTableColumns({ onModelClick: setSelectedModel }), usageColumn, statusColumn];
  }, [usageByModel]);

  const rows = useMemo(() => {
    const configured = data ?? [];
    const all = [...configured, ...observedOnlyModels(configured, usage?.usage ?? [])];
    const setUp = filterModelsByVisibleProviders(
      all,
      overview?.providers.map((row) => row.provider),
    );
    return filterModelsByProvider(setUp, selectedProvider);
  }, [data, usage, overview, selectedProvider]);

  return (
    <div className="flex flex-col gap-3">
      <label className="flex items-center gap-2 self-end text-sm">
        <span className="text-muted-foreground">Usage over</span>
        <select
          aria-label="Usage range"
          className="rounded-md border border-border bg-background px-2 py-1 text-sm"
          value={usageRange}
          onChange={(event) => setUsageRange(event.target.value)}
        >
          {USAGE_RANGES.map((range) => (
            <option key={range.value} value={range.value}>
              {range.label}
            </option>
          ))}
        </select>
      </label>

      <DataTable
        data={rows}
        columns={columns}
        getRowId={(model, index) => model.model_group || String(index)}
        sortingMode="client"
        sorting={sorting}
        onSortingChange={setSorting}
        isLoading={isLoading}
        loadingMessage="Loading models…"
        noDataMessage={
          selectedProvider
            ? `No models configured for ${selectedProvider}, and none recorded traffic.`
            : "No models configured, and none recorded traffic."
        }
      />
      <ModelHubDetailsDialog selectedModel={selectedModel} onClose={() => setSelectedModel(null)} />
    </div>
  );
};

export default ProviderModelsTable;
