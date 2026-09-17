"use client";

import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface UsageTabsProps {
  gateway: ReactNode;
  apis: ReactNode;
}

export default function UsageTabs({ gateway, apis }: UsageTabsProps) {
  return (
    <Tabs defaultValue="gateway">
      <TabsList>
        <TabsTrigger value="gateway">Gateway</TabsTrigger>
        <TabsTrigger value="apis">APIs</TabsTrigger>
      </TabsList>
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
