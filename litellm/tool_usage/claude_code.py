"""What each person spent inside Claude Code, per day.

Anthropic publishes this per actor per day with a cost per model, which makes it the richest
per-person source any tool offers. Two things about it are easy to get wrong and expensive.

The cost is in minor currency units, so a reported 186 is one dollar eighty-six. Storing it
verbatim overstates a customer's Claude Code spend a hundredfold, and it is the same trap the
Anthropic billing connector already has to avoid.

A record's `customer_type` says whether the money is already on a bill we read. `api` means it
was charged to the organisation's Anthropic account, which the Anthropic billing connector
already reports, so adding this row to a total would count it twice. `subscription` means it
sits on a Pro, Team or Enterprise plan and is genuinely separate money.

The endpoint returns one day per request, so a window is walked a day at a time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Final

from litellm.provider_billing.cloud_rows import decimal_or_none, decoded_object, utc_day_start
from litellm.types.proxy.tool_usage import (
    CostBasis,
    ToolFetched,
    ToolFetchFailed,
    ToolFetchResult,
    ToolName,
    ToolNotConfigured,
    ToolUsageFact,
)

DEFAULT_BASE_URL: Final = "https://api.anthropic.com"

USAGE_REPORT_PATH: Final = "/v1/organizations/usage_report/claude_code"

ANTHROPIC_VERSION: Final = "2023-06-01"

MAX_RECORDS_PER_PAGE: Final = 1000
"""The maximum the reference allows. Asking for more is a 400 on the first real call."""

MAX_PAGES_PER_DAY: Final = 20

MAX_DAYS_PER_RUN: Final = 31
"""One request per day, so an unbounded window would be an unbounded number of requests."""

MINOR_UNITS_PER_MAJOR: Final = Decimal(100)


def _basis_for(customer_type: object) -> CostBasis:
    """Whether this money is already on a provider bill we read.

    Anything other than a subscription is treated as already counted. That is the safe
    direction: under-counting a total is a figure a customer can question, while over-counting
    their Anthropic spend by the whole of their Claude Code usage is one they cannot.
    """
    return "new_money" if customer_type == "subscription" else "already_on_a_provider_bill"


def _person_for(actor: object) -> str | None:
    """The human this usage belongs to, or the API key when no human is named.

    A row attributed to an API key has no person to bill, but dropping it would lose real
    spend, so it is kept under the key's name and the screen can say so.
    """
    if not isinstance(actor, Mapping):
        return None
    if isinstance(email := actor.get("email_address"), str) and email:
        return email
    if isinstance(key_name := actor.get("api_key_name"), str) and key_name:
        return f"api key: {key_name}"
    return None


def _day_for(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed: Final = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return utc_day_start(parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc))


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _tokens_from(tokens: object, key: str) -> int | None:
    return _int_or_none(tokens.get(key)) if isinstance(tokens, Mapping) else None


def _facts_from(record: Mapping[str, object], credential_name: str) -> tuple[ToolUsageFact, ...]:
    """One fact per model in a record, because a person can use several in a day."""
    person: Final = _person_for(record.get("actor"))
    day: Final = _day_for(record.get("date"))
    if person is None or day is None:
        return ()

    basis: Final = _basis_for(record.get("customer_type"))
    breakdown: Final = record.get("model_breakdown")
    if not isinstance(breakdown, Sequence) or isinstance(breakdown, (str, bytes)):
        return ()

    return tuple(
        ToolUsageFact(
            tool="claude_code",
            person=person,
            day=day,
            cost=minor / MINOR_UNITS_PER_MAJOR,
            currency=currency if isinstance(currency := cost.get("currency"), str) and currency else "USD",
            basis=basis,
            model=model if isinstance(model := entry.get("model"), str) else None,
            input_tokens=_tokens_from(entry.get("tokens"), "input"),
            output_tokens=_tokens_from(entry.get("tokens"), "output"),
            sessions=_sessions_of(record),
        )
        for entry in breakdown
        if isinstance(entry, Mapping)
        and isinstance(cost := entry.get("estimated_cost"), Mapping)
        and (minor := decimal_or_none(cost.get("amount"))) is not None
        and minor >= 0
    )


def _sessions_of(record: Mapping[str, object]) -> int | None:
    core: Final = record.get("core_metrics")
    return _int_or_none(core.get("num_sessions")) if isinstance(core, Mapping) else None


def _days_in(since: datetime, until: datetime) -> tuple[datetime, ...]:
    first: Final = utc_day_start(since)
    span: Final = min((utc_day_start(until) - first).days + 1, MAX_DAYS_PER_RUN)
    return tuple(first + timedelta(days=offset) for offset in range(max(span, 0)))


class ClaudeCodeConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: the proxy's httpx wrapper is untyped
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._http_client_factory = http_client_factory
        self._usage_url = f"{base_url.rstrip('/')}{USAGE_REPORT_PATH}"

    @property
    def tool(self) -> ToolName:
        return "claude_code"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> ToolFetchResult:
        api_key: Final = credential_values.get("api_key")
        if not api_key:
            return ToolNotConfigured(reason=f"credential {credential_name} carries no api_key")

        client: Final = self._http_client_factory()
        headers: Final = MappingProxyType({"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION})

        facts: Final[list[ToolUsageFact]] = []  # mutable-ok: accumulated across days and pages
        for day in _days_in(since, until):
            params: dict[str, object] = {  # mutable-ok: the page cursor advances across requests
                "starting_at": day.strftime("%Y-%m-%d"),
                "limit": MAX_RECORDS_PER_PAGE,
            }
            for _ in range(MAX_PAGES_PER_DAY):
                response = await client.get(self._usage_url, params=MappingProxyType(dict(params)), headers=headers)
                status: Final = getattr(response, "status_code", 0)
                if status == 429:
                    return ToolFetchFailed(reason="anthropic rate limited this key", retryable=True)
                if status in (401, 403):
                    return ToolFetchFailed(reason=f"anthropic refused credential {credential_name}", retryable=False)
                if status != 200:
                    return ToolFetchFailed(reason=f"anthropic returned {status}", retryable=True)

                payload = decoded_object(response.text)
                if payload is None:
                    return ToolFetchFailed(reason="anthropic returned a body that is not an object", retryable=True)

                records = payload.get("data")
                if isinstance(records, Sequence) and not isinstance(records, (str, bytes)):
                    facts.extend(
                        fact
                        for record in records
                        if isinstance(record, Mapping)
                        for fact in _facts_from(record, credential_name)
                    )

                next_page = payload.get("next_page")
                if not payload.get("has_more") or not isinstance(next_page, str) or not next_page:
                    break
                params["page"] = next_page

        return ToolFetched(facts=tuple(facts), watermark=until)
