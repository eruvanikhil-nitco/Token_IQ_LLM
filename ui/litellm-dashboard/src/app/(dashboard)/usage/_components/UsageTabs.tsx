"use client";

import type { ReactNode } from "react";
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
    <Tabs defaultValue="combined">
      <TabsList>
        <TabsTrigger value="combined">Combined</TabsTrigger>
        <TabsTrigger value="gateway">Gateway</TabsTrigger>
        <TabsTrigger value="apis">APIs</TabsTrigger>
      </TabsList>
      <TabsContent value="combined" className="pt-6" keepMounted>
        {combined}
      </TabsContent>
      {/* keepMounted: switching to APIs and back must not reset the Gateway view's filters */}
      <TabsContent value="gateway" className="pt-6" keepMounted>
        {gateway}
      </TabsContent>
      <TabsContent value="apis" className="pt-6">
        {apis}
      </TabsContent>
    </Tabs>
  );
}
