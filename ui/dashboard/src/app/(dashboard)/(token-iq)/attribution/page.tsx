import AttributionTabs from "./_components/AttributionTabs";

export default function AttributionRulesPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Attribution Rules</h1>
        <p className="text-sm text-muted-foreground">
          Decide who owns spend that reached a provider without passing through the gateway.
        </p>
      </div>
      <AttributionTabs />
    </div>
  );
}
