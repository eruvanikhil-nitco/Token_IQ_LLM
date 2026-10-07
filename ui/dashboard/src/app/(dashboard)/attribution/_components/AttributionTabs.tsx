"use client";

import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BILLING_PROVIDERS } from "@/components/model_add/credential_form_helpers";
import RuleTable from "./RuleTable";
import UnmatchedPanel from "./UnmatchedPanel";

const DAYS = 30;

export default function AttributionTabs() {
  const [provider, setProvider] = useState<string>(BILLING_PROVIDERS[0].value);

  return (
    <div className="flex flex-col gap-6">
      <label className="flex w-fit flex-col gap-1 text-sm">
        <span>Provider</span>
        <select
          aria-label="Provider"
          className="h-9 rounded-md border bg-background px-2"
          value={provider}
          onChange={(event) => setProvider(event.target.value)}
        >
          {BILLING_PROVIDERS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <Tabs defaultValue="accounts">
        <TabsList>
          <TabsTrigger value="accounts">Cloud Accounts</TabsTrigger>
          <TabsTrigger value="unmatched">Unmatched</TabsTrigger>
        </TabsList>
        {/* keepMounted: switching tabs must not discard the rule being typed or reset the filter */}
        <TabsContent value="accounts" className="pt-6" keepMounted>
          <RuleTable provider={provider} />
        </TabsContent>
        <TabsContent value="unmatched" className="pt-6" keepMounted>
          <UnmatchedPanel provider={provider} days={DAYS} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
