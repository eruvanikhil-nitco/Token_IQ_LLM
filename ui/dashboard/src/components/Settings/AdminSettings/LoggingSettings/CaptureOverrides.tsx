"use client";

import React, { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  effectiveForProvider,
  effectiveForTeam,
  filterByName,
  ruleFor,
  withRule,
  type CaptureRule,
  type CaptureTable,
} from "./captureRules";

const RULE_OPTIONS: readonly { readonly value: CaptureRule; readonly label: string }[] = [
  { value: "default", label: "Use default" },
  { value: "capture", label: "Capture" },
  { value: "exclude", label: "Never capture" },
];

// Below this many rows the eye finds a name faster than the keyboard, and an always-present
// search box over three rows is clutter.
const SEARCH_THRESHOLD = 5;

interface TeamRow {
  readonly team_id: string;
  readonly team_alias?: string | null;
}

interface CaptureOverridesProps {
  readonly teams: readonly TeamRow[];
  readonly providers: readonly string[];
  readonly globalDefault: boolean;
  readonly teamTable: CaptureTable | undefined;
  readonly providerTable: CaptureTable | undefined;
  readonly onTeamTableChange: (next: CaptureTable) => void;
  readonly onProviderTableChange: (next: CaptureTable) => void;
  readonly disabled?: boolean;
}

/** One subject as the table renders it: the key its rule is stored under, plus what it resolves to. */
interface RuleRow {
  readonly key: string;
  readonly label: string;
  readonly rule: CaptureRule;
  readonly captured: boolean;
}

interface RuleSectionProps {
  readonly title: string;
  readonly subtitle?: string;
  readonly subjectHeader: string;
  readonly rows: readonly RuleRow[];
  readonly total: number;
  readonly search: string;
  readonly onSearchChange: (next: string) => void;
  readonly searchLabel: string;
  readonly emptyMessage: string;
  readonly noMatchMessage: string;
  readonly disabled?: boolean;
  readonly onRuleChange: (key: string, rule: CaptureRule) => void;
}

const SectionBody: React.FC<RuleSectionProps> = ({
  subjectHeader,
  rows,
  total,
  emptyMessage,
  noMatchMessage,
  disabled,
  onRuleChange,
}) => {
  if (total === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{noMatchMessage}</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{subjectHeader}</TableHead>
          <TableHead>Rule</TableHead>
          <TableHead>Effective</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.key}>
            <TableCell className="font-medium">{row.label}</TableCell>
            <TableCell>
              <select
                aria-label={`Capture rule for ${row.label}`}
                className="rounded-md border border-border bg-background px-2 py-1 text-sm"
                value={row.rule}
                disabled={disabled}
                onChange={(event) => onRuleChange(row.key, event.target.value as CaptureRule)}
              >
                {RULE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </TableCell>
            <TableCell>
              {row.captured ? <Badge variant="secondary">Stored</Badge> : <Badge variant="outline">Not stored</Badge>}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

const RuleSection: React.FC<RuleSectionProps> = (props) => (
  <div>
    <p className="mb-2 text-sm font-medium">{props.title}</p>
    {props.subtitle !== undefined && <p className="mb-2 text-xs text-muted-foreground">{props.subtitle}</p>}
    {props.total >= SEARCH_THRESHOLD && (
      <Input
        aria-label={props.searchLabel}
        placeholder={`${props.searchLabel}...`}
        value={props.search}
        onChange={(event) => props.onSearchChange(event.target.value)}
        className="mb-2 max-w-xs"
      />
    )}
    <SectionBody {...props} />
  </div>
);

/**
 * Per-team and per-provider rules for storing prompts and responses.
 *
 * Three states rather than a switch, because "follow the default" has to stay distinct from
 * "never capture". A team left on the default follows the gateway; a team set to never capture
 * keeps that answer even if the gateway default is turned on later.
 *
 * Teams come first because that is the order the gateway resolves them in, and because these
 * rules are almost always written about people rather than providers.
 *
 * Search only hides rows. Rules live in the table rather than in what is rendered, so editing
 * one subject while others are filtered out leaves their rules untouched.
 */
const CaptureOverrides: React.FC<CaptureOverridesProps> = ({
  teams,
  providers,
  globalDefault,
  teamTable,
  providerTable,
  onTeamTableChange,
  onProviderTableChange,
  disabled,
}) => {
  const [teamSearch, setTeamSearch] = useState("");
  const [providerSearch, setProviderSearch] = useState("");

  const teamRows: readonly RuleRow[] = useMemo(() => {
    const named = teams.map((team) => ({ team, label: team.team_alias || team.team_id }));
    return filterByName(named, (entry) => entry.label, teamSearch).map(({ team, label }) => ({
      key: label,
      label,
      rule: ruleFor(teamTable, label),
      captured: effectiveForTeam(teamTable, team.team_id, team.team_alias ?? undefined, globalDefault),
    }));
  }, [teams, teamSearch, teamTable, globalDefault]);

  const providerRows: readonly RuleRow[] = useMemo(
    () =>
      filterByName(providers, (provider) => provider, providerSearch).map((provider) => ({
        key: provider,
        label: provider,
        rule: ruleFor(providerTable, provider),
        captured: effectiveForProvider(providerTable, provider, globalDefault),
      })),
    [providers, providerSearch, providerTable, globalDefault],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Who gets recorded</CardTitle>
        <p className="text-sm text-muted-foreground">
          Prompts and responses are stored per request: a team rule wins, then a provider rule, then the gateway default
          above. Everything else about a request, who called, what it cost, how many tokens, is always recorded.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <RuleSection
          title="Teams"
          subjectHeader="Team"
          rows={teamRows}
          total={teams.length}
          search={teamSearch}
          onSearchChange={setTeamSearch}
          searchLabel="Search teams"
          emptyMessage="No teams yet."
          noMatchMessage={`No teams match "${teamSearch}".`}
          disabled={disabled}
          onRuleChange={(key, rule) => onTeamTableChange(withRule(teamTable, key, rule))}
        />
        <RuleSection
          title="Providers"
          subtitle="Applies only where the team above has no rule of its own."
          subjectHeader="Provider"
          rows={providerRows}
          total={providers.length}
          search={providerSearch}
          onSearchChange={setProviderSearch}
          searchLabel="Search providers"
          emptyMessage="No providers configured."
          noMatchMessage={`No providers match "${providerSearch}".`}
          disabled={disabled}
          onRuleChange={(key, rule) => onProviderTableChange(withRule(providerTable, key, rule))}
        />
      </CardContent>
    </Card>
  );
};

export default CaptureOverrides;
