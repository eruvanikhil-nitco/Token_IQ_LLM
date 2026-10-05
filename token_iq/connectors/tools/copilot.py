"""Who holds a GitHub Copilot licence.

Copilot is the one tool here that publishes no cost at all. GitHub says who has a seat, when
it was assigned and when they were last active, but the price sits on the customer's contract,
so this connector reports holders and an admin sets the price once.

That is why it returns seat holders rather than usage facts. A connector that cannot report
money must not be able to satisfy a protocol whose return type is money.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Final

from litellm.types.proxy.tool_usage import (
    SeatHolder,
    ToolFetchFailed,
    ToolName,
    ToolNotConfigured,
    ToolSeatResult,
    ToolSeatsFetched,
)
from token_iq.connectors.billing.cloud_rows import decoded_object

DEFAULT_BASE_URL: Final = "https://api.github.com"

SEATS_PATH_TEMPLATE: Final = "/orgs/{org}/copilot/billing/seats"

GITHUB_API_VERSION: Final = "2026-03-10"

MAX_SEATS_PER_PAGE: Final = 100
"""The maximum `per_page` the reference allows."""

MAX_PAGES_PER_RUN: Final = 50


def _moment_or_none(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed: Final = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _holder_from(seat: Mapping[str, object]) -> SeatHolder | None:
    assignee: Final = seat.get("assignee")
    login: Final = assignee.get("login") if isinstance(assignee, Mapping) else None
    if not isinstance(login, str) or not login:
        return None

    return SeatHolder(
        tool="copilot",
        person=login,
        plan=plan if isinstance(plan := seat.get("plan_type"), str) else None,
        assigned_at=_moment_or_none(seat.get("created_at")),
        last_active_at=_moment_or_none(seat.get("last_activity_at")),
    )


class CopilotConnector:
    def __init__(
        self,
        http_client_factory: Callable[[], Any],  # any-ok: the proxy's httpx wrapper is untyped
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._http_client_factory = http_client_factory
        self._base_url = base_url.rstrip("/")

    @property
    def tool(self) -> ToolName:
        return "copilot"

    async def fetch_seats(
        self,
        *,
        as_of: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> ToolSeatResult:
        token: Final = credential_values.get("api_key")
        org: Final = credential_values.get("organization")
        if not token:
            return ToolNotConfigured(reason=f"credential {credential_name} carries no api_key")
        if not org:
            return ToolNotConfigured(
                reason=f"credential {credential_name} carries no organization, and Copilot seats are per organisation"
            )

        client: Final = self._http_client_factory()
        url: Final = self._base_url + SEATS_PATH_TEMPLATE.format(org=org)
        headers: Final = MappingProxyType(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            }
        )

        holders: Final[list[SeatHolder]] = []  # mutable-ok: accumulated across pages
        for page in range(1, MAX_PAGES_PER_RUN + 1):
            params: Final = MappingProxyType({"page": page, "per_page": MAX_SEATS_PER_PAGE})
            response = await client.get(url, params=params, headers=headers)
            status: Final = getattr(response, "status_code", 0)
            if status == 429:
                return ToolFetchFailed(reason="github rate limited this token", retryable=True)
            if status in (401, 403):
                return ToolFetchFailed(reason=f"github refused credential {credential_name}", retryable=False)
            if status == 404:
                return ToolFetchFailed(
                    reason=f"github has no copilot seats for organisation {org}, or the token cannot see them",
                    retryable=False,
                )
            if status != 200:
                return ToolFetchFailed(reason=f"github returned {status}", retryable=True)

            payload = decoded_object(response.text)
            if payload is None:
                return ToolFetchFailed(reason="github returned a body that is not an object", retryable=True)

            seats = payload.get("seats")
            if not isinstance(seats, Sequence) or isinstance(seats, (str, bytes)):
                break

            holders.extend(
                holder for seat in seats if isinstance(seat, Mapping) and (holder := _holder_from(seat)) is not None
            )
            if len(seats) < MAX_SEATS_PER_PAGE:
                break

        return ToolSeatsFetched(holders=tuple(holders), watermark=as_of)
