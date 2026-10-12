"use client";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useUploads } from "@/app/(dashboard)/hooks/ledger/useUploads";

import EnterInvoiceDialog from "./EnterInvoiceDialog";
import { billsMissing, forwardingMessage, uploadRowViews } from "./uploadRows";

/**
 * Data Sources > Uploads: the bills that have no API.
 *
 * The blueprint's tab covers invoices, workspace exports and contracts. Only invoices have
 * anywhere to go: `/ledger/invoices` stores one and reconciliation reads it. An export or a
 * contract would be a form whose save has nothing behind it, so the tab names them as not yet
 * built rather than offering a field that drops what is typed into it.
 *
 * The rows worth the tab are the bills nobody entered. A missing bill is invisible everywhere
 * else: reconciliation for that month reports no bill rather than a difference, and the Overview
 * tab's coverage figure says how many are missing without saying which.
 */
interface UploadsTabProps {
  /** Whether this viewer may enter a bill. A read-only admin reads the rows and saves nothing. */
  canEnter: boolean;
}

export default function UploadsTab({ canEnter }: UploadsTabProps) {
  const { data, isLoading, error } = useUploads();

  if (isLoading) {
    return <p className="text-sm">Loading bills...</p>;
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Could not read the bills</p>;
  }

  const forwarding = forwardingMessage(data.forwarding);
  const rows = uploadRowViews(data.rows, data.checked_from);
  const missing = billsMissing(data.rows);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-md border p-3">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">Forwarding bills by email</span>
          {forwarding.address ? (
            <span className={`font-mono text-sm ${forwarding.tone === "unusable" ? "text-destructive" : ""}`}>
              {forwarding.address}
            </span>
          ) : null}
          <span className={`text-xs ${forwarding.tone === "unusable" ? "text-destructive" : "text-muted-foreground"}`}>
            {forwarding.text}
          </span>
        </div>
        {/* Hidden rather than disabled for a read-only admin, the same rule the page applies to
            Connect account: the save is refused server side, so the button would be a dead end. */}
        {canEnter ? <EnterInvoiceDialog providers={data.providers} /> : null}
      </div>

      {rows.length === 0 ? (
        <p className="text-sm">
          No bills entered, and no provider has billed anything that needs one. A bill is what reconciliation compares
          recorded usage against, so until one is entered a month can be reported but not checked.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Provider</TableHead>
              <TableHead>Period</TableHead>
              {/* The bill's own figure, in the bill's own currency. Never beside a figure Token IQ
                  worked out: a provider total and an attribution total are never added. */}
              <TableHead className="text-right">Bill total</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Note</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.provider}</TableCell>
                <TableCell>{row.period}</TableCell>
                <TableCell className="text-right">
                  {row.total ?? <span className="text-muted-foreground">Not entered</span>}
                </TableCell>
                <TableCell>
                  <Badge variant={row.status === "missing" ? "destructive" : "default"}>{row.statusLabel}</Badge>
                  {row.detail ? <span className="ml-2 text-xs text-muted-foreground">{row.detail}</span> : null}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{row.note ?? ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <p className="text-sm text-muted-foreground">
        {missing === 0
          ? "Every provider that billed in the last 30 days has a bill entered covering it."
          : `${missing} provider${missing === 1 ? "" : "s"} billed in the last 30 days with no bill entered to check it against.`}{" "}
        Workspace exports and contracts belong on this tab too and have nowhere to go yet, so neither is offered until
        something reads them.
      </p>
    </div>
  );
}
