from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException

from litellm.attribution.gap_owner import GapRow, attribute
from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.management_endpoints.combined_usage import comparison_response
from litellm.types.proxy.attribution import AttributionRule

DAY: Final = datetime(2026, 9, 15, tzinfo=timezone.utc)
SETTLED: Final = datetime(2026, 9, 19, tzinfo=timezone.utc)
MEMBER: Final = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-test")

GAP_10_MINUS_4: Final = GapRow("openrouter", "acct", DAY, Decimal("10"), Decimal("4"))
UNSETTLED: Final = GapRow("openrouter", "acct", SETTLED, Decimal("10"), Decimal("4"))
SILENT: Final = GapRow("openrouter", "acct", DAY, None, Decimal("4"))
ACCT_RULE: Final = AttributionRule("r-1", "openrouter", "cloud_account", "acct", "team", "t-1")


def _body(rows: tuple[GapRow, ...], rules: tuple[AttributionRule, ...] = ()):
    return comparison_response(days=7, attributed=attribute(rows, rules, settled_before=SETTLED))


def test_the_three_totals_are_reported_separately_and_never_added() -> None:
    body: Final = _body((GAP_10_MINUS_4,))
    assert body.total_provider == "10"
    assert body.total_gateway == "4"
    assert body.total_gap == "6"
    assert not hasattr(body, "total")


def test_a_day_the_provider_has_not_settled_contributes_to_no_total() -> None:
    body: Final = _body((UNSETTLED,))
    assert body.rows[0].status == "not_settled"
    assert body.total_gap == "0"
    assert body.total_gateway == "0"
    assert body.total_provider == "0"


def test_a_day_the_provider_said_nothing_about_is_not_reported_as_matched() -> None:
    body: Final = _body((SILENT,))
    assert body.rows[0].status == "no_provider_data"
    assert body.rows[0].provider_cost is None
    assert body.total_gateway == "0"


def test_an_owned_difference_is_still_a_gap_but_names_its_owner() -> None:
    body: Final = _body((GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.rows[0].status == "gap"
    assert body.rows[0].owner_type == "team"
    assert body.rows[0].owner_id == "t-1"


def test_an_unclaimed_difference_is_a_gap_with_no_owner() -> None:
    body: Final = _body((GAP_10_MINUS_4,))
    assert body.rows[0].status == "gap"
    assert body.rows[0].owner_id is None


def test_a_matched_day_contributes_to_both_source_totals_but_no_gap() -> None:
    row: Final = GapRow("openrouter", "acct", DAY, Decimal("5"), Decimal("5"))
    body: Final = _body((row,))
    assert body.rows[0].status == "matched"
    assert body.total_gateway == "5"
    assert body.total_provider == "5"
    assert body.total_gap == "0"


def test_every_amount_crosses_as_a_string() -> None:
    body: Final = _body((GAP_10_MINUS_4,))
    assert isinstance(body.total_gap, str)
    assert isinstance(body.rows[0].gateway_cost, str)
    assert isinstance(body.rows[0].gap, str)


def test_a_tiny_difference_is_readable_rather_than_scientific() -> None:
    row: Final = GapRow("openrouter", "acct", DAY, Decimal("0.0000072"), Decimal(0))
    body: Final = _body((row,))
    assert body.total_gap == "0.0000072"
    assert "E" not in body.total_gap


def test_a_provider_is_named_the_same_here_as_on_the_connections_page() -> None:
    from litellm.provider_billing.fetch_profile import FETCH_PROFILES

    body: Final = _body((GAP_10_MINUS_4,))
    assert body.rows[0].display_name == FETCH_PROFILES["openrouter"].display_name


def test_a_provider_with_no_profile_still_appears_rather_than_vanishing() -> None:
    row: Final = GapRow("some_new_provider", "acct", DAY, Decimal("10"), Decimal("4"))
    body: Final = _body((row,))
    assert body.rows[0].display_name == "some_new_provider"


def test_every_row_keeps_the_account_that_produced_it() -> None:
    other: Final = GapRow("openrouter", "other", DAY, Decimal("5"), Decimal("1"))
    body: Final = _body((GAP_10_MINUS_4, other))
    assert tuple(r.credential_name for r in body.rows) == ("acct", "other")


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_another_team_s_comparison() -> None:
    from litellm.proxy.management_endpoints.combined_usage import combined_comparison

    with pytest.raises(HTTPException) as caught:
        await combined_comparison(days=7, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403
