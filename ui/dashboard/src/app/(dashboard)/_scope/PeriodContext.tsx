"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { DEFAULT_PERIOD, PERIOD_CHOICES, periodFor, type Period, type PeriodChoice } from "./period";

/**
 * The one period every page that shows money reads.
 *
 * The blueprint puts a scope bar in the top bar and says every page respects it. This is the half
 * of it that exists: the period. The scope proper, organisation and team and project, arrives with
 * the task that enforces it server-side, because a picker that filtered nothing would promise
 * something no endpoint performs.
 *
 * Held in the shell rather than per page, which is what fixes the thing this replaces: three
 * copies of a period helper, two of which ran to today and one to the end of the month, so the
 * headline total and the ledger total described different periods and nothing said so.
 */

const STORAGE_KEY = "token-iq-period";
const MONTH_KEY = "token-iq-period-month";

interface PeriodState {
  choice: PeriodChoice;
  /** The month a reader named, for the `named-month` choice. Null for every relative choice. */
  month: string | null;
  period: Period;
  setChoice: (choice: PeriodChoice, month?: string | null) => void;
}

const PeriodStateContext = createContext<PeriodState | null>(null);

function isChoice(value: string | null): value is PeriodChoice {
  return value !== null && (PERIOD_CHOICES as readonly string[]).includes(value);
}

/**
 * What this viewer last chose, or the default.
 *
 * Wrapped because storage throws in a private window and comes back empty with site data cleared,
 * and a remembered period is a convenience rather than something a figure depends on.
 */
function remembered(): PeriodChoice {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isChoice(stored) ? stored : DEFAULT_PERIOD;
  } catch {
    return DEFAULT_PERIOD;
  }
}

function rememberedMonth(): string | null {
  try {
    return window.localStorage.getItem(MONTH_KEY);
  } catch {
    return null;
  }
}

function remember(choice: PeriodChoice, month: string | null): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, choice);
    if (month === null) {
      window.localStorage.removeItem(MONTH_KEY);
    } else {
      window.localStorage.setItem(MONTH_KEY, month);
    }
  } catch {
    // A viewer who cannot store a preference still gets a working period for this session.
  }
}

export function PeriodProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<PeriodChoice>(remembered);
  const [month, setMonthState] = useState<string | null>(rememberedMonth);

  const setChoice = useCallback((next: PeriodChoice, nextMonth: string | null = null) => {
    setChoiceState(next);
    setMonthState(nextMonth);
    remember(next, nextMonth);
  }, []);

  // Computed from the choice rather than stored, so a tab left open overnight does not keep
  // yesterday's "month to date" and report a day of spend as missing.
  const value = useMemo<PeriodState>(
    () => ({ choice, month, period: periodFor(choice, new Date(), month), setChoice }),
    [choice, month, setChoice],
  );

  return <PeriodStateContext.Provider value={value}>{children}</PeriodStateContext.Provider>;
}

/**
 * The period for this page.
 *
 * Outside the provider it answers the default rather than throwing: a page rendered in isolation,
 * which is what most of this suite does, should show a figure rather than an error.
 */
export function usePeriod(): PeriodState {
  const found = useContext(PeriodStateContext);
  if (found !== null) {
    return found;
  }
  return { choice: DEFAULT_PERIOD, month: null, period: periodFor(DEFAULT_PERIOD), setChoice: () => undefined };
}
