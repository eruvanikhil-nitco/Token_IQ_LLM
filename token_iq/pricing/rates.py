"""What a customer actually pays, as opposed to what a model costs at list.

The bundled price list and its history answer "what did this model cost on that day" for anybody.
A customer with a contract pays something else: a percentage off list across a provider, or a
committed price per million tokens for one model and one meter. Nothing in this product could
record either, so every figure it worked out for itself was list price, which for a customer with a
negotiated discount is wrong by exactly the discount they negotiated, in their favour, on the one
screen they check against their own invoice.

Two things here are refusals rather than answers, on purpose.

A period with no rate falls back to list price and says so. A missing rate is not a free month, and
a caller that reads "no rate" as zero turns real spend into free usage.

Two rates claiming the same model, the same meter and the same day are reported as a conflict
rather than resolved by picking one. Picking one means the figure depends on which row was written
first, which is not something anybody could work out from a screen, and the fix is for a person to
remove one of the two.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Final, TypeAlias

HUNDRED: Final = Decimal(100)
PER_MILLION: Final = Decimal(1_000_000)

PRICE_FIELDS: Final[tuple[str, ...]] = (
    "input_cost_per_token",
    "output_cost_per_token",
    "cache_read_input_token_cost",
    "cache_creation_input_token_cost",
)
"""The meters the price list prices, and therefore the ones a rate can name.

The same strings the bundled list and `price_as_of` use, rather than a second vocabulary: two names
for one meter is how a rate ends up applying to nothing.
"""


@dataclasses.dataclass(frozen=True, slots=True)
class Discount:
    """A percentage off whatever the list price is on the day.

    Expressed as the number a contract uses: 20 means twenty per cent off. It follows list price
    when list price changes, which is what a discount on a price list means.
    """

    percent_off: Decimal


@dataclasses.dataclass(frozen=True, slots=True)
class UnitPrice:
    """A committed price per million tokens, which replaces list rather than discounting it.

    Per million because that is the unit every provider quotes and every contract is written in.
    Stored per million and divided here, so the figure a person entered is the figure stored.
    """

    per_million: Decimal


RateBasis: TypeAlias = Discount | UnitPrice


@dataclasses.dataclass(frozen=True, slots=True)
class RateRule:
    """One thing a customer's contract says, with the period it says it for.

    `model` of None means every model of that provider, and `field` of None every meter. A period
    is required because a closed month must re-price with the rate that applied then: re-pricing
    last quarter at this quarter's rate produces a figure that still looks like a figure.
    """

    rate_id: str
    provider: str
    model: str | None
    field: str | None
    basis: RateBasis
    effective_from: date
    effective_to: date | None
    source: str
    """Where it came from, in the words of whoever entered it: a contract reference, an email, a
    renegotiation. A rate nobody can trace is a rate nobody will dare correct."""


@dataclasses.dataclass(frozen=True, slots=True)
class AppliedRate:
    rule: RateRule


@dataclasses.dataclass(frozen=True, slots=True)
class NoCustomerRate:
    """No contract covers this, so list price applies. Not free, and not an error."""


@dataclasses.dataclass(frozen=True, slots=True)
class ConflictingRates:
    """Two or more rates are equally specific and equally recent, so a person has to remove one."""

    rules: tuple[RateRule, ...]


RateAnswer: TypeAlias = AppliedRate | NoCustomerRate | ConflictingRates


def _in_force(rule: RateRule, when: date) -> bool:
    if rule.effective_from > when:
        return False
    return rule.effective_to is None or when <= rule.effective_to


def _matches(rule: RateRule, provider: str, model: str, field: str) -> bool:
    if rule.provider != provider:
        return False
    if rule.model is not None and rule.model != model:
        return False
    return rule.field is None or rule.field == field


def _specificity(rule: RateRule) -> int:
    """How closely a rule names the thing being priced: the model counts for more than the meter.

    A committed price for one model is the thing a customer negotiated; a provider-wide discount is
    the floor they fall back to.
    """
    return (2 if rule.model is not None else 0) + (1 if rule.field is not None else 0)


def effective_rate(
    rules: Sequence[RateRule],
    *,
    provider: str,
    model: str,
    field: str,
    when: date,
) -> RateAnswer:
    """Which of a customer's rates applies to one meter of one model on one day.

    The most specific rule in force wins, and the most recently effective of those. Equally
    specific and equally recent is a conflict rather than a coin toss.
    """
    candidates: Final = tuple(rule for rule in rules if _in_force(rule, when) and _matches(rule, provider, model, field))
    if not candidates:
        return NoCustomerRate()
    best: Final = max((_specificity(rule), rule.effective_from) for rule in candidates)
    winners: Final = tuple(
        rule for rule in candidates if (_specificity(rule), rule.effective_from) == best
    )
    return AppliedRate(rule=winners[0]) if len(winners) == 1 else ConflictingRates(rules=winners)


def cost_of(*, tokens: int, list_price_per_token: Decimal, rate: RateAnswer) -> Decimal | None:
    """What those tokens cost this customer, or None when nobody can say.

    None only for a conflict. Returning a figure from one of two conflicting rates would be a guess
    wearing the look of an answer, and the caller has somewhere to report the conflict instead.

    Nothing is rounded. The figures here are fractions of a cent per request, and a rounded rate
    manufactures a difference from the provider's own bill that a reader would spend a morning on.
    """
    match rate:
        case NoCustomerRate():
            return list_price_per_token * tokens
        case AppliedRate(rule=rule):
            return _at(rule.basis, tokens=tokens, list_price_per_token=list_price_per_token)
        case ConflictingRates():
            return None


def _at(basis: RateBasis, *, tokens: int, list_price_per_token: Decimal) -> Decimal:
    match basis:
        case Discount(percent_off=percent_off):
            return list_price_per_token * tokens * (HUNDRED - percent_off) / HUNDRED
        case UnitPrice(per_million=per_million):
            return per_million * tokens / PER_MILLION


def rate_problem(rule: RateRule) -> str | None:
    """Why this rate cannot be recorded, or None when it can.

    Checked before storing rather than when pricing, because a rate that cannot price anything is
    a row somebody will keep looking at and never see used.
    """
    if rule.effective_to is not None and rule.effective_to < rule.effective_from:
        return "The period ends before it starts."
    if rule.field is not None and rule.field not in PRICE_FIELDS:
        return f"{rule.field!r} is not a meter the price list prices: {', '.join(PRICE_FIELDS)}."
    return _basis_problem(rule)


def _basis_problem(rule: RateRule) -> str | None:
    match rule.basis:
        case Discount(percent_off=percent_off):
            if percent_off < 0:
                return (
                    "A discount cannot be negative. A price above list is recorded as a committed "
                    "price per million, so that the figure says what it is."
                )
            if percent_off > HUNDRED:
                return "A discount over a hundred per cent would make spend negative."
            return None
        case UnitPrice(per_million=per_million):
            if per_million < 0:
                return "A price cannot be negative."
            if rule.model is None:
                return "A committed price needs a model: one price across a catalogue prices a small model like a large one."
            if rule.field is None:
                return "A committed price needs a meter: input and output differ by a factor of three or more at list."
            return None
