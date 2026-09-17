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
async def test_summary_sql_casts_the_summed_cost_to_text():
    """asyncpg decodes a bare SUM(::numeric) as a Python float, which has already lost the
    exact digits billed_cost exists to preserve. Casting the sum to text is what keeps the
    value exact from the database to _decimal."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=[])

    await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=7)

    sql, *_ = client.db.query_raw.await_args.args
    assert "sum(f.billed_cost::numeric)::text" in sql.lower()


@pytest.mark.asyncio
async def test_a_string_cost_from_the_driver_becomes_an_exact_decimal():
    """A value routed through float first would already be damaged by the time it reaches
    here: Decimal(str(0.00780515)) matches, but Decimal(str(some_float)) for a value with
    more digits would not. Feeding the exact digits as a string is the only way this
    matters."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(
        return_value=[
            {
                "model": "gpt-4o",
                "credential_name": "prod",
                "evidence": "reconciled",
                "billed_cost": "0.00780515",
                "facts": 1,
            }
        ]
    )

    rows = await ProviderUsageFactRepository(client).summary_rows(provider="openai", days=7)

    assert rows[0].billed_cost == Decimal("0.00780515")


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
async def test_a_row_with_an_unrecognised_evidence_level_is_dropped():
    """evidence tells a reader which figures the provider asserted and which we derived.
    A value outside the known levels must not reach the Summary screen labeled as if it
    were one of them."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(
        return_value=[
            {
                "model": "gpt-4o",
                "credential_name": "prod",
                "evidence": "guessed",
                "billed_cost": Decimal("12.5"),
                "facts": 3,
            }
        ]
    )

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


@pytest.mark.asyncio
async def test_token_totals_survive_the_driver_decoding_bigint_sums_as_float():
    """prisma-client-py decodes SUM(bigint) as a Python float, not an int, the same class
    of type-changing decode that made billed_cost cross as a float before it was cast to
    text. A totals field that only accepts a strict int silently reports zero tokens next
    to real spend, which reads as a confident false statement rather than a missing one."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = MagicMock()
    client.db.query_raw = AsyncMock(
        return_value=[{"input": 3372.0, "output": 20.0, "cached_input": 5.0, "cache_write": 2.0}]
    )

    totals = await ProviderUsageFactRepository(client).token_totals(provider="openai", days=30)

    assert (totals.input_tokens, totals.output_tokens) == (3372, 20)
    assert (totals.cached_input_tokens, totals.cache_write_tokens) == (5, 2)


@pytest.mark.asyncio
async def test_recent_facts_are_bounded_ordered_newest_first_in_the_database():
    """Rendered on every page of the Raw Data view against a table that grows on every
    tick. An unbounded or Python-sorted read would eventually take the database down.

    The order carries fact_key as well as bucket_start: a live check against real data
    found 47 openrouter facts sharing one bucket_start (one connector run stamps every
    fact it writes with the same watermark), and ordering on bucket_start alone gives no
    guarantee about which of those rows a page boundary lands on, which is exactly what
    the fact_key tiebreaker in the cursor below depends on to stay correct."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(return_value=[])
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    await ProviderUsageFactRepository(client).recent_facts(provider="openai", limit=50, before=None)

    call = table.find_many.await_args.kwargs
    assert call["where"] == {"provider": "openai"}
    assert call["order"] == ({"bucket_start": "desc"}, {"fact_key": "desc"})
    assert call["take"] == 50


@pytest.mark.asyncio
async def test_paging_asks_only_for_rows_older_than_the_cursor():
    """Offset paging re-reads everything before the page. This table is append-heavy, so a
    keyset cursor is the difference between a fast page ten and a slow one.

    Without a fact_key half, the cursor can only filter on bucket_start, which is the
    best-effort fallback for a caller that has nothing else; the composite cursor below is
    what a full page from this repository actually hands back."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(return_value=[])
    client = MagicMock()
    client.db.litellm_providerusagefact = table
    cursor = datetime(2026, 9, 15, tzinfo=timezone.utc)

    await ProviderUsageFactRepository(client).recent_facts(provider="openai", limit=10, before=cursor)

    assert table.find_many.await_args.kwargs["where"] == {
        "provider": "openai",
        "bucket_start": {"lt": cursor},
    }


