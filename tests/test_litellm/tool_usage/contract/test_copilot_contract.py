"""Does our Copilot connector speak the API GitHub documents?

The request contract and the seat fields below come from GitHub's REST reference for Copilot
user management, `GET /orgs/{org}/copilot/billing/seats`:
https://docs.github.com/en/rest/copilot/copilot-user-management

GitHub publishes who holds a licence and never what it costs, so this connector returns seat
holders rather than money. Everything it does report is per organisation, which is why a
credential without one is refused rather than guessed at.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

import pytest

from tests.test_litellm.provider_billing.contract.conftest import Reply, Vendor

AS_OF: Final = datetime(2026, 9, 29, tzinfo=timezone.utc)
CREDENTIAL: Final = {"api_key": "ghp_not_a_real_token", "organization": "acme-eng"}


def _seat(login: str = "octocat", last_activity: str | None = "2026-09-28T09:00:00Z") -> dict[str, object]:
    return {
        "assignee": {"login": login, "id": 1, "type": "User"},
        "created_at": "2026-01-15T10:30:00Z",
        "updated_at": "2026-09-28T09:00:00Z",
        "last_activity_at": last_activity,
        "last_activity_editor": "vscode/1.90.0",
        "plan_type": "business",
        "pending_cancellation_date": None,
    }


def _page(*seats: dict[str, object], total: int | None = None) -> dict[str, object]:
    return {"total_seats": total if total is not None else len(seats), "seats": list(seats)}


async def _fetch(vendor: Vendor, *, values: dict[str, str] | None = None):
    from token_iq.connectors.tools.copilot import CopilotConnector

    return await CopilotConnector(
        http_client_factory=vendor.client_factory(), base_url="https://api.github.test"
    ).fetch_seats(
        as_of=AS_OF,
        credential_name="acme-copilot",
        credential_values=CREDENTIAL if values is None else values,
    )


@pytest.mark.asyncio
async def test_it_asks_for_the_path_and_method_github_documents(vendor):
    stand_in: Final = vendor(Reply(json=_page(_seat())))

    await _fetch(stand_in)

    assert stand_in.last.method == "GET"
    assert stand_in.last.path == "/orgs/acme-eng/copilot/billing/seats"


@pytest.mark.asyncio
async def test_it_sends_the_headers_github_requires(vendor):
    """GitHub needs the accept header and the API version alongside the token. Omitting the
    version leaves the response shape at the mercy of whatever GitHub defaults to next."""
    stand_in: Final = vendor(Reply(json=_page(_seat())))

    await _fetch(stand_in)

    assert stand_in.last.headers["authorization"] == "Bearer ghp_not_a_real_token"
    assert stand_in.last.headers["accept"] == "application/vnd.github+json"
    assert stand_in.last.headers["x-github-api-version"]


@pytest.mark.asyncio
async def test_it_stays_inside_the_page_size_github_allows(vendor):
    stand_in: Final = vendor(Reply(json=_page(_seat())))

    await _fetch(stand_in)

    assert 1 <= int(stand_in.last.params["per_page"]) <= 100


@pytest.mark.asyncio
async def test_it_reports_who_holds_a_licence_and_on_what_plan(vendor):
    from token_iq.types.tool_usage import ToolSeatsFetched

    stand_in: Final = vendor(Reply(json=_page(_seat("octocat"), _seat("hubot"))))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolSeatsFetched)
    assert {holder.person for holder in result.holders} == {"octocat", "hubot"}
    assert {holder.plan for holder in result.holders} == {"business"}


@pytest.mark.asyncio
async def test_it_reports_no_cost_at_all_because_github_publishes_none(vendor):
    """The price of a Copilot seat lives on the customer's contract. A figure invented here
    would put a number on a screen that nobody agreed to, so the type cannot carry one."""
    from token_iq.types.tool_usage import ToolSeatsFetched

    stand_in: Final = vendor(Reply(json=_page(_seat())))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolSeatsFetched)
    assert not hasattr(result.holders[0], "cost")
    assert not hasattr(result.holders[0], "amount")


@pytest.mark.asyncio
async def test_a_seat_with_no_recorded_activity_is_still_a_seat(vendor):
    """`last_activity_at` is null unless that person turned on telemetry in their IDE, so an
    empty value is not evidence the licence is unused. Dropping the row, or treating it as
    reclaimable, would recommend taking a licence from someone who uses it daily."""
    from token_iq.types.tool_usage import ToolSeatsFetched

    stand_in: Final = vendor(Reply(json=_page(_seat(last_activity=None))))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolSeatsFetched)
    assert len(result.holders) == 1
    assert result.holders[0].last_active_at is None


@pytest.mark.asyncio
async def test_it_keeps_when_a_seat_was_assigned_and_last_used(vendor):
    from token_iq.types.tool_usage import ToolSeatsFetched

    stand_in: Final = vendor(Reply(json=_page(_seat())))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolSeatsFetched)
    assert result.holders[0].assigned_at == datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
    assert result.holders[0].last_active_at == datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_it_pages_until_a_short_page_arrives(vendor):
    from token_iq.types.tool_usage import ToolSeatsFetched

    full: Final = _page(*[_seat(f"dev{index}") for index in range(100)])
    stand_in: Final = vendor(Reply(json=full), Reply(json=_page(_seat("last-one"))))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolSeatsFetched)
    assert len(stand_in.requests) == 2
    assert stand_in.requests[1].params["page"] == "2"
    assert len(result.holders) == 101


@pytest.mark.asyncio
async def test_a_credential_with_no_organisation_is_refused_rather_than_guessed(vendor):
    """Copilot seats are per organisation. Guessing one would read someone else's licences,
    or more likely just fail in a way nobody can act on."""
    from token_iq.types.tool_usage import ToolNotConfigured

    stand_in: Final = vendor(Reply(json=_page(_seat())))

    result: Final = await _fetch(stand_in, values={"api_key": "ghp_not_a_real_token"})

    assert isinstance(result, ToolNotConfigured)
    assert "organization" in result.reason
    assert stand_in.requests == []


@pytest.mark.asyncio
async def test_an_organisation_github_cannot_see_says_so_and_is_not_retried(vendor):
    from token_iq.types.tool_usage import ToolFetchFailed

    stand_in: Final = vendor(Reply(json={"message": "Not Found"}, status=404))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetchFailed)
    assert result.retryable is False
    assert "acme-eng" in result.reason


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (403, False), (429, True), (500, True), (503, True)],
)
@pytest.mark.asyncio
async def test_it_turns_an_error_into_a_reason_rather_than_raising(vendor, status: int, retryable: bool):
    from token_iq.types.tool_usage import ToolFetchFailed

    stand_in: Final = vendor(Reply(json={"message": "nope"}, status=status))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, ToolFetchFailed)
    assert result.retryable is retryable
    assert result.reason


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_a_failure_not_a_crash(vendor):
    from token_iq.types.tool_usage import ToolFetchFailed

    stand_in: Final = vendor(Reply(text="<html>unicorn</html>"))

    assert isinstance(await _fetch(stand_in), ToolFetchFailed)
