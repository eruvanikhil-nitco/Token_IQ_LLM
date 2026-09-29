import RecommendationTabs from "./_components/RecommendationTabs";

export default function RecommendationsPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Recommendations</h1>
        <p className="text-sm text-muted-foreground">
          What is worth doing about this period, the evidence behind it, and what was already decided.
        </p>
      </div>
      <RecommendationTabs />
    </div>
  );
}
