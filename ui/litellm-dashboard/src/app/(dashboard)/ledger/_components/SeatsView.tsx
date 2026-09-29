"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDeleteSeat, useSaveSeat, useSeats } from "@/app/(dashboard)/hooks/seats/useSeats";
import { useUserCosts } from "@/app/(dashboard)/hooks/seats/useUserCosts";
import { formatAmount } from "./ledgerDisplay";
import { CADENCE_LABEL, hasNoSeats } from "./seatsDisplay";
import type { SeatCadence } from "@/components/networking";

const CADENCES: readonly SeatCadence[] = ["monthly", "annual"] as const;

interface SeatsViewProps {
  periodStart: string;
  periodEnd: string;
}

export default function SeatsView({ periodStart, periodEnd }: SeatsViewProps) {
  const currency = "USD";
  const { data: seats, isLoading, error } = useSeats();
  const { data: costs } = useUserCosts(periodStart, periodEnd, currency);
  const save = useSaveSeat();
  const remove = useDeleteSeat();

  const [tool, setTool] = useState("claude-code");
  const [person, setPerson] = useState("");
  const [amount, setAmount] = useState("");
  const [cadence, setCadence] = useState<SeatCadence>("monthly");

  const canSave = person.trim() !== "" && amount.trim() !== "" && !save.isPending;

  const onSave = async () => {
    const draft = {
      tool: tool.trim(),
      user_id: person.trim(),
      cadence,
      currency,
      amount: amount.trim(),
      period_start: periodStart,
      period_end: periodEnd,
    };
    await save.mutateAsync(draft);
    setPerson("");
    setAmount("");
  };

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        A seat is a flat per-person subscription, read off a contract rather than an API. It counts toward that
        person&apos;s cost for the period it covers, and is never spread across days: a daily share of a monthly fee is
        a number nobody was charged.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span>Tool</span>
          <Input aria-label="Tool" value={tool} onChange={(event) => setTool(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Person</span>
          <Input
            aria-label="Person"
            value={person}
            onChange={(event) => setPerson(event.target.value)}
            placeholder="the user id"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Cadence</span>
          <select
            aria-label="Cadence"
            className="h-9 rounded-md border bg-background px-2"
            value={cadence}
            onChange={(event) => setCadence(event.target.value as SeatCadence)}
          >
            {CADENCES.map((option) => (
              <option key={option} value={option}>
                {CADENCE_LABEL[option]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Seat amount</span>
          <Input
            aria-label="Seat amount"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder="as written on the contract"
          />
        </label>
        <Button onClick={onSave} disabled={!canSave}>
          {save.isPending ? "Saving…" : "Save seat"}
        </Button>
      </div>

      {save.isError && <p className="text-sm text-destructive">Could not save that seat.</p>}
      {remove.isError && (
        <p className="text-sm text-destructive">Could not remove that seat, so it is still being counted.</p>
      )}
      {isLoading && <p className="text-sm text-muted-foreground">Reading the seats…</p>}
      {error && <p className="text-sm text-destructive">Could not read the seats.</p>}

      {!isLoading && (seats?.seats.length ?? 0) === 0 && (
        <p className="text-sm text-muted-foreground">No subscriptions assigned yet.</p>
      )}

      {(seats?.seats.length ?? 0) > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4">Tool</th>
                <th className="py-2 pr-4">Person</th>
                <th className="py-2 pr-4">Cadence</th>
                <th className="py-2 pr-4">Amount</th>
                <th className="py-2 pr-4">Period</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {(seats?.seats ?? []).map((seat) => (
                <tr key={seat.seat_id} className="border-b last:border-0">
                  <td className="py-2 pr-4">{seat.tool}</td>
                  <td className="py-2 pr-4">{seat.user_id}</td>
                  <td className="py-2 pr-4">{CADENCE_LABEL[seat.cadence]}</td>
                  <td className="py-2 pr-4">{formatAmount(seat.amount, seat.currency)}</td>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {seat.period_start} to {seat.period_end}
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      variant="ghost"
                      aria-label={`Remove the ${seat.tool} seat for ${seat.user_id}`}
                      onClick={() => remove.mutate(seat.seat_id)}
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

      {costs !== undefined && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">What each person cost, {costs.currency}</p>
          <p className="text-sm text-muted-foreground">{costs.costs[0]?.note ?? ""}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-4">Person</th>
                  <th className="py-2 pr-4">Gateway</th>
                  <th className="py-2 pr-4">Subscriptions</th>
                  <th className="py-2 pr-4">Total</th>
                  <th className="py-2">Made up of</th>
                </tr>
              </thead>
              <tbody>
                {costs.costs.map((cost) => (
                  <tr key={cost.user_id} className="border-b last:border-0">
                    <td className="py-2 pr-4">{cost.user_id}</td>
                    <td className="py-2 pr-4">{formatAmount(cost.gateway, cost.currency)}</td>
                    <td className="py-2 pr-4">{formatAmount(cost.seats, cost.currency)}</td>
                    <td className="py-2 pr-4">{formatAmount(cost.total, cost.currency)}</td>
                    <td className="py-2">
                      {hasNoSeats(cost)
                        ? "gateway traffic only"
                        : cost.seat_lines
                            .map((line) => `${line.tool} ${formatAmount(line.amount, line.currency)}`)
                            .join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
