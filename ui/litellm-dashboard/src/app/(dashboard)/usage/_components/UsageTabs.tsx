"use client";

import { BarChart3 } from "lucide-react";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/shared/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface UsageTabsProps {
  gateway: ReactNode;
  apis: ReactNode;
  combined: ReactNode;
}

export default function UsageTabs({ gateway, apis, combined }: UsageTabsProps) {
  // Combined opens first because it is the only view that reconciles the sources against each
  // other; Gateway and APIs each show one source alone and are unchanged.
  return (
    <Tabs defaultValue="combined" className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<BarChart3 />}
        title="Usage"
        subtitle="What was spent, who spent it, and what the two sources say about each other."
        tabs={
          <TabsList>
            <TabsTrigger value="combined">Combined</TabsTrigger>
            <TabsTrigger value="gateway">Gateway</TabsTrigger>
            <TabsTrigger value="apis">APIs</TabsTrigger>
          </TabsList>
        }
      />
      <TabsContent value="combined" keepMounted>
        {combined}
      </TabsContent>
      {/* keepMounted: switching to APIs and back must not reset the Gateway view's filters */}
      <TabsContent value="gateway" keepMounted>
        {gateway}
      </TabsContent>
      <TabsContent value="apis">{apis}</TabsContent>
    </Tabs>
  );
}
