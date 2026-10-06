from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException

from token_iq.attribution.gap_owner import GapRow, attribute
from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth
from token_iq.api.combined_usage import comparison_response
from token_iq.types.attribution import AttributionRule

DAY: Final = datetime(2026, 9, 15, tzinfo=timezone.utc)
SETTLED: Final = datetime(2026, 9, 19, tzinfo=timezone.utc)
MEMBER: Final = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-test")

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
    from token_iq.connectors.billing.fetch_profile import FETCH_PROFILES

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
    from token_iq.api.combined_usage import combined_comparison

    with pytest.raises(HTTPException) as caught:
        await combined_comparison(days=7, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403


from token_iq.api.combined_usage import explorer_response  # noqa: E402  # grouped with its tests
from token_iq.repositories.gateway_spend_repository import SpendSlice  # noqa: E402  # grouped with its tests

TEAM_SLICE: Final = SpendSlice(key="t-1", gateway_cost=Decimal("4"))


def _explorer(dimension: str, slices: tuple[SpendSlice, ...], rows: tuple[GapRow, ...], rules=(), total=None):
    return explorer_response(
        dimension=dimension,
        days=7,
        slices=slices,
        gateway_total=total if total is not None else sum((s.gateway_cost for s in slices), Decimal(0)),
        attributed=attribute(rows, rules, settled_before=SETTLED),
    )


def test_the_two_sources_are_reported_side_by_side_never_summed() -> None:
    body: Final = _explorer("team", (TEAM_SLICE,), (GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.total_through_gateway == "4"
    assert body.total_outside_gateway == "6"
    assert not hasattr(body, "total")


def test_outside_gateway_spend_lands_on_the_owner_a_rule_assigned() -> None:
    body: Final = _explorer("team", (TEAM_SLICE,), (GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.slices[0].key == "t-1"
    assert body.slices[0].outside_gateway == "6"
    assert body.unattributable_outside_gateway == "0"


def test_unowned_outside_gateway_spend_is_reported_apart_rather_than_spread() -> None:
    body: Final = _explorer("team", (TEAM_SLICE,), (GAP_10_MINUS_4,))
    assert body.unattributable_outside_gateway == "6"
    assert body.slices[0].outside_gateway == "0"


def test_grouping_by_model_cannot_place_outside_gateway_spend_and_says_why() -> None:
    body: Final = _explorer("model", (SpendSlice("gpt-4o", Decimal("4")),), (GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.slices[0].outside_gateway == "0"
    assert body.unattributable_outside_gateway == "6"
    assert "cannot be shown per model" in body.note


def test_gateway_spend_the_dimension_cannot_place_is_named_rather_than_lost() -> None:
    body: Final = _explorer("team", (TEAM_SLICE,), (), total=Decimal("10"))
    assert body.total_through_gateway == "10"
    assert body.unallocated_to_a_slice == "6"


def test_a_dimension_with_no_rows_says_so_rather_than_reporting_zero_spend() -> None:
    body: Final = _explorer("project", (), ())
    assert body.slices == ()
    assert "no project spend" in body.note.lower()


def test_a_rule_naming_another_dimension_does_not_leak_onto_this_one() -> None:
    project_rule: Final = AttributionRule("r-2", "openrouter", "cloud_account", "acct", "project", "t-1")
    body: Final = _explorer("team", (TEAM_SLICE,), (GAP_10_MINUS_4,), (project_rule,))
    assert body.slices[0].outside_gateway == "0"
    assert body.unattributable_outside_gateway == "6"


def test_every_explorer_amount_crosses_as_a_string() -> None:
    body: Final = _explorer("team", (TEAM_SLICE,), (GAP_10_MINUS_4,), (ACCT_RULE,))
    assert isinstance(body.total_through_gateway, str)
    assert isinstance(body.slices[0].outside_gateway, str)
    assert isinstance(body.unallocated_to_a_slice, str)


def test_a_slice_crosses_with_the_name_a_person_would_recognise() -> None:
    named: Final = SpendSlice(key="t-1", gateway_cost=Decimal("4"), label="Platform")
    body: Final = _explorer("team", (named,), (GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.slices[0].name == "Platform"


def test_a_slice_keeps_its_identifier_alongside_the_name() -> None:
    """The name is for reading. The identifier is what a rule, a filter or a link is written
    against, so replacing one with the other would make the row unusable."""
    named: Final = SpendSlice(key="t-1", gateway_cost=Decimal("4"), label="Platform")
    body: Final = _explorer("team", (named,), (GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.slices[0].key == "t-1"


def test_a_spender_with_no_name_shows_its_identifier_rather_than_vanishing() -> None:
    body: Final = _explorer("team", (TEAM_SLICE,), (GAP_10_MINUS_4,), (ACCT_RULE,))
    assert body.slices[0].name == "t-1"


def test_naming_a_slice_does_not_move_the_money_that_lands_on_it() -> None:
    """Outside-gateway spend is matched to a slice by identifier. Matching on the name instead
    would put a rule's money on the wrong row, or on no row, the moment a team is renamed."""
    named: Final = SpendSlice(key="t-1", gateway_cost=Decimal("4"), label="Platform")
    assert _explorer("team", (named,), (GAP_10_MINUS_4,), (ACCT_RULE,)).slices[0].outside_gateway == "6"


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_the_explorer_and_so_cannot_learn_other_teams_names() -> None:
    """The explorer now carries team and user names, not only identifiers, so the guard on this
    route is what stops a member reading the names of teams they are not in."""
    from token_iq.api.combined_usage import combined_explorer

    with pytest.raises(HTTPException) as caught:
        await combined_explorer(dimension="team", days=7, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403
