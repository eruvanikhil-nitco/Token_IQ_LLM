"""Request and response shapes for Pricing & Rates.

Every amount crosses as a string. A discount of 13.5 per cent and a committed price of 2.50 per
million are figures a person read off a contract, and a float would round one of them somewhere
between here and the screen.
"""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, Field


class RateBody(BaseModel):
    """What an administrator sends after reading a contract.

    `basis` decides which amount is required, and the server refuses the combinations that cannot
    price anything: a committed price with no model, or with no meter.
    """

    provider: str
    model: str | None = Field(default=None, description="Null for every model of that provider")
    field: str | None = Field(default=None, description="Null for every meter, for a discount")
    basis: Literal["discount", "unit_price"]
    percent_off: str | None = Field(default=None, description="Exact digits, for a discount: 20 means 20%")
    per_million: str | None = Field(default=None, description="Exact digits, for a committed price per million tokens")
    effective_from: str = Field(description="First day it applies, as YYYY-MM-DD")
    effective_to: str | None = Field(default=None, description="Last day it applies. Null while still in force")
    source: str = Field(description="Where it came from: a contract reference, an email, a renegotiation")


class RateResponse(BaseModel):
    rate_id: str
    provider: str
    model: str | None
    field: str | None
    basis: Literal["discount", "unit_price"]
    percent_off: str | None
    per_million: str | None
    effective_from: str
    effective_to: str | None
    source: str


class RateListResponse(BaseModel):
    rates: tuple[RateResponse, ...]


class RateDeletedResponse(BaseModel):
    deleted: bool


class RateApplied(BaseModel):
    """The rate that prices one meter of one model today, and what it makes a million tokens cost."""

    kind: Literal["applied"] = "applied"
    rate: RateResponse
    cost_per_million: str


class ListPriceApplies(BaseModel):
    """No contract covers this, so list price does. Not free, and not an error."""

    kind: Literal["list_price"] = "list_price"
    cost_per_million: str


class RatesConflict(BaseModel):
    """Two rates are equally specific and equally recent, so nothing can be priced until a person
    removes one. Reported rather than resolved, because resolving it silently would make the figure
    depend on which row was written first."""

    kind: Literal["conflict"] = "conflict"
    rates: tuple[RateResponse, ...]


class PriceUnknown(BaseModel):
    """Neither the price history nor the bundled list knows this model and meter.

    Its own state rather than a zero: a caller that read an unknown price as free would turn real
    spend into free usage.
    """

    kind: Literal["unknown"] = "unknown"
    reason: str


EffectiveRateResponse: TypeAlias = RateApplied | ListPriceApplies | RatesConflict | PriceUnknown


class CurrencyRateBody(BaseModel):
    """What an administrator sends after their finance team books a rate.

    One direction only: the rate that converts `source_currency` into `target_currency`. A pair
    needed the other way round is a second row, because inverting one here would report a figure
    nobody entered.
    """

    source_currency: str = Field(min_length=3, max_length=3, description="The currency being converted, as ISO 4217")
    target_currency: str = Field(min_length=3, max_length=3, description="The currency being reported in")
    rate: str = Field(description="Exact digits: how many of the target one unit of the source buys")
    effective_from: str = Field(description="First day it applies, as YYYY-MM-DD")
    effective_to: str | None = Field(default=None, description="Last day it applies. Null while still in force")
    source: str = Field(description="Where the rate came from: the month's booked rate, a bank, a contract")


class CurrencyRateResponse(BaseModel):
    rate_id: str
    source_currency: str
    target_currency: str
    rate: str
    effective_from: str
    effective_to: str | None
    source: str


class CurrencyRateListResponse(BaseModel):
    rates: tuple[CurrencyRateResponse, ...]


class ConversionNotNeeded(BaseModel):
    """Both currencies are the same, so nothing is converted and no rate is involved."""

    kind: Literal["not_needed"] = "not_needed"


class ConversionAvailable(BaseModel):
    kind: Literal["available"] = "available"
    rate: CurrencyRateResponse


class ConversionUnavailable(BaseModel):
    """Nobody recorded this pair for this day.

    Its own state, and the message names the direction to record. A rate recorded the other way
    round is not inverted: one divided by a rate is a figure nobody entered, and its last digits
    would be a rounding this product chose on a customer's behalf.
    """

    kind: Literal["unavailable"] = "unavailable"
    source_currency: str
    target_currency: str
    reason: str


class ConversionConflict(BaseModel):
    """Two rates for one pair are equally recent, so a person has to remove one."""

    kind: Literal["conflict"] = "conflict"
    rates: tuple[CurrencyRateResponse, ...]


ConversionResponse: TypeAlias = (
    ConversionNotNeeded | ConversionAvailable | ConversionUnavailable | ConversionConflict
)
