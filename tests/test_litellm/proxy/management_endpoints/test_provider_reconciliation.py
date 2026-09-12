from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")


def _prisma(rows: list[dict]) -> MagicMock:
    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=rows)
    return client


def _row(request_id: str, ours: str, theirs: str | None, evidence: str = "reconciled") -> dict:
    return {
        "request_id": request_id,
        "model": "openai/gpt-4o-mini",
        "credential_name": "acme-openrouter",
        "our_cost": Decimal(ours),
        "their_cost": None if theirs is None else Decimal(theirs),
        "evidence": evidence,
    }


async def _call(rows: list[dict], caller: UserAPIKeyAuth = ADMIN):
    from litellm.proxy.management_endpoints.provider_reconciliation import provider_reconciliation

    with patch("litellm.proxy.proxy_server.prisma_client", _prisma(rows)):
        return await provider_reconciliation(provider="openrouter", days=7, user_api_key_dict=caller)


@pytest.mark.asyncio
async def test_the_delta_is_what_the_page_exists_to_show():
    """Two totals side by side is a report. The difference between them is the product."""
    result = await _call([_row("gen-1", "0.0000030", "0.0000025")])

    assert result.rows[0].delta == "0.0000005"
    assert result.delta == "0.0000005"


@pytest.mark.asyncio
async def test_costs_cross_the_wire_as_strings():
    """A twelve-decimal-place figure serialised as a JSON float arrives at the dashboard
    already rounded, which would make the gateway look wrong about its own number."""
    result = await _call([_row("gen-1", "0.000001234567", "0.000001234567")])

    assert result.rows[0].our_cost == "0.000001234567"
    assert isinstance(result.our_total, str)


@pytest.mark.asyncio
async def test_a_request_the_provider_has_not_priced_yet_is_counted_not_hidden():
    """A row we have and they do not is either a backlog we have not polled or spend they
    never billed. Dropping it would hide both."""
    result = await _call([_row("gen-1", "0.000003", None, evidence="allocated")])

    assert result.unmatched_our_rows == 1
    assert result.rows[0].their_cost is None
    assert result.rows[0].delta is None
    assert result.rows[0].evidence == "allocated"


@pytest.mark.asyncio
async def test_an_unmatched_row_does_not_pollute_their_total():
    """Treating a missing provider figure as zero would report a fictitious saving."""
    result = await _call(
        [_row("gen-1", "0.000003", None, evidence="allocated"), _row("gen-2", "0.000002", "0.000002")]
    )

    assert result.their_total == "0.000002"
    assert result.our_total == "0.000005"


@pytest.mark.asyncio
async def test_the_window_is_bounded_so_one_call_cannot_scan_all_history():
    """Spend logs grow without limit. An unbounded reconciliation query would eventually
    take the database down while someone is looking at a dashboard."""
    from litellm.proxy.management_endpoints.provider_reconciliation import provider_reconciliation

    client = _prisma([])
    with patch("litellm.proxy.proxy_server.prisma_client", client):
        await provider_reconciliation(provider="openrouter", days=7, user_api_key_dict=ADMIN)

    sql = client.db.query_raw.await_args.args[0]
    assert "LIMIT" in sql.upper()
    assert client.db.query_raw.await_args.args[1:] == ("openrouter", "7")


@pytest.mark.asyncio
async def test_only_an_admin_may_read_it():
    """This names every provider account and what it was charged, across every team."""
    from fastapi import HTTPException

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await _call([], caller=member)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_tiny_delta_is_readable_rather_than_scientific():
    """Subtracting two token costs almost always produces a number Decimal would render
    as 5E-7. On a finance screen that reads as broken."""
    result = await _call([_row("gen-1", "0.0000030", "0.0000025")])

    assert "E" not in result.delta
    assert "E" not in result.rows[0].our_cost
