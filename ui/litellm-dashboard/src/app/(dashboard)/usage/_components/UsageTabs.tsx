"use client";

import { BarChart3 } from "lucide-react";
import { useState, type ReactNode } from "react";

import AdvancedDatePicker from "@/components/shared/advanced_date_picker";
import type { DateRangePickerValue } from "@/components/shared/date_picker_types";
import { PageHeader } from "@/components/shared/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface UsageTabsProps {
  gateway: (period: DateRangePickerValue) => ReactNode;
  apis: (period: DateRangePickerValue) => ReactNode;
  combined: (period: DateRangePickerValue) => ReactNode;
}

const DEFAULT_DAYS = 30;

export default function UsageTabs({ gateway, apis, combined }: UsageTabsProps) {
  // One period for the whole page. It used to be two: Combined had a 7/30/90 dropdown defaulting to
  // 30 days and Gateway had its own picker defaulting to 7, and because both panels stay mounted,
  // switching tab moved the window with nothing on screen saying so.
  // A lazy initialiser, so reading the clock happens once rather than on every render.
  const [period, setPeriod] = useState<DateRangePickerValue>(() => ({
    from: new Date(Date.now() - DEFAULT_DAYS * 24 * 60 * 60 * 1000),
    to: new Date(),
  }));

  // Combined opens first because it is the only view that reconciles the sources against each
  // other; Gateway and APIs each show one source alone.
  return (
    <Tabs defaultValue="combined" className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<BarChart3 />}
        title="Usage"
        subtitle="What was spent, who spent it, and what the two sources say about each other."
        tabs={
          <div className="flex flex-wrap items-center justify-between gap-3">
            <TabsList>
              <TabsTrigger value="combined">Combined</TabsTrigger>
              <TabsTrigger value="gateway">Gateway</TabsTrigger>
              <TabsTrigger value="apis">APIs</TabsTrigger>
            </TabsList>
            {/* Above the tabs on purpose: it governs all three, so it cannot sit inside one. */}
            <AdvancedDatePicker value={period} onValueChange={setPeriod} />
          </div>
        }
      />
      <TabsContent value="combined" keepMounted>
        {combined(period)}
      </TabsContent>
      {/* keepMounted: switching to APIs and back must not reset the Gateway view's filters */}
      <TabsContent value="gateway" keepMounted>
        {gateway(period)}
      </TabsContent>
      <TabsContent value="apis">{apis(period)}</TabsContent>
    </Tabs>
  );
}
