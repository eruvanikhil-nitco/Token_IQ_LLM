"""What OpenRouter says one request cost.

The only provider that will price an individual call. Everyone else answers in daily
aggregates, so this is the one place a per-request comparison is possible at all, and the
gateway already stores the generation id it needs as the spend row's request_id.

The window is 30 days. Anything not fetched inside it is gone.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

GENERATION_URL: Final = "https://openrouter.ai/api/v1/generation"

MAX_LOOKUPS_PER_RUN: Final = 100
"""One HTTP call prices one request, against a per-key rate limit shared with the
customer's real traffic. A backlog is worked through over several runs rather than in one."""

_LOOKBACK_DAYS: Final = 29
"""OpenRouter keeps 30 days. Asking for the last 29 leaves a day of margin for a run that
is late or slow, without reaching for history that has already expired."""


def _decimal(value: object) -> Decimal | None:
    """json gives a float; str() keeps the digits the provider actually sent."""
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _tokens(data: Mapping[str, object], native_key: str, normalised_key: str) -> int | None:
    """The provider's own count, falling back to OpenRouter's normalised one.

    OpenRouter reports tokens twice: `tokens_prompt` normalised to a GPT tokenizer so
    models can be compared, and `native_tokens_prompt` as the underlying provider counted
    them. Cost is computed from the native figures, so storing the normalised ones beside
    a native cost invents a discrepancy that does not exist. Not every provider behind
    OpenRouter reports native counts, hence the fallback.
    """
    return _int(data.get(native_key)) if _int(data.get(native_key)) is not None else _int(data.get(normalised_key))


class OpenRouterBillingConnector:
    def __init__(
        self,
        unpriced_request_ids: Callable[[], Awaitable[Sequence[str]]],
        http_client_factory: Callable[[], Any],  # any-ok: the proxy's httpx wrapper is untyped
    ) -> None:
        self._unpriced_request_ids = unpriced_request_ids
        self._http_client_factory = http_client_factory

    @property
    def provider(self) -> str:
        return "openrouter"

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

        pending: Final = tuple(await self._unpriced_request_ids())[:MAX_LOOKUPS_PER_RUN]
        if not pending:
            return Fetched(facts=(), watermark=until)

        client: Final = self._http_client_factory()
        headers: Final = {"Authorization": f"Bearer {api_key}"}

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across awaits in a loop
        for generation_id in pending:
            response = await client.get(GENERATION_URL, params={"id": generation_id}, headers=headers)
            status: Final = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="openrouter rate limited this key", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"openrouter refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"openrouter returned {status}", retryable=True)

            payload = response.json()
            data = payload.get("data") if isinstance(payload, Mapping) else None
            if not isinstance(data, Mapping):
                continue
            cost = _decimal(data.get("total_cost"))
            if cost is None:
                continue

            facts.append(
                ProviderUsageFact(
                    fact_key=f"openrouter:{generation_id}",
                    provider="openrouter",
                    credential_name=credential_name,
                    grain="request",
                    bucket_start=until,
                    evidence="reconciled",
                    billed_cost=cost,
                    provider_request_id=generation_id,
                    model=_str(data.get("model")),
                    input_tokens=_tokens(data, "native_tokens_prompt", "tokens_prompt"),
                    output_tokens=_tokens(data, "native_tokens_completion", "tokens_completion"),
                )
            )

        return Fetched(facts=tuple(facts), watermark=until)


def build_unpriced_openrouter_lookup(prisma_client: Any) -> Callable[[], Awaitable[Sequence[str]]]:
    """Generation ids this gateway recorded that no fact has priced yet, newest first.

    Newest first because OpenRouter drops history after 30 days: given a backlog, the rows
    about to expire are worth less than the ones a customer is looking at today, and the
    old ones will still be there next run while the recent ones will not.
    """

    async def unpriced() -> Sequence[str]:
        rows: Final = await prisma_client.db.query_raw(
            """
            SELECT s.request_id
              FROM "LiteLLM_SpendLogs" s
              LEFT JOIN "LiteLLM_ProviderUsageFact" f
                     ON f.provider_request_id = s.request_id AND f.provider = 'openrouter'
             WHERE s.custom_llm_provider = 'openrouter'
               AND s.request_id LIKE 'gen-%'
               AND f.id IS NULL
               AND s."startTime" >= NOW() - ($1 || ' days')::interval
             ORDER BY s."startTime" DESC
             LIMIT 500
            """,
            str(_LOOKBACK_DAYS),
        )
        return tuple(
            found for row in rows if isinstance(found := row.get("request_id"), str)
        )

    return unpriced
