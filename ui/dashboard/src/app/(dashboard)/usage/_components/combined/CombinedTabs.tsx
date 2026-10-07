"use client";

import { Info } from "lucide-react";

import type { DateRangePickerValue } from "@/components/shared/date_picker_types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { lastNDaysCoverage } from "../usagePeriod";
import CostExplorerView from "./CostExplorerView";
import SourceComparisonView from "./SourceComparisonView";
import UnallocatedView from "./UnallocatedView";

interface CombinedTabsProps {
  period: DateRangePickerValue;
}

export default function CombinedTabs({ period }: CombinedTabsProps) {
  // The period comes from the page, so switching tab cannot change it. These endpoints take a
  // number of days capped at 90 and always mean "the last N days", so they cannot serve every
  // period the picker offers. When they cannot, the reader is told, because showing a different
  // window that looks like the one they chose is the failure this replaced. The APIs tab reads an
  // endpoint of the same shape and says the same thing, from the same helper.
  const coverage = lastNDaysCoverage(period);

  return (
    <Tabs defaultValue="explorer" className="flex flex-col gap-6">
      <TabsList>
        <TabsTrigger value="explorer">Cost Explorer</TabsTrigger>
        <TabsTrigger value="comparison">Source Comparison</TabsTrigger>
        <TabsTrigger value="unallocated">Unallocated</TabsTrigger>
      </TabsList>

      {!coverage.exact && (
        <p role="status" className="flex items-start gap-2 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{coverage.note}</span>
        </p>
      )}

      {/* keepMounted: switching views must not reset the grouping the reader chose */}
      <TabsContent value="explorer" keepMounted>
        <CostExplorerView days={coverage.days} />
      </TabsContent>
      <TabsContent value="comparison" keepMounted>
        <SourceComparisonView days={coverage.days} />
      </TabsContent>
      <TabsContent value="unallocated" keepMounted>
        <UnallocatedView days={coverage.days} />
      </TabsContent>
    </Tabs>
  );
}
