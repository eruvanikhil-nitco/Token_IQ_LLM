import React from "react";
import type { components } from "@/lib/http/schema";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

export type ProviderCoverage = components["schemas"]["ProviderCourierCoverageResponse"];
export type TeamCourierCoverage = components["schemas"]["TeamCourierCoverageResponse"];
export type ApiAccessMode = TeamCourierCoverage["api_access_mode"];

export interface CourierModeSettingsProps {
  apiAccessMode: ApiAccessMode;
  onApiAccessModeChange: (mode: ApiAccessMode) => void;
  coverage: ProviderCoverage[];
  /** How many of this team's keys do not name the account they spend against. */
  unboundKeyCount: number;
  disabled?: boolean;
}

const MODES: ReadonlyArray<{ value: ApiAccessMode; label: string; blurb: string }> = [
  {
    value: "both",
    label: "Either",
    blurb:
      "Apps may use each provider's own address or the shared one. Use this to move applications across a few at a time.",
  },
  {
    value: "courier",
    label: "Courier only",
    blurb:
      "Only each provider's own address. Every request from this team is one the gateway never opened, and the shared address is refused.",
  },
  {
    value: "translator",
    label: "Translating only",
    blurb:
      "Only the shared address, where apps write one common format and the gateway converts it. The provider addresses are refused.",
  },
];

type CoverageState = "blocked" | "billingGap" | "covered";

const coverageState = (entry: ProviderCoverage): CoverageState => {
  if (!entry.has_route) return "blocked";
  if (!entry.reads_usage) return "billingGap";
  return "covered";
};

const STATE_ICON: Record<CoverageState, React.ReactNode> = {
  blocked: <XCircle className="size-4 shrink-0 text-destructive" />,
  billingGap: <AlertTriangle className="size-4 shrink-0 text-warning" />,
  covered: <CheckCircle2 className="size-4 shrink-0 text-success" />,
};

const CoverageRow: React.FC<{ entry: ProviderCoverage }> = ({ entry }) => {
  const state = coverageState(entry);

  return (
    <div className="flex flex-col gap-1 py-2">
      <div className="flex items-center gap-2">
        {STATE_ICON[state]}
        <span className="font-medium">{entry.provider}</span>
        {state === "billingGap" && <Badge variant="destructive">Records no cost</Badge>}
        {state === "blocked" && <Badge variant="secondary">Unavailable</Badge>}
      </div>
      <p className="pl-6 text-sm text-muted-foreground">{entry.summary}</p>
    </div>
  );
};

const CourierModeSettings: React.FC<CourierModeSettingsProps> = ({
  apiAccessMode,
  onApiAccessModeChange,
  coverage,
  unboundKeyCount,
  disabled = false,
}) => {
  const showsCourierDetail = apiAccessMode !== "translator";

  return (
    <Card className="p-4">
      <h3 className="text-base font-semibold">How this team reaches the models</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        A request is translated or not according to the address it arrives at. This chooses which of those addresses
        this team may use. Spend, tokens and logs are recorded either way.
      </p>

      <fieldset className="mt-3 flex flex-col gap-2" disabled={disabled}>
        <legend className="sr-only">How this team reaches the models</legend>
        {MODES.map((mode) => (
          <label
            key={mode.value}
            className="flex cursor-pointer items-start gap-3 rounded-md border p-3 has-checked:border-primary has-disabled:cursor-not-allowed has-disabled:opacity-60"
          >
            <input
              type="radio"
              name="api-access-mode"
              className="mt-1"
              value={mode.value}
              checked={apiAccessMode === mode.value}
              disabled={disabled}
              onChange={() => onApiAccessModeChange(mode.value)}
            />
            <span className="text-sm">
              <span className="font-medium">{mode.label}</span>
              <span className="mt-0.5 block text-muted-foreground">{mode.blurb}</span>
            </span>
          </label>
        ))}
      </fieldset>

      {apiAccessMode === "courier" && (
        <div className="mt-3 flex items-start gap-2 rounded-md bg-muted p-3">
          <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            This one is not a silent change. Applications written against the shared address will be refused until they
            are updated. Pick Either instead if this team still has apps to move.
          </p>
        </div>
      )}

      {showsCourierDetail && (
        <>
          <Separator className="my-4" />
          <h4 className="text-sm font-semibold">What each provider will do</h4>
          <div className="mt-1 divide-y">
            {coverage.map((entry) => (
              <CoverageRow key={entry.provider} entry={entry} />
            ))}
          </div>

          {unboundKeyCount > 0 && (
            <div className="mt-4 flex items-start gap-2 rounded-md border border-warning p-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
              <div className="text-sm">
                <p className="font-medium">
                  {unboundKeyCount} key{unboundKeyCount === 1 ? "" : "s"} on this team name no account
                </p>
                <p className="mt-1 text-muted-foreground">
                  A key that names the account it spends against is charged to exactly that one, and its spend records
                  say so. A key that names none is charged to whichever account this gateway finds first for the
                  provider, which for a customer holding more than one account at a provider may not be the intended
                  one.
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  );
};

export default CourierModeSettings;
