from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from token_iq.connectors.billing.fetch_profile import FETCH_PROFILES
from token_iq.gateway.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from token_iq.types.provider_billing import ProviderUsageFact, RecentFactsPage, SummaryRow, TokenTotals

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")
NON_ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")

TOKENS = TokenTotals(input_tokens=100, output_tokens=20, cached_input_tokens=5, cache_write_tokens=2)


class _FakeRepository:
    def __init__(self, rows: tuple[SummaryRow, ...], tokens: TokenTotals) -> None:
        self._rows = rows
        self._tokens = tokens

    def __call__(self, _prisma_client: object) -> _FakeRepository:
        return self

    async def summary_rows(self, *, provider: str, days: int) -> tuple[SummaryRow, ...]:
        return self._rows

    async def token_totals(self, *, provider: str, days: int) -> TokenTotals:
        return self._tokens


@pytest.mark.asyncio
async def test_only_an_admin_may_read_provider_usage():
    """This exposes what every account in the deployment spent. A non-admin reaching it
    leaks financial data across teams."""
    from fastapi import HTTPException

    from token_iq.api.provider_usage import provider_usage_summary

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_summary(provider="openrouter", days=30, user_api_key_dict=NON_ADMIN)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_usage_without_a_database_answers_500_not_a_crash():
    from fastapi import HTTPException

    from token_iq.api.provider_usage import provider_usage_summary

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", None):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_summary(provider="openrouter", days=30, user_api_key_dict=ADMIN)

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_rather_than_answering_an_empty_summary():
    """An empty summary for a typo'd provider reads as 'you spent nothing', which is a
    different and much worse message than 'no such provider'."""
    from fastapi import HTTPException

    from token_iq.api.provider_usage import provider_usage_summary

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_summary(provider="notreal", days=30, user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404
    assert "notreal" in exc.value.detail["error"]
    assert "openrouter" in exc.value.detail["error"]


@pytest.mark.asyncio
async def test_the_response_carries_the_settling_note_so_recent_figures_are_not_read_as_final():
    from token_iq.api.provider_usage import provider_usage_summary

    rows = (
        SummaryRow(model="claude-3-5", credential_name="prod", evidence="reconciled", billed_cost=Decimal("1.50"),
                   facts=3),
    )
    fake_repository = _FakeRepository(rows, TOKENS)

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with patch("token_iq.api.provider_usage.ProviderUsageFactRepository", fake_repository):
            result = await provider_usage_summary(provider="bedrock", days=30, user_api_key_dict=ADMIN)

    assert result.total_cost == "1.50"
    assert isinstance(result.total_cost, str)
    assert result.delay_note == FETCH_PROFILES["bedrock"].delay_note
    assert result.settling_note == FETCH_PROFILES["bedrock"].settling_note
    assert result.grain == "day"


def _raw_fact(key: str, bucket_start: datetime) -> ProviderUsageFact:
    return ProviderUsageFact(
        fact_key=key,
        provider="openrouter",
        credential_name="acme-openrouter",
        grain="request",
        bucket_start=bucket_start,
        evidence="reconciled",
        billed_cost=Decimal("0.0000025"),
        provider_request_id=key,
        model="gpt-4o",
        input_tokens=100,
        output_tokens=20,
        cached_input_tokens=5,
        cache_write_tokens=2,
        raw={"id": key, "total_cost": 0.0000025},
        fetched_at=datetime(2026, 9, 15, 1, tzinfo=timezone.utc),
    )


class _FakeRawRepository:
    """Mirrors the real repository's keyset semantics: newest first, tie-broken by
    fact_key, excluding exactly what a composite cursor says was already served.

    A naive fake that just slices a list by `limit` would pass every route test while
    hiding the tie-boundary bug a live check against real data actually found, so this
    fake applies the same `(bucket_start, fact_key)` comparison the repository's `OR`
    where-clause does."""

    def __init__(self, facts: tuple[ProviderUsageFact, ...]) -> None:
        self._facts = tuple(sorted(facts, key=lambda fact: (fact.bucket_start, fact.fact_key), reverse=True))

    def __call__(self, _prisma_client: object) -> _FakeRawRepository:
        return self

    async def recent_facts(
        self, *, provider: str, limit: int, before: datetime | None, before_fact_key: str | None = None
    ) -> RecentFactsPage:
        def _after_cursor(fact: ProviderUsageFact) -> bool:
            if before is None:
                return True
            if before_fact_key is None:
                return fact.bucket_start < before
            return (fact.bucket_start, fact.fact_key) < (before, before_fact_key)

        page_facts: Final = tuple(fact for fact in self._facts if _after_cursor(fact))[:limit]
        next_cursor: Final = (
            (page_facts[-1].bucket_start, page_facts[-1].fact_key) if len(page_facts) == limit else None
        )
        return RecentFactsPage(facts=page_facts, next_cursor=next_cursor)


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_on_the_raw_route_too():
    """The summary route already refuses a typo'd provider instead of answering an empty
    result; the raw route must agree, or the same mistake means two different things
    depending on which screen the customer happens to be looking at."""
    from fastapi import HTTPException

    from token_iq.api.provider_usage import provider_usage_raw

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_raw(provider="notreal", limit=50, before=None, user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404
    assert "notreal" in exc.value.detail["error"]
    assert "openrouter" in exc.value.detail["error"]


@pytest.mark.asyncio
async def test_only_an_admin_may_read_provider_raw_usage():
    """This is the provider's own billing payload for every account. A non-admin reaching
    it leaks financial detail across teams."""
    from fastapi import HTTPException

    from token_iq.api.provider_usage import provider_usage_raw

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_raw(provider="openrouter", limit=50, before=None, user_api_key_dict=NON_ADMIN)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_raw_usage_without_a_database_answers_500_not_a_crash():
    from fastapi import HTTPException

    from token_iq.api.provider_usage import provider_usage_raw

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", None):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_raw(provider="openrouter", limit=50, before=None, user_api_key_dict=ADMIN)

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_raw_rows_carry_the_providers_own_payload_and_exact_cost_as_a_string():
    """Raw Data exists to show the provider's fields verbatim. A response that reshapes,
    prunes or rounds `raw`, or that lets the cost cross as a JSON number, defeats the whole
    point of storing it."""
    from token_iq.api.provider_usage import provider_usage_raw

    fact = _raw_fact("gen-1", datetime(2026, 9, 15, tzinfo=timezone.utc))
    fake_repository = _FakeRawRepository((fact,))

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with patch("token_iq.api.provider_usage.ProviderUsageFactRepository", fake_repository):
            result = await provider_usage_raw(provider="openrouter", limit=50, before=None, user_api_key_dict=ADMIN)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.raw == {"id": "gen-1", "total_cost": 0.0000025}
    assert isinstance(row.billed_cost, str)
    assert row.billed_cost == "0.0000025"
    assert row.provider_request_id == "gen-1"
    assert row.fetched_at == "2026-09-15T01:00:00+00:00"


@pytest.mark.asyncio
async def test_next_before_is_set_when_the_page_is_full():
    """A full page means there may be more rows behind it. Omitting the cursor here would
    silently truncate a customer's history at whatever the page size happened to be."""
    from token_iq.api.provider_usage import provider_usage_raw

    facts = tuple(
        _raw_fact(f"gen-{i}", datetime(2026, 9, 15 - i, tzinfo=timezone.utc)) for i in range(5)
    )
    fake_repository = _FakeRawRepository(facts)

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with patch("token_iq.api.provider_usage.ProviderUsageFactRepository", fake_repository):
            result = await provider_usage_raw(provider="openrouter", limit=5, before=None, user_api_key_dict=ADMIN)

    assert len(result.rows) == 5
    assert result.next_before == f"{facts[-1].bucket_start.isoformat()}|{facts[-1].fact_key}"


@pytest.mark.asyncio
async def test_next_before_is_none_when_the_page_is_short():
    """A short page is the only reliable signal that the scan reached the end. Reporting a
    cursor anyway would make the client ask for a page that will always come back empty."""
    from token_iq.api.provider_usage import provider_usage_raw

    facts = tuple(
        _raw_fact(f"gen-{i}", datetime(2026, 9, 15 - i, tzinfo=timezone.utc)) for i in range(3)
    )
    fake_repository = _FakeRawRepository(facts)

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with patch("token_iq.api.provider_usage.ProviderUsageFactRepository", fake_repository):
            result = await provider_usage_raw(provider="openrouter", limit=50, before=None, user_api_key_dict=ADMIN)

    assert len(result.rows) == 3
    assert result.next_before is None


@pytest.mark.asyncio
async def test_the_composite_cursor_resumes_across_a_tie_on_bucket_start_without_loss():
    """A live check against real data found dozens of openrouter facts sharing one
    bucket_start, because one connector run stamps every fact it fetches with that run's
    watermark. A page boundary that lands inside that group must defer the whole remainder
    to the next page; filtering the next page on bucket_start alone would have dropped it
    for good, which is exactly the bug this cursor exists to rule out."""
    from token_iq.api.provider_usage import provider_usage_raw

    tied_bucket = datetime(2026, 9, 15, 11, 7, 58, tzinfo=timezone.utc)
    tied_facts = tuple(_raw_fact(f"gen-tied-{i}", tied_bucket) for i in range(6))
    newer_fact = _raw_fact("gen-newest", datetime(2026, 9, 16, tzinfo=timezone.utc))
    fake_repository = _FakeRawRepository((newer_fact, *tied_facts))

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with patch("token_iq.api.provider_usage.ProviderUsageFactRepository", fake_repository):
            page1 = await provider_usage_raw(provider="openrouter", limit=4, before=None, user_api_key_dict=ADMIN)
            assert page1.next_before is not None
            page2 = await provider_usage_raw(
                provider="openrouter", limit=4, before=page1.next_before, user_api_key_dict=ADMIN
            )

    seen = [row.provider_request_id for row in (*page1.rows, *page2.rows)]
    assert len(seen) == len(set(seen))
    assert set(seen) == {newer_fact.provider_request_id, *(fact.provider_request_id for fact in tied_facts)}


def _raw_prisma_row(*, fact_key: str, bucket_start: datetime, evidence: str, fetched_at: datetime) -> MagicMock:
    return MagicMock(
        fact_key=fact_key,
        provider="openrouter",
        credential_name="acme-openrouter",
        grain="request",
        bucket_start=bucket_start,
        evidence=evidence,
        billed_cost="0.01",
        billing_currency="USD",
        provider_request_id=fact_key,
        provider_api_key_id=None,
        model="gpt-4o",
        input_tokens=1,
        output_tokens=1,
        cached_input_tokens=None,
        cache_write_tokens=None,
        raw=None,
        fetched_at=fetched_at,
    )


@pytest.mark.asyncio
async def test_next_before_is_set_even_when_one_row_in_a_full_page_is_dropped():
    """The database can return exactly `limit` rows and still have one of them fail
    `_fact_or_none` (a bad evidence value here, but the same applies to any unreadable
    field). Whether a row survives parsing has nothing to do with whether the database had
    more rows behind the cursor, so "was the page full" must come from what the database
    returned, not from how many facts survived. Deciding it from the survivor count is
    exactly the silent-truncation bug the composite cursor was built to rule out, one layer
    further up: a customer would stop paging early and believe they had seen everything,
    while rows sit unreachable behind a cursor that was never set.

    This test drives the real repository through the real route, with a mocked prisma table,
    rather than the `_FakeRawRepository` used elsewhere: a fake that only ever returns
    already-filtered facts cannot represent "the database returned more rows than survived",
    which is the entire bug.
    """
    from token_iq.api.provider_usage import provider_usage_raw

    good_row = _raw_prisma_row(
        fact_key="openrouter:gen-1",
        bucket_start=datetime(2026, 9, 15, tzinfo=timezone.utc),
        evidence="reconciled",
        fetched_at=datetime(2026, 9, 15, 1, tzinfo=timezone.utc),
    )
    bad_row = _raw_prisma_row(
        fact_key="openrouter:gen-2",
        bucket_start=datetime(2026, 9, 14, tzinfo=timezone.utc),
        evidence="not-a-real-evidence-level",
        fetched_at=datetime(2026, 9, 14, 1, tzinfo=timezone.utc),
    )
    table = MagicMock()
    table.find_many = AsyncMock(return_value=[good_row, bad_row])
    prisma_client = MagicMock()
    prisma_client.db.litellm_providerusagefact = table

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", prisma_client):
        result = await provider_usage_raw(provider="openrouter", limit=2, before=None, user_api_key_dict=ADMIN)

    assert len(result.rows) == 1
    assert result.next_before is not None


@pytest.mark.asyncio
async def test_a_malformed_cursor_is_refused_rather_than_crashing():
    from fastapi import HTTPException

    from token_iq.api.provider_usage import provider_usage_raw

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", MagicMock()):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_raw(
                provider="openrouter", limit=50, before="not-a-timestamp", user_api_key_dict=ADMIN
            )

    assert exc.value.status_code == 400
