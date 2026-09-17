from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.types.proxy.provider_billing import SummaryRow, TokenTotals

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

    from litellm.proxy.management_endpoints.provider_usage import provider_usage_summary

    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_summary(provider="openrouter", days=30, user_api_key_dict=NON_ADMIN)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_usage_without_a_database_answers_500_not_a_crash():
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.provider_usage import provider_usage_summary

    with patch("litellm.proxy.proxy_server.prisma_client", None):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_summary(provider="openrouter", days=30, user_api_key_dict=ADMIN)

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_rather_than_answering_an_empty_summary():
    """An empty summary for a typo'd provider reads as 'you spent nothing', which is a
    different and much worse message than 'no such provider'."""
    from fastapi import HTTPException

    from litellm.proxy.management_endpoints.provider_usage import provider_usage_summary

    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()):
        with pytest.raises(HTTPException) as exc:
            await provider_usage_summary(provider="notreal", days=30, user_api_key_dict=ADMIN)

    assert exc.value.status_code == 404
    assert "notreal" in exc.value.detail["error"]
    assert "openrouter" in exc.value.detail["error"]


@pytest.mark.asyncio
async def test_the_response_carries_the_settling_note_so_recent_figures_are_not_read_as_final():
    from litellm.proxy.management_endpoints.provider_usage import provider_usage_summary

    rows = (
        SummaryRow(model="claude-3-5", credential_name="prod", evidence="reconciled", billed_cost=Decimal("1.50"),
                   facts=3),
    )
    fake_repository = _FakeRepository(rows, TOKENS)

    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()):
        with patch("litellm.proxy.management_endpoints.provider_usage.ProviderUsageFactRepository", fake_repository):
            result = await provider_usage_summary(provider="bedrock", days=30, user_api_key_dict=ADMIN)

    assert result.total_cost == "1.50"
    assert isinstance(result.total_cost, str)
    assert "settles over about" in result.settling_note
    assert result.delay_note
    assert result.grain == "day"
