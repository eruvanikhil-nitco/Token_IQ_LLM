"use client";

import { usePeriod } from "@/app/(dashboard)/_scope/PeriodContext";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useDecideRecommendation,
  useRecommendations,
  useUndoRecommendation,
} from "@/app/(dashboard)/hooks/recommendations/useRecommendations";
import RecommendationCard from "./RecommendationCard";
import type { Recommendation, RecommendationDecision } from "@/components/networking";

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
  // From the scope bar, so a recommendation and the figure it is based on cover the same days.
  const { period } = usePeriod();
  const periodStart = period.start;
  const periodEnd = period.end;

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
      <p className="text-sm text-muted-foreground">
        What is worth doing between {periodStart} and {periodEnd}, the period in the top bar
      </p>

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
