"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { providerUsageRawCall, type ProviderUsageRawResponse } from "@/components/networking";

const PAGE_SIZE = 25;

interface RawRecordsPanelProps {
  provider: string;
  onClose: () => void;
}

/**
 * One provider's records exactly as it sent them.
 *
 * The blueprint's own words for why this exists: "the data exactly as received, before Token IQ
 * priced or allocated it". So nothing here is recomputed or reformatted beyond making it readable:
 * the cost is shown as the string the provider sent, in the currency it named, because reformatting
 * a figure is the first step towards disagreeing with the bill it came from.
 *
 * Keyset-paged on the cursor the endpoint returns, rather than by page number, because rows arrive
 * continuously and an offset would skip or repeat rows as new ones land.
 */
export default function RawRecordsPanel({ provider, onClose }: RawRecordsPanelProps) {
  const { accessToken } = useAuthorized();
  const [before, setBefore] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<ProviderUsageRawResponse>({
    queryKey: ["provider-usage-raw", provider, before],
    queryFn: () => providerUsageRawCall(accessToken!, provider, PAGE_SIZE, before),
    enabled: Boolean(accessToken),
  });

  return (
    <section className="rounded-md border p-4" aria-label={`Raw records for ${provider}`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          Raw records from {provider}, as received
        </h3>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      {isLoading ? <p className="text-sm">Loading records...</p> : null}
      {error ? <p className="text-sm text-destructive">Could not read raw records for {provider}</p> : null}

      {data && data.rows.length === 0 ? (
        <p className="text-sm">No records stored for this period yet.</p>
      ) : null}

      {data && data.rows.length > 0 ? (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Bucket start</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Grain</TableHead>
                <TableHead>Evidence</TableHead>
                <TableHead className="text-right">Billed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((row, index) => (
                <TableRow key={`${row.bucket_start}:${row.credential_name}:${row.model ?? ""}:${index}`}>
                  <TableCell>{row.bucket_start}</TableCell>
                  <TableCell>{row.credential_name}</TableCell>
                  <TableCell>{row.model ?? <span className="text-muted-foreground">No model</span>}</TableCell>
                  <TableCell>{row.grain}</TableCell>
                  <TableCell>{row.evidence}</TableCell>
                  {/* The provider's own string and its own currency, not a reformatted number. */}
                  <TableCell className="text-right">
                    {row.billed_cost} {row.billing_currency}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="mt-3 flex items-center gap-2">
            {before !== null ? (
              <Button variant="outline" size="sm" onClick={() => setBefore(null)}>
                Back to newest
              </Button>
            ) : null}
            {data.next_before !== null ? (
              <Button variant="outline" size="sm" onClick={() => setBefore(data.next_before)}>
                Older records
              </Button>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
