"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DECISION_LABEL, FIGURE_LABEL, KIND_LABEL, formatFigure } from "./recommendationDisplay";
import type { Recommendation } from "@/components/networking";

interface RecommendationCardProps {
  recommendation: Recommendation;
  onDecide: (ruleId: string, state: "done" | "dismissed") => void;
  onUndo: (ruleId: string) => void;
  busy: boolean;
}

export default function RecommendationCard({ recommendation, onDecide, onUndo, busy }: RecommendationCardProps) {
  const figure = formatFigure(recommendation.figure, recommendation.figure_kind, recommendation.currency);

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase text-muted-foreground">{KIND_LABEL[recommendation.kind]}</span>
          <h3 className="text-base font-semibold">{recommendation.title}</h3>
        </div>
        {/* No figure block at all when there is nothing honest to show, rather than a zero */}
        {figure !== "" && (
          <div className="text-right">
            <p className="text-xl font-semibold">{figure}</p>
            <p className="text-xs text-muted-foreground">{FIGURE_LABEL[recommendation.figure_kind]}</p>
          </div>
        )}
      </div>

      <p className="text-sm text-muted-foreground">{recommendation.noticed}</p>

      <div className="flex flex-col gap-1">
        <p className="text-xs uppercase text-muted-foreground">Evidence</p>
        <table className="w-full max-w-md text-sm">
          <tbody>
            {recommendation.evidence.map((item, index) => (
              <tr key={`${item.label}-${index}`}>
                <td className="py-1 pr-4 text-muted-foreground">{item.label}</td>
                <td className="py-1">{item.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-sm">
        <span className="text-muted-foreground">Who should act: </span>
        {recommendation.who_should_act}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {recommendation.state === null ? (
          <>
            <Button
              variant="outline"
              disabled={busy}
              aria-label={`Mark done: ${recommendation.title}`}
              onClick={() => onDecide(recommendation.rule_id, "done")}
            >
              Mark done
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              aria-label={`Dismiss: ${recommendation.title}`}
              onClick={() => onDecide(recommendation.rule_id, "dismissed")}
            >
              Dismiss
            </Button>
          </>
        ) : (
          <>
            <span className="text-sm text-muted-foreground">{DECISION_LABEL[recommendation.state]}</span>
            <Button
              variant="ghost"
              disabled={busy}
              aria-label={`Bring back: ${recommendation.title}`}
              onClick={() => onUndo(recommendation.rule_id)}
            >
              Bring back
            </Button>
          </>
        )}
      </div>
    </Card>
  );
}
