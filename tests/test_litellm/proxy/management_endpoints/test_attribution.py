from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException

from token_iq.attribution.gap_owner import GapRow, attribute
from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.management_endpoints.attribution import unallocated_response
from litellm.types.proxy.attribution import AttributionRule

DAY: Final = datetime(2026, 9, 15, tzinfo=timezone.utc)
SETTLED: Final = datetime(2026, 9, 19, tzinfo=timezone.utc)
ADMIN: Final = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-test")
MEMBER: Final = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-test")

GAP_10_MINUS_4: Final = GapRow("openrouter", "acct", DAY, Decimal("10"), Decimal("4"))
ACCT_RULE: Final = AttributionRule("r-1", "openrouter", "cloud_account", "acct", "team", "t-1")


def _response(rows: tuple[GapRow, ...], rules: tuple[AttributionRule, ...]):
    return unallocated_response(
        provider="openrouter", days=7, attributed=attribute(rows, rules, settled_before=SETTLED)
    )


def test_unallocated_totals_cross_as_strings_not_numbers() -> None:
    body: Final = _response((GAP_10_MINUS_4,), ())
    assert body.total_unallocated == "6"
    assert isinstance(body.total_unallocated, str)
    assert isinstance(body.lines[0].gap, str)


def test_an_owned_gap_is_not_also_counted_as_unallocated() -> None:
    body: Final = _response((GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.total_unallocated == "0"
    assert body.total_owned == "6"
    assert body.lines[0].owner_id == "t-1"
    assert body.lines[0].rule_id == "r-1"


def test_a_rule_moves_money_between_the_totals_without_changing_it() -> None:
    without: Final = _response((GAP_10_MINUS_4,), ())
    with_rule: Final = _response((GAP_10_MINUS_4,), (ACCT_RULE,))
    assert Decimal(without.total_unallocated) == Decimal(with_rule.total_owned)
    assert Decimal(with_rule.total_unallocated) == Decimal(0)


def test_a_tiny_gap_is_readable_rather_than_scientific() -> None:
    row: Final = GapRow("openrouter", "acct", DAY, Decimal("0.0000072"), Decimal(0))
    body: Final = _response((row,), ())
    assert body.total_unallocated == "0.0000072"
    assert "E" not in body.total_unallocated


def test_a_day_the_provider_said_nothing_about_reports_no_cost_rather_than_zero() -> None:
    row: Final = GapRow("openrouter", "acct", DAY, None, Decimal("4"))
    body: Final = _response((row,), ())
    assert body.lines[0].provider_cost is None
    assert body.lines[0].state == "no_provider_data"
    assert body.total_unallocated == "0"


def test_an_unsettled_day_contributes_nothing_to_either_total() -> None:
    row: Final = GapRow("openrouter", "acct", SETTLED, Decimal("10"), Decimal("0"))
    body: Final = _response((row,), (ACCT_RULE,))
    assert body.lines[0].state == "not_settled"
    assert body.total_unallocated == "0"
    assert body.total_owned == "0"


def test_every_row_appears_as_a_line_in_the_order_it_arrived() -> None:
    other: Final = GapRow("openrouter", "other", DAY, Decimal("5"), Decimal("1"))
    body: Final = _response((GAP_10_MINUS_4, other), ())
    assert tuple(line.credential_name for line in body.lines) == ("acct", "other")


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_another_team_s_unallocated_spend() -> None:
    from litellm.proxy.management_endpoints.attribution import attribution_unallocated

    with pytest.raises(HTTPException) as caught:
        await attribution_unallocated(provider="openrouter", days=7, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_a_non_admin_cannot_list_the_rules() -> None:
    from litellm.proxy.management_endpoints.attribution import list_attribution_rules

    with pytest.raises(HTTPException) as caught:
        await list_attribution_rules(user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_rather_than_answered_empty() -> None:
    from litellm.proxy.management_endpoints.attribution import attribution_unallocated

    with pytest.raises(HTTPException) as caught:
        await attribution_unallocated(provider="opnerouter", days=7, user_api_key_dict=ADMIN)
    assert caught.value.status_code == 404


def test_an_unknown_owner_type_is_refused_by_validation() -> None:
    from pydantic import ValidationError

    from litellm.types.proxy.management_endpoints.attribution_endpoints import AttributionRuleBody

    with pytest.raises(ValidationError):
        AttributionRuleBody(
            provider="openrouter",
            match_type="cloud_account",
            match_value="acct",
            owner_type="departmnet",  # pyright: ignore[reportArgumentType]  # the point of the test
            owner_id="x",
        )


def test_an_unknown_match_type_is_refused_by_validation() -> None:
    from pydantic import ValidationError

    from litellm.types.proxy.management_endpoints.attribution_endpoints import AttributionRuleBody

    with pytest.raises(ValidationError):
        AttributionRuleBody(
            provider="openrouter",
            match_type="telepathy",  # pyright: ignore[reportArgumentType]  # the point of the test
            match_value="acct",
            owner_type="team",
            owner_id="x",
        )
