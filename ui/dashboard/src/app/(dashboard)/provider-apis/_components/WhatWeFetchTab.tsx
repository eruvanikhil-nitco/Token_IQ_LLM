"use client";

import type { ProviderFetchDetail } from "@/components/networking";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { describeCadence, describeWindow } from "./fetchCadence";

export default function WhatWeFetchTab({ fetches }: { fetches: ProviderFetchDetail }) {
  const rows: ReadonlyArray<readonly [string, string]> = [
    ["Endpoint", fetches.endpoint],
    ["Address", fetches.endpoint_url],
    ["Detail level", fetches.grain === "request" ? "Per request" : "Per day"],
    ["Refresh", describeCadence(fetches.refresh_seconds)],
    ["Window read each time", describeWindow(fetches.window_hours)],
  ];

  return (
    <div className="flex flex-col gap-6">
      <Table>
        <TableBody>
          {rows.map(([label, value]) => (
            <TableRow key={label}>
              <TableCell className="w-56 font-medium">{label}</TableCell>
              <TableCell>{value}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex flex-col gap-2 text-sm text-muted-foreground">
        <p>{fetches.delay_note}</p>
        <p>{fetches.history_note}</p>
      </div>
    </div>
  );
}
