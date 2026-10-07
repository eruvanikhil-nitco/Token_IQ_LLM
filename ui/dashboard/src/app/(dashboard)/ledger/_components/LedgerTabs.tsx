"use client";

import { useState } from "react";

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BILLING_PROVIDERS } from "@/components/model_add/credential_form_helpers";
import BillReconciliationView from "./BillReconciliationView";
import CostLedgerView from "./CostLedgerView";
import InvoicesView from "./InvoicesView";
import SeatsView from "./SeatsView";

/** The month that has most likely finished billing, which is the one a reader wants first. */
const defaultPeriod = (): { start: string; end: string } => {
  const now = new Date();
  const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const last = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0));
  return { start: first.toISOString().slice(0, 10), end: last.toISOString().slice(0, 10) };
};

export default function LedgerTabs() {
  const period = defaultPeriod();
  const [provider, setProvider] = useState<string>(BILLING_PROVIDERS[0].value);
  // Controlled, so an empty state can move the reader to the tab that fills it.
  const [tab, setTab] = useState("ledger");
  const [periodStart, setPeriodStart] = useState(period.start);
  const [periodEnd, setPeriodEnd] = useState(period.end);

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
        <label className="flex flex-col gap-1 text-sm">
          <span>Period start</span>
          <input
            aria-label="Period start"
            type="date"
            className="h-9 rounded-md border bg-background px-2"
            value={periodStart}
            onChange={(event) => setPeriodStart(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Period end</span>
          <input
            aria-label="Period end"
            type="date"
            className="h-9 rounded-md border bg-background px-2"
            value={periodEnd}
            onChange={(event) => setPeriodEnd(event.target.value)}
          />
        </label>
      </div>

      <Tabs value={tab} onValueChange={(next) => next !== null && setTab(next)}>
        <TabsList>
          <TabsTrigger value="ledger">Cost Ledger</TabsTrigger>
          <TabsTrigger value="reconciliation">Bill Reconciliation</TabsTrigger>
          <TabsTrigger value="invoices">Invoices</TabsTrigger>
          <TabsTrigger value="seats">Seats &amp; Commitments</TabsTrigger>
        </TabsList>
        {/* keepMounted: switching tabs must not discard a half-typed bill or reset the period */}
        <TabsContent value="ledger" className="pt-6" keepMounted>
          <CostLedgerView provider={provider} periodStart={periodStart} periodEnd={periodEnd} />
        </TabsContent>
        <TabsContent value="reconciliation" className="pt-6" keepMounted>
          <BillReconciliationView
            provider={provider}
            periodStart={periodStart}
            periodEnd={periodEnd}
            onEnterBill={() => setTab("invoices")}
          />
        </TabsContent>
        <TabsContent value="invoices" className="pt-6" keepMounted>
          <InvoicesView provider={provider} periodStart={periodStart} periodEnd={periodEnd} />
        </TabsContent>
        {/* keepMounted: switching tabs must not discard a half-typed seat */}
        <TabsContent value="seats" className="pt-6" keepMounted>
          <SeatsView periodStart={periodStart} periodEnd={periodEnd} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
