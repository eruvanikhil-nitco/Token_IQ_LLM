"use client";

import { useState } from "react";

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BILLING_PROVIDERS } from "@/components/model_add/credential_form_helpers";
import BillReconciliationView from "./BillReconciliationView";
import CostLedgerView from "./CostLedgerView";
import InvoicesView from "./InvoicesView";
import { enterBillHref, monthOfPeriod } from "@/app/(dashboard)/(token-iq)/data-sources/_components/invoiceSubmit";
import SeatsView from "./SeatsView";
import { usePeriod } from "@/app/(dashboard)/_scope/PeriodContext";

export default function LedgerTabs() {
  // The period comes from the scope bar in the top bar rather than from controls on this page.
  // There were three copies of a period helper and they disagreed: this page ran to the end of the
  // month while the Overview page ran to today, so the two totals described different periods.
  const { period } = usePeriod();
  const periodStart = period.start;
  const periodEnd = period.end;
  const [provider, setProvider] = useState<string>(BILLING_PROVIDERS[0].value);
  // Controlled, so an empty state can move the reader to the tab that fills it.
  const [tab, setTab] = useState("ledger");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1 text-sm">
          <Label htmlFor="ledger-provider">Provider</Label>
          <Select
            items={BILLING_PROVIDERS}
            value={provider}
            onValueChange={(next) => next !== null && setProvider(next)}
          >
            <SelectTrigger id="ledger-provider" aria-label="Provider" className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {BILLING_PROVIDERS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <p className="self-end text-sm text-muted-foreground">
          {periodStart} to {periodEnd}, from the period in the top bar
        </p>
      </div>

      <Tabs value={tab} onValueChange={(next) => next !== null && setTab(next)}>
        <TabsList>
          <TabsTrigger value="ledger">Cost Ledger</TabsTrigger>
          <TabsTrigger value="reconciliation">Bill Reconciliation</TabsTrigger>
          <TabsTrigger value="invoices">Invoices</TabsTrigger>
          <TabsTrigger value="seats">Seats &amp; Commitments</TabsTrigger>
        </TabsList>
        {/* keepMounted: switching tabs must not discard a half-typed seat or reset the period */}
        <TabsContent value="ledger" className="pt-6" keepMounted>
          <CostLedgerView provider={provider} periodStart={periodStart} periodEnd={periodEnd} />
        </TabsContent>
        <TabsContent value="reconciliation" className="pt-6" keepMounted>
          <BillReconciliationView
            provider={provider}
            periodStart={periodStart}
            periodEnd={periodEnd}
            enterBillHref={enterBillHref({ provider, month: monthOfPeriod(periodStart) })}
          />
        </TabsContent>
        <TabsContent value="invoices" className="pt-6" keepMounted>
          <InvoicesView provider={provider} periodStart={periodStart} />
        </TabsContent>
        {/* keepMounted: switching tabs must not discard a half-typed seat */}
        <TabsContent value="seats" className="pt-6" keepMounted>
          <SeatsView periodStart={periodStart} periodEnd={periodEnd} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
