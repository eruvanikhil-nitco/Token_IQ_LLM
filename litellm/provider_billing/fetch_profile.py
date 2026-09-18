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

from litellm.provider_billing.bedrock import SETTLING_HOURS
from litellm.provider_billing.runner import LOOKBACK
from litellm.provider_billing.scheduled import INTERVAL_SECONDS
from litellm.types.proxy.provider_billing import UsageGrain

_NO_BACKFILL: Final = (
    "Each run re-reads the most recent window. There is no first-connection backfill yet, so "
    "cost from before this connection was made is not loaded."
)

_NO_VERIFIED_SETTLING: Final = (
    "How long this provider keeps adjusting recent figures has not been verified against "
    "a real account, so treat the most recent days as provisional."
)

_BEDROCK_SETTLING_NOTE: Final = (
    f"Cost Explorer settles over about {SETTLING_HOURS} hours, so the most recent day is "
    "deliberately not read until it stops moving."
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
    settling_note: str


def _profile(
    provider: str,
    display_name: str,
    endpoint: str,
    endpoint_url: str,
    grain: UsageGrain,
    delay_note: str,
    settling_note: str,
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
        settling_note=settling_note,
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
            _NO_VERIFIED_SETTLING,
        ),
        "anthropic": _profile(
            "anthropic",
            "Anthropic",
            "Admin Cost Report",
            "https://api.anthropic.com/v1/organizations/cost_report",
            "day",
            "Anthropic reports cost by day against its own workspace rather than our teams, so "
            "the finest comparison against gateway traffic is by model and day.",
            _NO_VERIFIED_SETTLING,
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
            _NO_VERIFIED_SETTLING,
        ),
        "bedrock": _profile(
            "bedrock",
            "Amazon Bedrock",
            "Cost Explorer",
            "https://ce.us-east-1.amazonaws.com/",
            "day",
            "Cost Explorer reports by day and settles over the following days, so the most "
            "recent day is deliberately not read until it stops moving.",
            _BEDROCK_SETTLING_NOTE,
        ),
        "azure": _profile(
            "azure",
            "Azure",
            "Cost Management query",
            "https://management.azure.com/",
            "day",
            "Azure reports cloud cost by day for the whole subscription rather than per model, "
            "so the finest comparison against gateway traffic is by service and day. Recent "
            "days can still change.",
            _NO_VERIFIED_SETTLING,
        ),
        "vertex_ai": _profile(
            "vertex_ai",
            "Google Vertex AI",
            "BigQuery billing export",
            "https://bigquery.googleapis.com/",
            "day",
            "Google publishes no billing API for this, so figures come from a detailed "
            "billing export the customer enables into BigQuery, and that export lands hours "
            "behind.",
            _NO_VERIFIED_SETTLING,
        ),
    }
)
