from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=GatewayUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")


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
    from token_iq.api.provider_reconciliation import provider_reconciliation

    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma(rows)):
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
    from token_iq.api.provider_reconciliation import provider_reconciliation

    client = _prisma([])
    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", client):
        await provider_reconciliation(provider="openrouter", days=7, user_api_key_dict=ADMIN)

    sql = client.db.query_raw.await_args.args[0]
    assert "LIMIT" in sql.upper()
    assert client.db.query_raw.await_args.args[1:] == ("openrouter", "7")


@pytest.mark.asyncio
async def test_only_an_admin_may_read_it():
    """This names every provider account and what it was charged, across every team."""
    from fastapi import HTTPException

    member = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await _call([], caller=member)

    assert exc.value.status_code == 403


def _driver_decoded(sql: str, marker: str, value: str) -> object:
    return value if marker in sql else float(value)


def _prisma_matching_driver(our_cost: str, their_cost: str) -> MagicMock:
    client = MagicMock()

    async def _query_raw(sql: str, *_args: object) -> list[dict[str, object]]:
        return [
            {
                "request_id": "gen-1",
                "model": "openai/gpt-4o-mini",
                "credential_name": "acme-openrouter",
                "our_cost": _driver_decoded(sql, "s.spend::numeric::text", our_cost),
                "their_cost": _driver_decoded(sql, "f.billed_cost::numeric::text", their_cost),
                "evidence": "reconciled",
            }
        ]

    client.db.query_raw = AsyncMock(side_effect=_query_raw)
    return client


@pytest.mark.asyncio
async def test_the_total_keeps_every_digit_the_provider_billed():
    from token_iq.api.provider_reconciliation import provider_reconciliation

    client = _prisma_matching_driver(our_cost="0.123456789012345678", their_cost="0.123456789012345678")
    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", client):
        result = await provider_reconciliation(provider="openrouter", days=7, user_api_key_dict=ADMIN)

    assert result.rows[0].our_cost == "0.123456789012345678"
    assert result.rows[0].their_cost == "0.123456789012345678"
    assert result.our_total == "0.123456789012345678"
    assert result.their_total == "0.123456789012345678"
    sql = client.db.query_raw.await_args.args[0]
    assert "s.spend::numeric::text" in sql
    assert "f.billed_cost::numeric::text" in sql


@pytest.mark.asyncio
async def test_a_float_input_is_rejected_as_unparseable():
    from token_iq.api.provider_reconciliation import _decimal

    assert _decimal(1.5) is None


@pytest.mark.asyncio
async def test_a_tiny_delta_is_readable_rather_than_scientific():
    """Subtracting two token costs almost always produces a number Decimal would render
    as 5E-7. On a finance screen that reads as broken."""
    result = await _call([_row("gen-1", "0.0000030", "0.0000025")])

    assert "E" not in result.delta
    assert "E" not in result.rows[0].our_cost


def _connector_returning(result: object, provider: str = "anthropic"):
    class _Connector:
        def __init__(self) -> None:
            self.provider = provider

        async def fetch(self, **_: object):
            return result

    return _Connector()


async def _creds(_provider: str):
    from token_iq.types.provider_billing import BillingCredential

    return (BillingCredential(name="acme", values={"api_key": "sk-ant-admin01-x"}),)


async def _no_creds(_provider: str):
    return ()


@pytest.mark.asyncio
async def test_the_probe_reports_a_working_connector_without_writing_anything():
    """Neither Anthropic nor OpenAI could be verified on a machine with no admin key. The
    probe is how the first real key gets checked, in one command."""
    from datetime import datetime, timezone

    from token_iq.api.provider_reconciliation import run_billing_probe
    from token_iq.types.provider_billing import Fetched, ProviderUsageFact

    fact = ProviderUsageFact(
        fact_key="anthropic:2026-09-12:claude-opus-5",
        provider="anthropic",
        credential_name="acme",
        grain="day",
        bucket_start=datetime.now(timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("1.25"),
    )

    result = await run_billing_probe(
        provider="anthropic",
        connectors=(_connector_returning(Fetched(facts=(fact,), watermark=datetime.now(timezone.utc))),),
        credentials_for=_creds,
    )

    assert result.outcome == "fetched"
    assert result.facts_found == 1
    assert result.sample_cost == "1.25"
    assert result.credential_name == "acme"


@pytest.mark.asyncio
async def test_the_probe_names_a_missing_credential_rather_than_failing():
    from token_iq.api.provider_reconciliation import run_billing_probe

    result = await run_billing_probe(
        provider="anthropic", connectors=(_connector_returning(None),), credentials_for=_no_creds
    )

    assert result.outcome == "not_configured"
    assert "billing_ingestion" in (result.detail or "")
    assert result.credential_name is None


@pytest.mark.asyncio
async def test_the_probe_reports_a_refused_key_as_a_failure_with_the_reason():
    """The whole point on the day a key arrives: say why, not just that it did not work."""
    from token_iq.api.provider_reconciliation import run_billing_probe
    from token_iq.types.provider_billing import FetchFailed

    result = await run_billing_probe(
        provider="anthropic",
        connectors=(_connector_returning(FetchFailed(reason="anthropic refused credential acme", retryable=False)),),
        credentials_for=_creds,
    )

    assert result.outcome == "failed"
    assert "refused" in (result.detail or "")
    assert "retryable=False" in (result.detail or "")


@pytest.mark.asyncio
async def test_the_probe_says_so_when_no_connector_exists_for_a_provider():
    from token_iq.api.provider_reconciliation import run_billing_probe

    result = await run_billing_probe(provider="bedrock", connectors=(), credentials_for=_no_creds)

    assert result.outcome == "no_connector"


@pytest.mark.asyncio
async def test_a_provider_that_answers_with_nothing_is_not_reported_as_broken():
    """An empty window is a healthy answer, and a customer with no spend yesterday would
    otherwise see a failure."""
    from datetime import datetime, timezone

    from token_iq.api.provider_reconciliation import run_billing_probe
    from token_iq.types.provider_billing import Fetched

    result = await run_billing_probe(
        provider="anthropic",
        connectors=(_connector_returning(Fetched(facts=(), watermark=datetime.now(timezone.utc))),),
        credentials_for=_creds,
    )

    assert result.outcome == "fetched"
    assert result.facts_found == 0


@pytest.mark.asyncio
async def test_only_an_admin_may_probe():
    from fastapi import HTTPException

    from token_iq.api.provider_reconciliation import provider_billing_probe

    member = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await provider_billing_probe(provider="anthropic", user_api_key_dict=member)

    assert exc.value.status_code == 403
