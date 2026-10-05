"""Response shapes for the Overview page.

Every amount crosses as a string, exactly as the other money endpoints do: a JSON number is a
binary float by the time a browser has parsed it, and these figures are the ones a customer
reads off the screen and repeats.

An amount that cannot be computed is `None` rather than `"0"`. Zero asserts the company spent
nothing, which is a different and more dangerous claim than not knowing yet.
"""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel

MatchStatus: TypeAlias = Literal["matched", "gateway_saw_less", "gateway_saw_more", "not_seen_by_gateway"]
"""Deliberately four states rather than a boolean. A bill larger than the gateway's record and
one smaller than it are different problems, and a provider the gateway never saw is neither."""


class ProviderStandingResponse(BaseModel):
    provider: str
    billed: str
    recorded: str | None
    status: MatchStatus


class FreshnessResponse(BaseModel):
    source: str
    last_sync_at: str | None
    """None means never, which the screen says in words rather than leaving blank."""


class OverviewRecommendation(BaseModel):
    rule_id: str
    title: str
    kind: str
    figure: str | None
    figure_kind: str
    currency: str | None


class OverviewResponse(BaseModel):
    period_start: str
    period_end: str
    currency: str

    total: str | None
    previous_total: str | None
    change: str | None

    attributed: str | None
    unallocated: str | None
    unallocated_share: str | None

    providers: tuple[ProviderStandingResponse, ...]
    recommendations: tuple[OverviewRecommendation, ...]
    freshness: tuple[FreshnessResponse, ...]
