"""What this build reads from each provider, in the words the What We Fetch tab shows.

Deliberately modest: every line describes behaviour that exists in this repository today.
A backfill depth or an earliest available date we have not verified against a real account
would read as a promise, and the first customer to check it would find it wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from litellm.provider_billing.runner import LOOKBACK
from litellm.provider_billing.scheduled import INTERVAL_SECONDS
from litellm.types.proxy.provider_billing import UsageGrain

_NO_BACKFILL: Final = (
    "Each run re-reads the most recent window. There is no first-connection backfill yet, so "
    "cost from before this connection was made is not loaded."
)


@dataclass(frozen=True, slots=True)
class FetchProfile:
    provider: str
    display_name: str
    endpoint: str
    endpoint_url: str
    grain: UsageGrain
    refresh_seconds: int
    window_hours: int
    delay_note: str
    history_note: str


def _profile(
    provider: str, display_name: str, endpoint: str, endpoint_url: str, grain: UsageGrain, delay_note: str
) -> FetchProfile:
    return FetchProfile(
        provider=provider,
        display_name=display_name,
        endpoint=endpoint,
        endpoint_url=endpoint_url,
        grain=grain,
        refresh_seconds=INTERVAL_SECONDS,
        window_hours=int(LOOKBACK.total_seconds() // 3600),
        delay_note=delay_note,
        history_note=_NO_BACKFILL,
    )


FETCH_PROFILES: Final[Mapping[str, FetchProfile]] = MappingProxyType(
    {
        "openai": _profile(
            "openai",
            "OpenAI",
            "Organization Costs",
            "https://api.openai.com/v1/organization/costs",
            "day",
            "OpenAI reports cost by day for the whole organisation, so the finest comparison "
            "against gateway traffic is by model and day. Recent days can still change.",
        ),
        "anthropic": _profile(
            "anthropic",
            "Anthropic",
            "Admin Cost Report",
            "https://api.anthropic.com/v1/organizations/cost_report",
            "day",
            "Anthropic reports cost by day against its own workspace rather than our teams, so "
            "the finest comparison against gateway traffic is by model and day.",
        ),
        "openrouter": _profile(
            "openrouter",
            "OpenRouter",
            "Generation",
            "https://openrouter.ai/api/v1/generation",
            "request",
            "OpenRouter prices each request individually, so every gateway request can be "
            "checked against what OpenRouter charged for it. OpenRouter drops this history "
            "after about 30 days, so the newest requests are read first.",
        ),
        "bedrock": _profile(
            "bedrock",
            "Amazon Bedrock",
            "Cost Explorer",
            "https://ce.us-east-1.amazonaws.com/",
            "day",
            "Cost Explorer reports by day and settles over the following days, so the most "
            "recent day is deliberately not read until it stops moving.",
        ),
    }
)
