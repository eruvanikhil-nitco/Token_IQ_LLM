"use client";

import Link from "next/link";

import { Card } from "@/components/ui/card";
import { migratedHref } from "@/utils/migratedPages";
import { useComparison } from "@/app/(dashboard)/hooks/combined/useComparison";
import { formatAmount, needsAttention } from "./comparisonDisplay";

interface UnallocatedViewProps {
  days: number;
}

export default function UnallocatedView({ days }: UnallocatedViewProps) {
  const { data, isLoading, error } = useComparison(days);

  if (isLoading) return <p className="text-sm text-muted-foreground">Looking for spend with no owner…</p>;
  if (error) return <p className="text-sm text-destructive">Could not read the comparison.</p>;
  if (!data) return null;

  const unclaimed = data.rows.filter(needsAttention);

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <p className="text-sm text-muted-foreground">Bypassed the gateway with no owner</p>
        <p className="text-2xl font-semibold">{formatAmount(data.total_gap)}</p>
      </Card>

      {unclaimed.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Every difference in this window is either assigned to an owner or still settling.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Day</th>
                <th className="py-2 pr-4">Provider</th>
                <th className="py-2 pr-4">Account</th>
                <th className="py-2 pr-4">Unclaimed</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {unclaimed.map((row) => (
                <tr key={`${row.day}-${row.provider}-${row.credential_name}`} className="border-b last:border-0">
                  <td className="py-2 pr-4 whitespace-nowrap">{row.day}</td>
                  <td className="py-2 pr-4">{row.display_name}</td>
                  <td className="py-2 pr-4">{row.credential_name}</td>
                  <td className="py-2 pr-4">{formatAmount(row.gap)}</td>
                  <td className="py-2 text-right">
                    <Link
                      className="underline"
                      href={migratedHref("attribution")}
                      aria-label={`Assign this account, ${row.credential_name}, to an owner`}
                    >
                      Assign this account
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
