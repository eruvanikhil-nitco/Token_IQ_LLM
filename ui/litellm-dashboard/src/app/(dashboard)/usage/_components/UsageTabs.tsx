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
      <TabsContent value="gateway" className="pt-6">
        {gateway}
      </TabsContent>
      <TabsContent value="apis" className="pt-6">
        {apis}
      </TabsContent>
    </Tabs>
  );
}
