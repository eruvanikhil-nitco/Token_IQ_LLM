"use client";

import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { auditListCall } from "@/components/networking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { UiLoadingSpinner } from "@/components/ui/ui-loading-spinner";
import { hasDetail, objectKindOptions, objectLabel, renderValue, shortId, type AuditEntry } from "./auditRows";

const PAGE_SIZE = 25;

const ACTIONS: readonly { readonly value: string; readonly label: string }[] = [
  { value: "", label: "All actions" },
  { value: "created", label: "Created" },
  { value: "updated", label: "Updated" },
  { value: "deleted", label: "Deleted" },
];

const ACTION_VARIANT: Readonly<Record<string, "secondary" | "outline" | "destructive">> = {
  created: "secondary",
  updated: "outline",
  deleted: "destructive",
};

interface AuditListResponse {
  entries: AuditEntry[];
  total: number;
  page: number;
  size: number;
}

const ChangeTable: React.FC<{ readonly entry: AuditEntry }> = ({ entry }) => (
  <div className="rounded-md border border-border bg-muted/40 p-3">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-1/4">Field</TableHead>
          <TableHead>Before</TableHead>
          <TableHead>After</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entry.changes.map((change) => (
          <TableRow key={change.field}>
            <TableCell className="font-mono text-xs">{change.field}</TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground break-all">
              {renderValue(change.before, entry.action)}
            </TableCell>
            <TableCell className="font-mono text-xs break-all">{renderValue(change.after, entry.action)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </div>
);

/**
 * Who changed what, and when.
 *
 * Shows the fields that moved rather than the raw row snapshots the database holds: an update
 * writes the whole row, of which one field usually matters, and the point of an audit trail is
 * answering "what changed" without making the reader diff two JSON blobs by eye.
 *
 * Secrets are redacted by the endpoint, not here, so this cannot be the place they leak.
 */
const AuditLogView: React.FC = () => {
  const { accessToken } = useAuthorized();
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [tableName, setTableName] = useState("");
  const [changedBy, setChangedBy] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery<AuditListResponse>({
    queryKey: ["audit", "list", page, action, tableName, changedBy],
    queryFn: () =>
      auditListCall(accessToken as string, {
        page,
        size: PAGE_SIZE,
        ...(action && { action }),
        ...(tableName && { table_name: tableName }),
        ...(changedBy && { changed_by: changedBy }),
      }),
    enabled: Boolean(accessToken),
  });

  const entries = useMemo(() => data?.entries ?? [], [data]);
  const kinds = useMemo(() => objectKindOptions(entries), [entries]);
  const total = data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const onFilterChange = (setter: (value: string) => void) => (value: string) => {
    setter(value);
    setPage(1);
  };

  const body = () => {
    if (isLoading) {
      return (
        <div className="flex justify-center py-8">
          <UiLoadingSpinner />
        </div>
      );
    }
    if (isError) {
      return <p className="py-6 text-sm text-muted-foreground">Could not load the audit trail.</p>;
    }
    if (entries.length === 0) {
      return (
        <p className="py-6 text-sm text-muted-foreground">
          Nothing recorded yet. Changes are only kept while <code>store_audit_logs</code> is enabled.
        </p>
      );
    }
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Object</TableHead>
            <TableHead>Who</TableHead>
            <TableHead>What changed</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry) => (
            <React.Fragment key={entry.id}>
              <TableRow>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {entry.changed_at.replace("T", " ").slice(0, 19)}
                </TableCell>
                <TableCell>
                  <Badge variant={ACTION_VARIANT[entry.action] ?? "outline"}>{entry.action}</Badge>
                </TableCell>
                <TableCell>
                  <span className="font-medium">{objectLabel(entry.table_name)}</span>{" "}
                  <span className="font-mono text-xs text-muted-foreground">{shortId(entry.object_id)}</span>
                </TableCell>
                <TableCell>{entry.changed_by || "unknown"}</TableCell>
                <TableCell className="text-muted-foreground">{entry.summary}</TableCell>
                <TableCell className="text-right">
                  {hasDetail(entry) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                    >
                      {expanded === entry.id ? "Hide" : "Details"}
                    </Button>
                  )}
                </TableCell>
              </TableRow>
              {expanded === entry.id && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <ChangeTable entry={entry} />
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Audit log</CardTitle>
        <p className="text-sm text-muted-foreground">
          Every change to a key, team, model or user, with the fields that moved. Secrets are redacted.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Filter by action"
            className="rounded-md border border-border bg-background px-2 py-1 text-sm"
            value={action}
            onChange={(event) => onFilterChange(setAction)(event.target.value)}
          >
            {ACTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter by object"
            className="rounded-md border border-border bg-background px-2 py-1 text-sm"
            value={tableName}
            onChange={(event) => onFilterChange(setTableName)(event.target.value)}
          >
            <option value="">All objects</option>
            {kinds.map((kind) => (
              <option key={kind.value} value={kind.value}>
                {kind.label}
              </option>
            ))}
          </select>
          <Input
            aria-label="Filter by who made the change"
            placeholder="Filter by who..."
            value={changedBy}
            onChange={(event) => onFilterChange(setChangedBy)(event.target.value)}
            className="max-w-xs"
          />
        </div>

        {body()}

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Page {page} of {lastPage}, {total} recorded changes
            </span>
            <span className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={page >= lastPage} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AuditLogView;
