"use client";

import { useState } from "react";

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CostExplorerView from "./CostExplorerView";
import SourceComparisonView from "./SourceComparisonView";
import UnallocatedView from "./UnallocatedView";

const RANGES = [
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
] as const;

export default function CombinedTabs() {
  const [days, setDays] = useState<string>("30");

  return (
    <Tabs defaultValue="explorer" className="flex flex-col gap-6">
      {/* The view and the period it covers read as one control, so they share a row rather than
          stacking into two bands of chrome above the figures. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TabsList>
          <TabsTrigger value="explorer">Cost Explorer</TabsTrigger>
          <TabsTrigger value="comparison">Source Comparison</TabsTrigger>
          <TabsTrigger value="unallocated">Unallocated</TabsTrigger>
        </TabsList>
        <div className="flex items-center gap-2">
          <Label htmlFor="combined-date-range" className="text-muted-foreground">
            Date range
          </Label>
          <Select items={RANGES} value={days} onValueChange={(next) => next !== null && setDays(next)}>
            <SelectTrigger id="combined-date-range" aria-label="Date range" className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {RANGES.map((range) => (
                <SelectItem key={range.value} value={range.value}>
                  {range.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* keepMounted: switching views must not reset the grouping or the date range */}
      <TabsContent value="explorer" keepMounted>
        <CostExplorerView days={Number(days)} />
      </TabsContent>
      {/* keepMounted: switching views must not reset the date range the reader chose */}
      <TabsContent value="comparison" keepMounted>
        <SourceComparisonView days={Number(days)} />
      </TabsContent>
      <TabsContent value="unallocated" keepMounted>
        <UnallocatedView days={Number(days)} />
      </TabsContent>
    </Tabs>
  );
}