@pytest.mark.asyncio
async def test_the_fact_key_tiebreaker_keeps_rows_tied_on_bucket_start_reachable():
    """A page boundary that lands inside a group of facts sharing one bucket_start must
    defer the whole group rather than lose whichever of them did not fit the page. Filtering
    on bucket_start alone at that boundary would exclude every tied row forever, including
    ones a previous page never returned; the fact_key half makes the exclusion exact instead
    of blanket."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(return_value=[])
    client = MagicMock()
    client.db.litellm_providerusagefact = table
    cursor = datetime(2026, 9, 15, tzinfo=timezone.utc)

    await ProviderUsageFactRepository(client).recent_facts(
        provider="openai", limit=10, before=cursor, before_fact_key="openai:acct:2026-09-15:gpt-4o"
    )

    assert table.find_many.await_args.kwargs["where"] == {
        "provider": "openai",
        "OR": (
            {"bucket_start": {"lt": cursor}},
            {"bucket_start": cursor, "fact_key": {"lt": "openai:acct:2026-09-15:gpt-4o"}},
        ),
    }


def _fact_row(**overrides: object) -> MagicMock:
    fields: dict[str, object] = {
        "fact_key": "openrouter:gen-1",
        "provider": "openrouter",
        "credential_name": "acme-openrouter",
        "grain": "request",
        "bucket_start": datetime(2026, 9, 15, tzinfo=timezone.utc),
        "evidence": "reconciled",
        "billed_cost": "0.0000025",
        "billing_currency": "USD",
        "provider_request_id": "gen-1",
        "provider_api_key_id": None,
        "model": "gpt-4o",
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_input_tokens": 5,
        "cache_write_tokens": 2,
        "raw": {"id": "gen-1", "total_cost": 0.0000025},
        "fetched_at": datetime(2026, 9, 15, 1, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return MagicMock(**fields)


@pytest.mark.asyncio
async def test_recent_facts_carry_the_raw_payload_and_exact_cost_unchanged():
    """Raw Data exists to show exactly what the provider sent. A read path that reshapes or
    rounds `raw` or `billed_cost` defeats the entire reason this column was stored."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(return_value=[_fact_row()])
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    page = await ProviderUsageFactRepository(client).recent_facts(provider="openrouter", limit=50, before=None)

    assert len(page.facts) == 1
    assert dict(page.facts[0].raw) == {"id": "gen-1", "total_cost": 0.0000025}
    assert page.facts[0].billed_cost == Decimal("0.0000025")
    assert isinstance(page.facts[0].billed_cost, Decimal)


@pytest.mark.asyncio
async def test_recent_facts_drops_a_row_it_cannot_read_rather_than_fabricating_it():
    """A fabricated row on the Raw Data screen is worse than a missing one: the whole point
    of that screen is to show exactly what the provider said, nothing invented."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(
        return_value=[_fact_row(), _fact_row(fact_key="openrouter:gen-2", evidence="guessed")]
    )
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    page = await ProviderUsageFactRepository(client).recent_facts(provider="openrouter", limit=50, before=None)

    assert [fact.fact_key for fact in page.facts] == ["openrouter:gen-1"]


@pytest.mark.asyncio
async def test_a_full_database_page_stays_full_even_when_one_row_is_dropped():
    """The database can return exactly `limit` rows while one of them fails
    `_fact_or_none`. Deciding "full page" from how many facts survived, rather than from how
    many rows the database actually returned, is exactly the silent-truncation bug this
    cursor exists to rule out, one layer above the bucket_start tie that caused it the first
    time: a customer would stop paging early and believe they had seen everything, while
    rows sit unreachable behind a cursor that was never set."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(
        return_value=[_fact_row(), _fact_row(fact_key="openrouter:gen-2", evidence="guessed")]
    )
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    page = await ProviderUsageFactRepository(client).recent_facts(provider="openrouter", limit=2, before=None)

    assert len(page.facts) == 1
    assert page.next_cursor is not None


@pytest.mark.asyncio
async def test_next_cursor_is_none_when_the_database_page_is_short():
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    table = MagicMock()
    table.find_many = AsyncMock(return_value=[_fact_row()])
    client = MagicMock()
    client.db.litellm_providerusagefact = table

    page = await ProviderUsageFactRepository(client).recent_facts(provider="openrouter", limit=50, before=None)

    assert page.next_cursor is None
