import LedgerTabs from "./_components/LedgerTabs";

export default function LedgerPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Ledger</h1>
        <p className="text-sm text-muted-foreground">
          Every cost line the providers reported, the bills they sent, and what the difference is.
        </p>
      </div>
      <LedgerTabs />
    </div>
  );
}
