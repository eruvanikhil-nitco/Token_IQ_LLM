"use client";

import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useDecideRecommendation,
  useRecommendations,
  useUndoRecommendation,
} from "@/app/(dashboard)/hooks/recommendations/useRecommendations";
import RecommendationCard from "./RecommendationCard";
import type { Recommendation, RecommendationDecision } from "@/components/networking";

/** The month so far, which is the period a reader is deciding about right now. */
const defaultPeriod = (): { start: string; end: string } => {
  const now = new Date();
  const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  return { start: first.toISOString().slice(0, 10), end: now.toISOString().slice(0, 10) };
};

interface CardListProps {
  cards: Recommendation[];
  empty: string;
  onDecide: (ruleId: string, state: RecommendationDecision) => void;
  onUndo: (ruleId: string) => void;
  busy: boolean;
}

function CardList({ cards, empty, onDecide, onUndo, busy }: CardListProps) {
  if (cards.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="flex flex-col gap-4">
      {cards.map((card) => (
        <RecommendationCard key={card.rule_id} recommendation={card} onDecide={onDecide} onUndo={onUndo} busy={busy} />
      ))}
    </div>
  );
}

export default function RecommendationTabs() {
  const period = defaultPeriod();
  const [periodStart, setPeriodStart] = useState(period.start);
  const [periodEnd, setPeriodEnd] = useState(period.end);

  const { data, isLoading, error } = useRecommendations(periodStart, periodEnd);
  const decide = useDecideRecommendation();
  const undo = useUndoRecommendation();

  const busy = decide.isPending || undo.isPending;
  const onDecide = (ruleId: string, state: RecommendationDecision) => decide.mutate({ ruleId, state });
  const onUndo = (ruleId: string) => undo.mutate(ruleId);

  const open = data?.open ?? [];
  const decided = data?.decided ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-3">
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

      {isLoading && <p className="text-sm text-muted-foreground">Working out what is worth doing...</p>}
      {error && <p className="text-sm text-destructive">The recommendations could not be read.</p>}

      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="business">Business</TabsTrigger>
          <TabsTrigger value="technical">Technical</TabsTrigger>
          <TabsTrigger value="decided">Done &amp; Dismissed</TabsTrigger>
        </TabsList>
        <TabsContent value="all" className="pt-6">
          <CardList
            cards={open}
            empty="Nothing needs attention for this period."
            onDecide={onDecide}
            onUndo={onUndo}
            busy={busy}
          />
        </TabsContent>
        <TabsContent value="business" className="pt-6">
          <CardList
            cards={open.filter((card) => card.kind === "business")}
            empty="Nothing for the business side to act on for this period."
            onDecide={onDecide}
            onUndo={onUndo}
            busy={busy}
          />
        </TabsContent>
        <TabsContent value="technical" className="pt-6">
          <CardList
            cards={open.filter((card) => card.kind === "technical")}
            empty="Nothing for the engineering side to act on for this period."
            onDecide={onDecide}
            onUndo={onUndo}
            busy={busy}
          />
        </TabsContent>
        <TabsContent value="decided" className="pt-6">
          <CardList
            cards={decided}
            empty="Nothing has been marked done or dismissed yet."
            onDecide={onDecide}
            onUndo={onUndo}
            busy={busy}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
