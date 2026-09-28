"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useAttributionRules,
  useDeleteAttributionRule,
  useSaveAttributionRule,
} from "@/app/(dashboard)/hooks/attribution/useAttributionRules";
import type { AttributionOwnerType } from "@/components/networking";

const OWNER_TYPES: readonly AttributionOwnerType[] = ["team", "project", "user"] as const;

interface RuleTableProps {
  provider: string;
}

export default function RuleTable({ provider }: RuleTableProps) {
  const { data, isLoading, error } = useAttributionRules();
  const save = useSaveAttributionRule();
  const remove = useDeleteAttributionRule();

  const [account, setAccount] = useState("");
  const [ownerType, setOwnerType] = useState<AttributionOwnerType>("team");
  const [ownerId, setOwnerId] = useState("");

  const rules = (data?.rules ?? []).filter((rule) => rule.provider === provider);
  const canSave = account.trim() !== "" && ownerId.trim() !== "" && !save.isPending;

  const onSave = async () => {
    const draft = {
      provider,
      match_value: account.trim(),
      owner_type: ownerType,
      owner_id: ownerId.trim(),
    };
    await save.mutateAsync(draft);
    setAccount("");
    setOwnerId("");
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        A rule says which team, project or user owns a provider account. Spend that reached this account without passing
        through the gateway is assigned to whoever owns it. An account can have one owner, so saving a rule for an
        account that already has one moves it.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span>Provider account</span>
          <Input
            aria-label="Provider account"
            value={account}
            onChange={(event) => setAccount(event.target.value)}
            placeholder="the credential name in Data Sources"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Owner type</span>
          <select
            aria-label="Owner type"
            className="h-9 rounded-md border bg-background px-2"
            value={ownerType}
            onChange={(event) => setOwnerType(event.target.value as AttributionOwnerType)}
          >
            {OWNER_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Owner</span>
          <Input
            aria-label="Owner"
            value={ownerId}
            onChange={(event) => setOwnerId(event.target.value)}
            placeholder="team, project or user id"
          />
        </label>
        <Button onClick={onSave} disabled={!canSave}>
          {save.isPending ? "Saving…" : "Save rule"}
        </Button>
      </div>

      {save.isError && <p className="text-sm text-destructive">Could not save that rule.</p>}
      {remove.isError && (
        <p className="text-sm text-destructive">Could not remove that rule, so its spend is still assigned.</p>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Reading the rules…</p>}
      {error && <p className="text-sm text-destructive">Could not read the rules.</p>}

      {!isLoading && rules.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No rules for this provider yet, so all of its unmatched spend is unassigned.
        </p>
      )}

      {rules.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Provider account</th>
                <th className="py-2 pr-4">Owner</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.rule_id} className="border-b last:border-0">
                  <td className="py-2 pr-4">{rule.match_value}</td>
                  <td className="py-2 pr-4">
                    {rule.owner_type}: {rule.owner_id}
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      variant="ghost"
                      aria-label={`Remove the rule for ${rule.match_value}`}
                      onClick={() => remove.mutate(rule.rule_id)}
                      disabled={remove.isPending}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
