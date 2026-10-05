"""What each person spent inside Cursor, per day.

Cursor reports one row per request rather than a daily total, so a day's cost for a person is
the sum of their events that day. Rolling up here rather than storing every event is deliberate:
a busy team produces hundreds of thousands of rows a month, and nothing downstream asks a
question that needs one.

Cursor buys the models itself and bills the customer, so none of this appears on a provider
bill we read. Every fact is new money, unlike Claude Code on an API organisation.

Two details are easy to get wrong. `chargedCents` is cents and is fractional, so 21.36232 is
twenty-one and a third cents, and dividing by a hundred must not round. And `timestamp` is
epoch milliseconds delivered as a string, not a number and not a date.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Final

from litellm.types.proxy.tool_usage import (
    ToolFetched,
    ToolFetchFailed,
    ToolFetchResult,
    ToolName,
    ToolNotConfigured,
    ToolUsageFact,
)
from token_iq.connectors.billing.cloud_rows import decimal_or_none, decoded_object, utc_day_start

DEFAULT_BASE_URL: Final = "https://api.cursor.com"

USAGE_EVENTS_PATH: Final = "/teams/filtered-usage-events"

MAX_EVENTS_PER_PAGE: Final = 1000
"""The maximum the reference allows."""

MAX_PAGES_PER_WINDOW: Final = 50
"""Usage events allow sixty requests a minute, so one run must not try to drain a huge backlog."""

MAX_DAYS_PER_REQUEST: Final = 30
"""The window the team endpoints accept in one call, so a longer period is split."""

CENTS_PER_UNIT: Final = Decimal(100)

_MILLISECONDS: Final = 1000


def _epoch_millis(moment: datetime) -> int:
    return int(moment.timestamp() * _MILLISECONDS)


def _day_of(timestamp: object) -> datetime | None:
    """The UTC day an event belongs to.

    Cursor sends epoch milliseconds as a string. Accepting a number too costs nothing and means
    a change of mind on their side does not silently drop every event.
    """
    if isinstance(timestamp, bool) or not isinstance(timestamp, (str, int, Decimal)):
        return None
    try:
        millis: Final = int(Decimal(str(timestamp)))
    except ArithmeticError:
        return None
    return utc_day_start(datetime.fromtimestamp(millis / _MILLISECONDS, tz=timezone.utc))


def _tokens_of(event: Mapping[str, object], key: str) -> int:
    usage: Final = event.get("tokenUsage")
    if not isinstance(usage, Mapping):
        return 0
    value: Final = usage.get(key)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _windows(since: datetime, until: datetime) -> tuple[tuple[datetime, datetime], ...]:
    """The period split into chunks the endpoint will accept."""
    span: Final = timedelta(days=MAX_DAYS_PER_REQUEST)
    starts: Final = tuple(
        since + span * index for index in range((max((until - since).days, 0) // MAX_DAYS_PER_REQUEST) + 1)
    )
    return tuple((start, min(start + span, until)) for start in starts if start < until)


def _rolled_up(events: Sequence[Mapping[str, object]]) -> tuple[ToolUsageFact, ...]:
    """One fact per person, day and model, summed from that person's events.

    Keyed by model as well as day so a fact can still say which model the money went to, the
    same shape Claude Code produces, rather than collapsing a day into one opaque number.
    """
    totals: Final[dict[tuple[str, datetime, str | None], tuple[Decimal, int, int]]] = {}  # mutable-ok: a rollup
    for event in events:
        person = event.get("userEmail")
        day = _day_of(event.get("timestamp"))
        cents = decimal_or_none(event.get("chargedCents"))
        if not isinstance(person, str) or not person or day is None or cents is None or cents < 0:
            continue
        model = event.get("model") if isinstance(event.get("model"), str) else None
        key = (person, day, model)
        running = totals.get(key, (Decimal(0), 0, 0))
        totals[key] = (
            running[0] + cents,
            running[1] + _tokens_of(event, "inputTokens"),
            running[2] + _tokens_of(event, "outputTokens"),
        )

    return tuple(
        ToolUsageFact(
            tool="cursor",
            person=person,
            day=day,
            cost=cents / CENTS_PER_UNIT,
            currency="USD",
            basis="new_money",
            model=model,
            input_tokens=inputs or None,
            output_tokens=outputs or None,
        )
        for (person, day, model), (cents, inputs, outputs) in totals.items()
    )


class CursorConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: the proxy's httpx wrapper is untyped
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._http_client_factory = http_client_factory
        self._events_url = f"{base_url.rstrip('/')}{USAGE_EVENTS_PATH}"

    @property
    def tool(self) -> ToolName:
        return "cursor"

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
        events: Final[list[Mapping[str, object]]] = []  # mutable-ok: accumulated across windows and pages

        for window_start, window_end in _windows(since, until):
            for page in range(1, MAX_PAGES_PER_WINDOW + 1):
                body: Final = {  # mutable-ok: httpx serialises this with json.dumps, which has no mappingproxy encoder
                    "startDate": _epoch_millis(window_start),
                    "endDate": _epoch_millis(window_end),
                    "page": page,
                    "pageSize": MAX_EVENTS_PER_PAGE,
                }
                # Basic auth with the key as the username and no password, which is Cursor's
                # documented scheme and unlike every other connector here.
                response = await client.post(self._events_url, json=body, auth=(api_key, ""))
                status: Final = getattr(response, "status_code", 0)
                if status == 429:
                    return ToolFetchFailed(reason="cursor rate limited this key", retryable=True)
                if status in (401, 403):
                    return ToolFetchFailed(reason=f"cursor refused credential {credential_name}", retryable=False)
                if status != 200:
                    return ToolFetchFailed(reason=f"cursor returned {status}", retryable=True)

                payload = decoded_object(response.text)
                if payload is None:
                    return ToolFetchFailed(reason="cursor returned a body that is not an object", retryable=True)

                batch = payload.get("usageEvents")
                if isinstance(batch, Sequence) and not isinstance(batch, (str, bytes)):
                    events.extend(entry for entry in batch if isinstance(entry, Mapping))

                pagination = payload.get("pagination")
                has_next = pagination.get("hasNextPage") if isinstance(pagination, Mapping) else None
                if has_next is not True:
                    break

        return ToolFetched(facts=_rolled_up(events), watermark=until)
