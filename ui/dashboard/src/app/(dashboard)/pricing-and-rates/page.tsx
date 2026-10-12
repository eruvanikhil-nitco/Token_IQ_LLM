"use client";

import { Receipt } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CostTrackingSettings } from "@/app/(dashboard)/cost-tracking/_components";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";

import ContractedRatesPanel from "./_components/ContractedRatesPanel";
import CurrencyRatesPanel from "./_components/CurrencyRatesPanel";

/**
 * Administration > Pricing & Rates. Cost Tracking under the name section 12's label table gives it.
 *
 * Three tabs, two of them new. "Effective rates" is what the blueprint asks for: the contracted
 * discounts and committed prices that decide what a customer actually pays, each dated and
 * attributable. "Currency" is the rate a period was booked at.
 *
 * The third keeps every control the Cost Tracking page had, under a name that says what those
 * controls move. They are not the same thing as a contracted rate and the difference matters: the
 * provider discount there is applied by the gateway when it records a request, so it changes the
 * gateway's own figure from that moment on and cannot re-price a month already recorded. A rate on
 * the first tab is applied when a figure is read, carries the period it applies to, and can
 * therefore re-price a closed month at the rate that applied then.
 */
export default function PricingAndRatesPage() {
  const { accessToken, userRole, userId } = useAuthorized();

  return (
    <main className="flex h-full flex-col gap-6 p-8">
      <PageHeader
        icon={<Receipt />}
        title="Pricing & Rates"
        subtitle="Contracted rates, effective prices and currency conversion. What you actually pay, as opposed to what a model costs at list."
      />
      <Tabs defaultValue="effective-rates">
        <TabsList variant="line" className="h-auto w-max flex-nowrap justify-start">
          <TabsTrigger value="effective-rates" className="flex-none">
            Effective rates
          </TabsTrigger>
          <TabsTrigger value="currency" className="flex-none">
            Currency
          </TabsTrigger>
          <TabsTrigger value="gateway" className="flex-none">
            Gateway cost settings
          </TabsTrigger>
        </TabsList>
        <TabsContent value="effective-rates" className="pt-6">
          <ContractedRatesPanel />
        </TabsContent>
        <TabsContent value="currency" className="pt-6">
          <CurrencyRatesPanel />
        </TabsContent>
        <TabsContent value="gateway" className="pt-6">
          <p className="max-w-3xl pb-2 text-sm text-muted-foreground">
            These change the figure the gateway records for a request, from the moment they are saved, and cannot
            re-price a month already recorded. A contracted rate on the first tab is applied when a figure is read
            and carries the period it applies to, which is what lets a closed month price at the rate that applied
            then
          </p>
          <CostTrackingSettings userID={userId} userRole={userRole} accessToken={accessToken} />
        </TabsContent>
      </Tabs>
    </main>
  );
}
