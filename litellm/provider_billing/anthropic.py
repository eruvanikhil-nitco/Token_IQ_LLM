"""What Anthropic says our usage cost.

Day grain: Anthropic reports daily aggregates against its own workspace and key, not our
teams, so a fact here cannot be split back to a team. What it answers is whether the
provider's charge for a day matches what this gateway recorded for it.

Two traps live in this response and both are silent. `amount` is in cents as a decimal
string, so 123.45 is one dollar twenty-three. And one bucket carries a row per token type,
so the rows have to be summed per model or the same day's cost lands several times over.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

COST_REPORT_URL: Final = "https://api.anthropic.com/v1/organizations/cost_report"

ANTHROPIC_VERSION: Final = "2023-06-01"

MAX_BUCKETS_PER_PAGE: Final = 31
"""Anthropic's documented maximum for daily buckets."""

MAX_PAGES_PER_RUN: Final = 12
"""A stop, so a paging bug cannot spin against the provider forever."""

_CENTS_PER_DOLLAR: Final = Decimal(100)

UNATTRIBUTED: Final = "unattributed"
"""Web search and code execution charges carry no model."""


def _decimal(value: object) -> Decimal | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _day(bucket: Mapping[str, object]) -> datetime | None:
    raw: Final = bucket.get("starting_at")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _facts_from(buckets: Sequence[object], credential_name: str) -> tuple[ProviderUsageFact, ...]:
    """One fact per model per day, summing the token-type rows within a bucket."""
    facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across buckets
    for bucket in buckets:
        if not isinstance(bucket, Mapping):
            continue
        day = _day(bucket)
        results = bucket.get("results")
        if day is None or not isinstance(results, Sequence):
            continue

        per_model: dict[str, Decimal] = defaultdict(Decimal)  # mutable-ok: accumulator per bucket
        for item in results:
            if not isinstance(item, Mapping):
                continue
            cents = _decimal(item.get("amount"))
            if cents is None:
                continue
            model = item.get("model")
            per_model[model if isinstance(model, str) else UNATTRIBUTED] += cents / _CENTS_PER_DOLLAR

        facts.extend(
            ProviderUsageFact(
                fact_key=f"anthropic:{day.date().isoformat()}:{model}",
                provider="anthropic",
                credential_name=credential_name,
                grain="day",
                bucket_start=day,
                evidence="reconciled",
                billed_cost=dollars,
                model=None if model == UNATTRIBUTED else model,
            )
            for model, dollars in sorted(per_model.items())
        )
    return tuple(facts)


class AnthropicBillingConnector:
    def __init__(self, http_client_factory: Callable[[], Any]) -> None:  # any-ok: untyped httpx wrapper
        self._http_client_factory = http_client_factory

    @property
    def provider(self) -> str:
        return "anthropic"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        api_key: Final = credential_values.get("api_key")
        if not api_key:
            return NotConfigured(reason=f"credential {credential_name} carries no api_key")

        client: Final = self._http_client_factory()
        headers: Final = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
        params: dict[str, object] = {  # mutable-ok: the page cursor advances across requests
            "starting_at": since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ending_at": until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bucket_width": "1d",
            "group_by[]": "description",
            "limit": MAX_BUCKETS_PER_PAGE,
        }

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        for _ in range(MAX_PAGES_PER_RUN):
            response = await client.get(COST_REPORT_URL, params=dict(params), headers=headers)
            status: Final = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="anthropic rate limited this key", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"anthropic refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"anthropic returned {status}", retryable=True)

            payload = response.json()
            if not isinstance(payload, Mapping):
                return FetchFailed(reason="anthropic returned a body that is not an object", retryable=True)

            buckets = payload.get("data")
            if isinstance(buckets, Sequence) and not isinstance(buckets, (str, bytes)):
                facts.extend(_facts_from(buckets, credential_name))

            next_page = payload.get("next_page")
            if not payload.get("has_more") or not isinstance(next_page, str):
                break
            params["page"] = next_page

        return Fetched(facts=tuple(facts), watermark=until)
