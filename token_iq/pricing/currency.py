"""One reporting currency, using a rate the customer recorded and never one we invented.

Every figure in this product carries the currency it was billed in, and totals are reported per
currency, because adding two of them produces a number in no currency at all. That is right and it
is not enough: a customer with invoices in two currencies wants one figure for the board, and the
only honest way to give them one is with a rate they entered, dated, with where it came from.

Three refusals hold the line, and each one is a thing a reader can act on.

A pair nobody recorded is not converted, and the total refuses rather than leaving that money out.
Silently excluding it is the worst of the three options available: the figure looks complete and is
short by exactly the amount nobody could convert.

A rate recorded in the other direction is not inverted. One divided by 1.08 is a figure nobody
entered, and its last digits are a rounding this code chose. Recording the direction being reported
in is a minute's work and the refusal names it.

Two rates for one pair on one day are a conflict, for the same reason two prices for one model are:
resolving it silently makes the figure depend on which row was written first.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final, TypeAlias


@dataclasses.dataclass(frozen=True, slots=True)
class CurrencyRate:
    """One rate a customer booked a period at, in one direction.

    `rate` is how many units of the target currency one unit of the source buys: a rate of 1.08 on
    EUR to USD turns fifty euros into fifty-four dollars. Exact digits, because a month's spend
    multiplied by a rounded rate differs from the finance team's own figure by more than the
    rounding.
    """

    rate_id: str
    source_currency: str
    target_currency: str
    rate: Decimal
    effective_from: date
    effective_to: date | None
    source: str
    """Where the rate came from, in the words of whoever entered it. A conversion nobody can trace
    is a figure a finance team will not repeat."""


@dataclasses.dataclass(frozen=True, slots=True)
class SameCurrency:
    """Nothing to convert. Its own answer so a screen never says "converted at 1.0"."""


@dataclasses.dataclass(frozen=True, slots=True)
class UseRate:
    rate: CurrencyRate


@dataclasses.dataclass(frozen=True, slots=True)
class NoConversionRate:
    """Nobody recorded this pair for this day, so nothing here can convert it."""

    source: str
    target: str


@dataclasses.dataclass(frozen=True, slots=True)
class RateConflict:
    """Two rates for one pair are equally recent, so a person has to remove one."""

    rates: tuple[CurrencyRate, ...]


Conversion: TypeAlias = SameCurrency | UseRate | NoConversionRate | RateConflict


def _in_force(rate: CurrencyRate, when: date) -> bool:
    if rate.effective_from > when:
        return False
    return rate.effective_to is None or when <= rate.effective_to


def conversion(
    rates: Sequence[CurrencyRate],
    *,
    source: str,
    target: str,
    when: date,
) -> Conversion:
    """How to turn one currency into another on one day, or why nothing can.

    Only the direction asked for: a rate recorded the other way round is a different row to record,
    not a division to perform here.
    """
    if source == target:
        return SameCurrency()
    candidates: Final = tuple(
        rate
        for rate in rates
        if rate.source_currency == source and rate.target_currency == target and _in_force(rate, when)
    )
    if not candidates:
        return NoConversionRate(source=source, target=target)
    newest: Final = max(rate.effective_from for rate in candidates)
    winners: Final = tuple(rate for rate in candidates if rate.effective_from == newest)
    return UseRate(rate=winners[0]) if len(winners) == 1 else RateConflict(rates=winners)


@dataclasses.dataclass(frozen=True, slots=True)
class AppliedConversion:
    """What was converted, at which rate, and where that rate came from."""

    source: str
    target: str
    amount: Decimal
    rate: Decimal
    converted: Decimal
    rate_source: str


@dataclasses.dataclass(frozen=True, slots=True)
class OneTotal:
    """One figure in the reporting currency, with every conversion that went into it."""

    currency: str
    amount: Decimal
    applied: tuple[AppliedConversion, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class MissingRates:
    """At least one currency could not be converted, so there is no single figure.

    `by_currency` travels with the refusal so a screen can still show what it does know. Nothing
    here is dropped: a total short by the money nobody could convert looks complete and is wrong.
    """

    pairs: tuple[tuple[str, str], ...]
    by_currency: Mapping[str, Decimal]


ConversionOutcome: TypeAlias = OneTotal | MissingRates


def convert_total(
    by_currency: Mapping[str, Decimal],
    *,
    into: str,
    rates: Sequence[CurrencyRate],
    when: date,
) -> ConversionOutcome:
    """Per-currency totals as one figure in the reporting currency, or a refusal naming what is
    missing.

    Takes the mapping `total_of` already produces, so the arithmetic that must not lose a digit and
    the rule about what may be added stay in separate places.
    """
    answers: Final = tuple((currency, conversion(rates, source=currency, target=into, when=when)) for currency, _ in sorted(by_currency.items()))
    missing: Final = tuple(
        (currency, into) for currency, answer in answers if isinstance(answer, (NoConversionRate, RateConflict))
    )
    if missing:
        return MissingRates(pairs=missing, by_currency=MappingProxyType(dict(by_currency)))

    applied: Final = tuple(
        AppliedConversion(
            source=currency,
            target=into,
            amount=by_currency[currency],
            rate=answer.rate.rate,
            converted=by_currency[currency] * answer.rate.rate,
            rate_source=answer.rate.source,
        )
        for currency, answer in answers
        if isinstance(answer, UseRate)
    )
    unconverted: Final = sum(
        (by_currency[currency] for currency, answer in answers if isinstance(answer, SameCurrency)),
        Decimal(0),
    )
    return OneTotal(
        currency=into,
        amount=unconverted + sum((conversion_.converted for conversion_ in applied), Decimal(0)),
        applied=applied,
    )
