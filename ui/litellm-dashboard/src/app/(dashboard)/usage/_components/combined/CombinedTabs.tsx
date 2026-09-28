"use client";

import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SourceComparisonView from "./SourceComparisonView";
import UnallocatedView from "./UnallocatedView";

const RANGES = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
] as const;

export default function CombinedTabs() {
  const [days, setDays] = useState<number>(30);

  return (
    <div className="flex flex-col gap-6">
      <label className="flex w-fit flex-col gap-1 text-sm">
        <span>Date range</span>
        <select
          aria-label="Date range"
          className="h-9 rounded-md border bg-background px-2"
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
        >
          {RANGES.map((range) => (
            <option key={range.value} value={range.value}>
              {range.label}
            </option>
          ))}
        </select>
      </label>

      <Tabs defaultValue="comparison">
        <TabsList>
          <TabsTrigger value="comparison">Source Comparison</TabsTrigger>
          <TabsTrigger value="unallocated">Unallocated</TabsTrigger>
        </TabsList>
        {/* keepMounted: switching views must not reset the date range the reader chose */}
        <TabsContent value="comparison" className="pt-6" keepMounted>
          <SourceComparisonView days={days} />
        </TabsContent>
        <TabsContent value="unallocated" className="pt-6" keepMounted>
          <UnallocatedView days={days} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
