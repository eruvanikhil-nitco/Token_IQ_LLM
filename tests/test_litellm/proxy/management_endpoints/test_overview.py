from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from litellm.overview.totals import Sources, totals_for
from litellm.proxy.management_endpoints.overview import match_status, overview_response
from litellm.repositories.overview_repository import ProviderStanding

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)


def _sources(**over: object) -> Sources:
    base: Final[dict[str, object]] = {
        "provider_billed": Decimal("100"),
        "tool_new_money": Decimal("0"),
        "seats": Decimal("0"),
        "gateway_recorded": Decimal("90"),
        "unallocated": Decimal("10"),
        "has_any_data": True,
    }
    return Sources(**{**base, **over})  # pyright: ignore[reportArgumentType]  # test builder spreads a dict


def _response(**over: object):
    base: Final[dict[str, object]] = {
        "period_start": START,
        "period_end": END,
        "totals": totals_for(_sources()),
        "providers": (),
        "recommendations": (),
        "freshness": {},
        "sources_seen": (),
    }
    return overview_response(**{**base, **over})  # pyright: ignore[reportArgumentType]  # test builder


def test_every_amount_crosses_as_a_string() -> None:
    """A JSON number is a binary float by the time a browser has parsed it, and these are the
    figures a customer reads off the screen and repeats."""
    body: Final = _response()

    assert body.total == "150" or isinstance(body.total, str)
    assert isinstance(body.attributed, str)


def test_a_figure_that_cannot_be_computed_is_absent_rather_than_zero() -> None:
    body: Final = _response(totals=totals_for(_sources(has_any_data=False)))

    assert body.total is None
    assert body.unallocated_share is None


def test_the_period_asked_for_is_reported_back() -> None:
    body: Final = _response()

    assert body.period_start == "2026-09-01"
    assert body.period_end == "2026-09-30"


def test_a_provider_whose_bill_matches_the_gateway_reads_as_matched() -> None:
    standing: Final = ProviderStanding(provider="openrouter", billed=Decimal("10"), recorded=Decimal("10"))

    assert match_status(standing) == "matched"


def test_a_rounding_difference_is_not_shown_as_a_gap() -> None:
    standing: Final = ProviderStanding(provider="openrouter", billed=Decimal("10.0000001"), recorded=Decimal("10"))

    assert match_status(standing) == "matched"


def test_a_bill_larger_than_the_gateway_record_is_told_apart_from_a_smaller_one() -> None:
    """They are different problems: one is spend that bypassed the gateway, the other is the
    gateway charging for something the provider has not billed yet."""
    more: Final = ProviderStanding(provider="p", billed=Decimal("10"), recorded=Decimal("5"))
    less: Final = ProviderStanding(provider="p", billed=Decimal("5"), recorded=Decimal("10"))

    assert match_status(more) == "gateway_saw_less"
    assert match_status(less) == "gateway_saw_more"


def test_a_provider_the_gateway_never_saw_is_its_own_state_not_a_full_gap() -> None:
    """Reading a provider only through its bill is a normal way to run. Calling it a
    discrepancy would put a permanent red mark on a working connection."""
    standing: Final = ProviderStanding(provider="azure", billed=Decimal("10"), recorded=None)

    assert match_status(standing) == "not_seen_by_gateway"


def test_a_source_that_has_never_synced_is_reported_as_never_rather_than_omitted() -> None:
    """Leaving it out would make a broken connection look like one that does not exist."""
    body: Final = _response(freshness={}, sources_seen=("openrouter", "azure"))

    assert [entry.source for entry in body.freshness] == ["openrouter", "azure"]
    assert all(entry.last_sync_at is None for entry in body.freshness)


def test_a_source_that_has_synced_carries_its_time() -> None:
    body: Final = _response(freshness={"openrouter": "2026-09-18T11:11:46"}, sources_seen=("openrouter",))

    assert body.freshness[0].last_sync_at == "2026-09-18T11:11:46"


def test_the_providers_are_reported_with_their_own_figures() -> None:
    body: Final = _response(
        providers=(ProviderStanding(provider="openrouter", billed=Decimal("0.0078"), recorded=Decimal("0.0079")),)
    )

    assert body.providers[0].provider == "openrouter"
    assert body.providers[0].billed == "0.0078"
    assert body.providers[0].status == "gateway_saw_more"


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_the_overview() -> None:
    from fastapi import HTTPException

    from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
    from litellm.proxy.management_endpoints.overview import _admin_or_403

    with pytest.raises(HTTPException) as refusal:
        _admin_or_403(UserAPIKeyAuth(api_key="sk-x", user_role=LitellmUserRoles.INTERNAL_USER))

    assert refusal.value.status_code == 403
