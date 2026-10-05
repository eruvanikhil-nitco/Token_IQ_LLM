"""What OpenAI says our usage cost.

Day grain, like Anthropic, and for the same reason: OpenAI reports against its own project
and key rather than our teams.

Three things differ from Anthropic and each one is a silent trap. The amount is already in
dollars, not cents. The window is Unix seconds, not RFC 3339. And the amount is nested
under `amount.value` rather than sitting flat on the result.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Final

from token_iq.connectors.billing.cloud_rows import decimal_or_none, decoded_object
from token_iq.types.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

DEFAULT_BASE_URL: Final = "https://api.openai.com"

COSTS_PATH: Final = "/v1/organization/costs"

MAX_BUCKETS_PER_PAGE: Final = 31

MAX_PAGES_PER_RUN: Final = 12
"""A stop, so a paging bug cannot spin against the provider forever."""

UNATTRIBUTED: Final = "unattributed"


def _day(bucket: Mapping[str, object]) -> datetime | None:
    raw: Final = bucket.get("start_time")
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return None
    return datetime.fromtimestamp(int(raw), tz=timezone.utc)


MODEL_AND_METER: Final = ", "
"""What OpenAI puts between a model and the thing it is charging for."""


def split_line_item(line_item: str) -> tuple[str | None, str | None]:
    """A billing line item as the model it names and the meter it charges.

    OpenAI bills per line item, and the whole string used to go into `model`, so
    "gpt-4.1-2026-04-14, input" and "gpt-4.1-2026-04-14, output" read as two different models and
    nothing could total a model across its meters.

    Three shapes, and the discriminator for the last two is a space. A model id never contains one,
    so "web search tool calls" is a meter charged against no model, while "gpt-4o" is a model whose
    meter OpenAI did not state.
    """
    text: Final = line_item.strip()
    if not text:
        return None, None
    model, separator, meter = text.partition(MODEL_AND_METER)
    if separator:
        return model.strip() or None, meter.strip() or None
    return (None, text) if " " in text else (text, None)


def _facts_from(buckets: Sequence[object], credential_name: str) -> tuple[ProviderUsageFact, ...]:
    facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across buckets
    for bucket in buckets:
        if not isinstance(bucket, Mapping):
            continue
        day = _day(bucket)
        results = bucket.get("results")
        if day is None or not isinstance(results, Sequence):
            continue

        for item in results:
            if not isinstance(item, Mapping):
                continue
            amount = item.get("amount")
            dollars = decimal_or_none(amount.get("value")) if isinstance(amount, Mapping) else None
            if dollars is None:
                continue
            raw_line_item = item.get("line_item")
            line_item = raw_line_item if isinstance(raw_line_item, str) else UNATTRIBUTED
            model, meter = (None, None) if line_item == UNATTRIBUTED else split_line_item(line_item)
            facts.append(
                ProviderUsageFact(
                    fact_key=f"openai:{credential_name}:{day.date().isoformat()}:{line_item}",
                    provider="openai",
                    credential_name=credential_name,
                    grain="day",
                    bucket_start=day,
                    evidence="reconciled",
                    billed_cost=dollars,
                    model=model,
                    meter=meter,
                    raw=dict(item),
                )
            )
    return tuple(facts)


class OpenAIBillingConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: untyped httpx wrapper
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._http_client_factory = http_client_factory
        self._costs_url = f"{base_url.rstrip('/')}{COSTS_PATH}"

    @property
    def provider(self) -> str:
        return "openai"

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
        headers: Final = {"Authorization": f"Bearer {api_key}"}
        params: dict[str, object] = {  # mutable-ok: the page cursor advances across requests
            "start_time": int(since.timestamp()),
            "end_time": int(until.timestamp()),
            "bucket_width": "1d",
            "group_by[]": "line_item",
            "limit": MAX_BUCKETS_PER_PAGE,
        }

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        for _ in range(MAX_PAGES_PER_RUN):
            response = await client.get(self._costs_url, params=dict(params), headers=headers)
            status: Final = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="openai rate limited this key", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"openai refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"openai returned {status}", retryable=True)

            payload = decoded_object(response.text)
            if payload is None:
                return FetchFailed(reason="openai returned a body that is not an object", retryable=True)

            buckets = payload.get("data")
            if isinstance(buckets, Sequence) and not isinstance(buckets, (str, bytes)):
                facts.extend(_facts_from(buckets, credential_name))

            next_page = payload.get("next_page")
            if not payload.get("has_more") or not isinstance(next_page, str):
                break
            params["page"] = next_page

        return Fetched(facts=tuple(facts), watermark=until)
