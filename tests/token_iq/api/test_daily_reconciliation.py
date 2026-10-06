from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from token_iq.gateway.proxy._types import LitellmUserRoles, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")


def _row(day: str, ours: str | None, theirs: str | None) -> dict:
    return {
        "day": day,
        "our_cost": None if ours is None else Decimal(ours),
        "their_cost": None if theirs is None else Decimal(theirs),
    }


async def _call(rows: list[dict], caller: UserAPIKeyAuth = ADMIN):
    from token_iq.api.provider_reconciliation import daily_reconciliation

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=rows)
    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", client):
        return await daily_reconciliation(provider="anthropic", days=7, user_api_key_dict=caller)


@pytest.mark.asyncio
async def test_a_day_the_provider_charged_more_is_flagged_as_escaped_spend():
    """The discovery no gateway can make on its own. If the provider billed more than we
    recorded, the difference is traffic that never came through us, and a customer who
    bought a gateway for control needs to know it is leaking."""
    result = await _call([_row("2026-09-12", "10.00", "14.00")])

    assert result.rows[0].escaped_spend is True
    assert result.rows[0].delta == "-4.00"
    assert result.days_provider_charged_more == 1


@pytest.mark.asyncio
async def test_a_day_we_recorded_more_is_not_escaped_spend():
    """Our estimate running high is a pricing problem, not a leak. Calling both the same
    thing would cry wolf on every stale price entry."""
    result = await _call([_row("2026-09-12", "14.00", "10.00")])

    assert result.rows[0].escaped_spend is False
    assert result.days_provider_charged_more == 0


@pytest.mark.asyncio
async def test_a_day_the_provider_has_not_reported_is_not_flagged():
    """Cloud bills land a day or two late. Flagging every recent day as a leak would make
    the signal useless."""
    result = await _call([_row("2026-09-13", "5.00", None)])

    assert result.rows[0].escaped_spend is False
    assert result.rows[0].their_cost is None
    assert result.rows[0].delta is None


@pytest.mark.asyncio
async def test_a_day_only_the_provider_reported_is_entirely_escaped_spend():
    """Nothing came through the gateway that day and the provider still charged. That is
    the strongest form of the signal, and it must not be dropped for having no gateway
    row to join against."""
    result = await _call([_row("2026-09-12", None, "9.00")])

    assert result.rows[0].escaped_spend is True
    assert result.rows[0].our_cost == "0"
    assert result.rows[0].their_cost == "9.00"


@pytest.mark.asyncio
async def test_totals_are_fixed_point_strings():
    result = await _call([_row("2026-09-12", "0.0000030", "0.0000025")])

    assert "E" not in result.delta
    assert isinstance(result.our_total, str)


@pytest.mark.asyncio
async def test_an_unreported_day_does_not_pollute_their_total():
    result = await _call([_row("2026-09-13", "5.00", None), _row("2026-09-12", "3.00", "3.00")])

    assert result.their_total == "3.00"
    assert result.our_total == "8.00"


def _driver_decoded(sql: str, marker: str, value: str) -> object:
    return value if marker in sql else float(value)


def _prisma_matching_driver(our_cost: str, their_cost: str) -> MagicMock:
    client = MagicMock()

    async def _query_raw(sql: str, *_args: object) -> list[dict[str, object]]:
        return [
            {
                "day": "2026-09-19",
                "our_cost": _driver_decoded(sql, "SUM(s.spend)::numeric::text", our_cost),
                "their_cost": _driver_decoded(sql, "SUM(f.billed_cost::numeric)::text", their_cost),
            }
        ]

    client.db.query_raw = AsyncMock(side_effect=_query_raw)
    return client


@pytest.mark.asyncio
async def test_daily_totals_keep_every_digit_the_provider_billed():
    from token_iq.api.provider_reconciliation import daily_reconciliation

    client = _prisma_matching_driver(our_cost="0.123456789012345678", their_cost="0.123456789012345678")
    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", client):
        result = await daily_reconciliation(provider="openai", days=7, user_api_key_dict=ADMIN)

    assert result.rows[0].our_cost == "0.123456789012345678"
    assert result.rows[0].their_cost == "0.123456789012345678"
    assert result.our_total == "0.123456789012345678"
    assert result.their_total == "0.123456789012345678"
    sql = client.db.query_raw.await_args.args[0]
    assert "SUM(s.spend)::numeric::text" in sql
    assert "SUM(f.billed_cost::numeric)::text" in sql


def _fact(day: str, grain: str, billed_cost: str) -> Mapping[str, str]:
    return {"day": day, "grain": grain, "billed_cost": billed_cost}


def _prisma_summing_facts(facts: Sequence[Mapping[str, str]], our_cost: str = "0") -> MagicMock:
    """Stands in for postgres summing `LiteLLM_ProviderUsageFact` rows into a day.

    Filters by `f.grain = 'day'` only when that clause is actually present in the SQL sent,
    the same way a real `WHERE` clause would. A day with no fact left after that filter still
    reports its `their_cost` as unknown rather than as zero, matching the real query's full
    outer join: the day exists because some request happened on it, the provider figure is
    simply missing.
    """
    client = MagicMock()

    async def _query_raw(sql: str, *_args: object) -> list[dict[str, object]]:
        day_grain_only: Final = "f.grain = 'day'" in sql
        selected: Final = tuple(fact for fact in facts if not day_grain_only or fact["grain"] == "day")
        all_days: Final = {fact["day"] for fact in facts}
        return [
            {
                "day": day,
                "our_cost": our_cost,
                "their_cost": (
                    str(sum((Decimal(fact["billed_cost"]) for fact in selected if fact["day"] == day), Decimal(0)))
                    if any(fact["day"] == day for fact in selected)
                    else None
                ),
            }
            for day in all_days
        ]

    client.db.query_raw = AsyncMock(side_effect=_query_raw)
    return client


@pytest.mark.asyncio
async def test_a_request_grain_fact_counts_toward_the_daily_provider_total():
    """Grain says how finely the provider answered, not what period the money belongs to.
    A request-grain fact still has a bucket_start and still belongs to a day, so filtering
    it out of the daily total told a customer their provider charged them nothing."""
    from token_iq.api.provider_reconciliation import daily_reconciliation

    client = _prisma_summing_facts([_fact("2026-09-19", "request", "5.00")])
    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", client):
        result = await daily_reconciliation(provider="openrouter", days=7, user_api_key_dict=ADMIN)

    assert result.rows[0].their_cost == "5.00"
    assert result.their_total == "5.00"


@pytest.mark.asyncio
async def test_mixed_grain_facts_for_the_same_day_are_summed_not_dropped():
    """No connector emits two grains for one period today, but nothing in the query says
    so. If one ever does, both amounts belong in the day's total, not just one of them."""
    from token_iq.api.provider_reconciliation import daily_reconciliation

    client = _prisma_summing_facts([_fact("2026-09-19", "request", "5.00"), _fact("2026-09-19", "day", "2.00")])
    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", client):
        result = await daily_reconciliation(provider="openrouter", days=7, user_api_key_dict=ADMIN)

    assert result.rows[0].their_cost == "7.00"


@pytest.mark.asyncio
async def test_only_an_admin_may_read_it():
    from fastapi import HTTPException

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await _call([], caller=member)

    assert exc.value.status_code == 403
