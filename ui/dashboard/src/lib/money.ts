/**
 * Money arrives from the proxy as an exact decimal digit string and is formatted here without
 * ever passing through a binary float, so a figure shown to a customer is the figure the
 * provider billed.
 *
 * Two decimal places is the default. The exception matters more than the rule: an amount that
 * is genuinely non-zero but smaller than a cent keeps enough digits to stay visible, because
 * "$0.00" asserts the company spent nothing and that is a different claim from "less than a
 * cent". An absent figure is a dash for the same reason.
 */

const SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "€",
  GBP: "£",
  JPY: "¥",
  INR: "₹",
};

const DECIMAL = /^(-?)(\d+)(?:\.(\d*))?$/;

const SIGNIFICANT_DIGITS = 2;
const DEFAULT_PLACES = 2;

/** Half-up rounding on the digit string itself, so no value is rounded through a float. */
function roundDigits(integer: string, fraction: string, places: number): { integer: string; fraction: string } {
  const kept = fraction.slice(0, places).padEnd(places, "0");
  const roundsUp = (fraction.charCodeAt(places) || 0) >= "5".charCodeAt(0);
  if (!roundsUp) return { integer, fraction: kept };

  const carried = (BigInt(integer + kept) + BigInt(1)).toString().padStart(kept.length + 1, "0");
  const cut = carried.length - places;
  return { integer: carried.slice(0, cut), fraction: carried.slice(cut) };
}

const groupThousands = (integer: string): string => integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/**
 * How many decimal places this amount needs to say something true.
 *
 * An amount of a cent or more needs two. One below that needs enough to reach its first
 * significant digits, so a real cost is never displayed as nothing.
 */
function placesFor(integer: string, fraction: string): number {
  if (BigInt(integer) !== BigInt(0)) return DEFAULT_PLACES;
  const firstSignificant = fraction.search(/[1-9]/);
  if (firstSignificant < 0) return DEFAULT_PLACES;
  return Math.max(DEFAULT_PLACES, firstSignificant + SIGNIFICANT_DIGITS);
}

const withCurrency = (sign: string, digits: string, currency: string | null): string => {
  const symbol = currency === null ? "" : SYMBOLS[currency];
  return symbol === undefined ? `${sign}${currency} ${digits}` : `${sign}${symbol}${digits}`;
};

/**
 * Every digit the provider billed, for the screens whose job is to reconcile.
 *
 * A ledger line and a bill-versus-gateway row have to add up against each other, and figures
 * rounded independently do not. Those screens show the exact amount; a headline tile, which
 * nothing is subtracted from, uses `formatMoney`.
 */
export function formatExactMoney(amount: string | null, currency: string | null): string {
  if (amount === null) return "—";
  const trimmed = amount.trim();
  if (trimmed === "") return "—";
  return withCurrency("", trimmed, currency);
}

export function formatMoney(amount: string | null, currency: string | null): string {
  if (amount === null) return "—";
  const trimmed = amount.trim();
  const parsed = DECIMAL.exec(trimmed);
  if (parsed === null) return "—";

  const [, sign, rawInteger, rawFraction = ""] = parsed;
  const rounded = roundDigits(rawInteger, rawFraction, placesFor(rawInteger, rawFraction));
  const trailing = rounded.fraction.replace(/(\.?\d*?)0+$/, "$1");
  const digits = `${groupThousands(rounded.integer.replace(/^0+(?=\d)/, ""))}.${
    trailing.length >= DEFAULT_PLACES ? trailing : rounded.fraction.slice(0, DEFAULT_PLACES)
  }`;

  return withCurrency(sign, digits, currency);
}
