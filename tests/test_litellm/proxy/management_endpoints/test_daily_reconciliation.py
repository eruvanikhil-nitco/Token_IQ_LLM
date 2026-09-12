from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")


def _row(day: str, ours: str | None, theirs: str | None) -> dict:
    return {
        "day": day,
        "our_cost": None if ours is None else Decimal(ours),
        "their_cost": None if theirs is None else Decimal(theirs),
    }


async def _call(rows: list[dict], caller: UserAPIKeyAuth = ADMIN):
    from litellm.proxy.management_endpoints.provider_reconciliation import daily_reconciliation

    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=rows)
    with patch("litellm.proxy.proxy_server.prisma_client", client):
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


@pytest.mark.asyncio
async def test_only_an_admin_may_read_it():
    from fastapi import HTTPException

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await _call([], caller=member)

    assert exc.value.status_code == 403
