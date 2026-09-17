from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.types.proxy.provider_billing import ProviderUsageFact


def _fact(key: str = "openrouter:gen-1") -> ProviderUsageFact:
    return ProviderUsageFact(
        fact_key=key,
        provider="openrouter",
        credential_name="acme-openrouter",
        grain="request",
        bucket_start=datetime.now(timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("0.0000025"),
        provider_request_id=key.split(":", 1)[1],
    )


def _client() -> MagicMock:
    client = MagicMock()
    client.db.litellm_providerusagefact.upsert = AsyncMock(return_value=MagicMock())
    client.db.litellm_providerusagefact.find_many = AsyncMock(return_value=[])
    return client


@pytest.mark.asyncio
async def test_refetching_the_same_fact_updates_rather_than_duplicates():
    """Every connector re-reads overlapping windows, because a watermark that never
    overlaps loses anything that landed late. Without an upsert on fact_key that would
    double-count a customer's spend on every tick."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    written = await ProviderUsageFactRepository(client).upsert_many([_fact(), _fact()])

    assert written == 2
    assert client.db.litellm_providerusagefact.upsert.await_count == 2
    for call in client.db.litellm_providerusagefact.upsert.await_args_list:
        assert call.kwargs["where"] == {"fact_key": "openrouter:gen-1"}


@pytest.mark.asyncio
async def test_the_cost_reaches_the_database_as_a_string_not_a_float():
    """The column is text precisely so the provider's digits survive. Handing Prisma a
    float here would round them away at the last possible moment."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    await ProviderUsageFactRepository(client).upsert_many([_fact()])

    created = client.db.litellm_providerusagefact.upsert.await_args_list[0].kwargs["data"]["create"]
    assert isinstance(created["billed_cost"], str)
    assert created["billed_cost"] == "0.0000025"


@pytest.mark.asyncio
async def test_writing_nothing_touches_the_database_not_at_all():
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()

    assert await ProviderUsageFactRepository(client).upsert_many([]) == 0
    client.db.litellm_providerusagefact.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_fetched_requests_are_reported_so_they_can_be_skipped():
    """OpenRouter prices one request per call and rate limits. Re-looking-up a request we
    already priced spends the budget we need for new ones."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    client.db.litellm_providerusagefact.find_many = AsyncMock(
        return_value=[MagicMock(provider_request_id="gen-1")]
    )

    seen = await ProviderUsageFactRepository(client).request_ids_already_fetched(
        provider="openrouter", request_ids=["gen-1", "gen-2"]
    )

    assert seen == frozenset({"gen-1"})


@pytest.mark.asyncio
async def test_asking_about_no_requests_does_not_query():
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()

    assert await ProviderUsageFactRepository(client).request_ids_already_fetched(
        provider="openrouter", request_ids=[]
    ) == frozenset()
    client.db.litellm_providerusagefact.find_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_providers_own_payload_is_written_to_the_raw_column():
    """Raw Data shows the provider's fields verbatim. A fact whose payload was dropped at
    parse time can never be shown, and the provider will not serve that day again."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.upsert = AsyncMock()
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    fact = ProviderUsageFact(
        fact_key="openai:acct:2026-09-15:gpt-4o",
        provider="openai",
        credential_name="acct",
        grain="day",
        bucket_start=datetime(2026, 9, 15, tzinfo=timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("1.25"),
        raw={"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}},
    )

    await ProviderUsageFactRepository(client).upsert_many([fact])

    written = table.upsert.await_args.kwargs["data"]["create"]
    assert written["raw"] == {"line_item": "gpt-4o", "amount": {"value": 1.25, "currency": "usd"}}


@pytest.mark.asyncio
async def test_counts_by_credential_reads_the_all_count_prisma_actually_returns():
    """prisma-client-py's group_by(count=True) nests the tally under _count._all, not under
    the grouped field name. Reading the wrong key would silently report every account as
    having zero facts, which is indistinguishable from a connection that has never worked."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    client.db.litellm_providerusagefact.group_by = AsyncMock(
        return_value=[
            {"credential_name": "prod", "_count": {"_all": 40}},
            {"credential_name": "staging", "_count": {"_all": 0}},
        ]
    )

    counts = await ProviderUsageFactRepository(client).counts_by_credential("openai")

    assert dict(counts) == {"prod": 40, "staging": 0}
    client.db.litellm_providerusagefact.group_by.assert_awaited_once_with(
        by=["credential_name"], where={"provider": "openai"}, count=True
    )


@pytest.mark.asyncio
async def test_counts_by_credential_drops_a_row_it_cannot_read():
    """A row missing the fields we depend on must not crash the connections screen or be
    guessed at as zero facts for some other account."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    client.db.litellm_providerusagefact.group_by = AsyncMock(
        return_value=[
            {"credential_name": "prod", "_count": {"_all": 5}},
            {"_count": {"_all": 3}},
        ]
    )

    counts = await ProviderUsageFactRepository(client).counts_by_credential("openai")

    assert dict(counts) == {"prod": 5}


@pytest.mark.asyncio
async def test_summary_rows_aggregate_in_sql_and_are_bounded_by_the_window():
    """This table grows on every scheduler tick. Summing in Python would mean reading the
    whole history to render one screen."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=[])

    await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=30)

    sql, *params = client.db.query_raw.await_args.args
    assert "group by" in sql.lower()
    assert "sum(" in sql.lower()
    assert params[0] == "openai"
    assert params[1] == "30"


@pytest.mark.asyncio
async def test_summary_rows_carry_model_account_cost_and_request_count():
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(
        return_value=[
            {
                "model": "gpt-4o",
                "credential_name": "prod",
                "evidence": "reconciled",
                "billed_cost": Decimal("12.5"),
                "facts": 3,
            }
        ]
    )

    rows = await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=7)

    assert rows[0].model == "gpt-4o"
    assert rows[0].credential_name == "prod"
    assert rows[0].evidence == "reconciled"
    assert rows[0].billed_cost == Decimal("12.5")
    assert rows[0].facts == 3


@pytest.mark.asyncio
async def test_a_row_we_cannot_read_is_dropped_rather_than_guessed():
    """A malformed aggregate row must not become a zero-cost line that silently understates
    the bill."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=[{"model": "gpt-4o", "billed_cost": "not-a-number"}])

    assert await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=7) == ()


@pytest.mark.asyncio
async def test_token_totals_sum_each_token_type_separately():
    """Input, output, cache read and cache write are priced differently. Collapsing them
    into one number hides the thing a reader is looking for."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(
        return_value=[{"input": 100, "output": 20, "cached_input": 5, "cache_write": 2}]
    )

    totals = await ProviderUsageFactRepository(client).token_totals(provider="openai", days=7)

    assert (totals.input_tokens, totals.output_tokens) == (100, 20)
    assert (totals.cached_input_tokens, totals.cache_write_tokens) == (5, 2)
