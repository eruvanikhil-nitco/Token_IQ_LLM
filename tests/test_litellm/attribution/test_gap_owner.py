from datetime import datetime
from decimal import Decimal

from litellm.attribution.gap_owner import GapRow, attribute
from litellm.types.proxy.attribution import AttributionRule

SETTLED = datetime(2026, 1, 18)
DAY = datetime(2026, 1, 17)
UNSETTLED_DAY = datetime(2026, 1, 18)


def test_an_account_rule_owns_the_gap_its_account_produced() -> None:
    row = GapRow(provider="openai", credential_name="acct", day=DAY, provider_cost=Decimal("10"), gateway_cost=Decimal("4"))
    rules = (AttributionRule("r-acct", "openai", "cloud_account", "acct", "team", "t-1"),)
    result = attribute((row,), rules, settled_before=SETTLED)
    assert result[0].owner_id == "t-1"
    assert result[0].owner_type == "team"
    assert result[0].gap == Decimal("6")
    assert result[0].state == "owned"
    assert result[0].rule_id == "r-acct"


def test_a_rule_for_another_account_on_the_same_provider_never_matches() -> None:
    row = GapRow("openai", "acct-a", DAY, Decimal("10"), Decimal("4"))
    rules = (AttributionRule("r", "openai", "cloud_account", "acct-b", "team", "t-1"),)
    assert attribute((row,), rules, settled_before=SETTLED)[0].state == "unallocated"


def test_a_gap_no_rule_matches_is_unallocated_not_zero() -> None:
    row = GapRow("openai", "acct", DAY, Decimal("10"), Decimal("4"))
    result = attribute((row,), (), settled_before=SETTLED)
    assert result[0].state == "unallocated"
    assert result[0].owner_id is None
    assert result[0].gap == Decimal("6")


def test_a_day_the_provider_has_not_settled_is_not_reported_as_a_gap() -> None:
    row = GapRow("openai", "acct", UNSETTLED_DAY, Decimal("0"), Decimal("4"))
    result = attribute((row,), (), settled_before=SETTLED)
    assert result[0].state == "not_settled"


def test_an_unsettled_day_reports_not_settled_even_when_a_rule_would_otherwise_match() -> None:
    row = GapRow("openai", "acct", UNSETTLED_DAY, Decimal("10"), Decimal("4"))
    rules = (AttributionRule("r-acct", "openai", "cloud_account", "acct", "team", "t-1"),)
    result = attribute((row,), rules, settled_before=SETTLED)
    assert result[0].state == "not_settled"
    assert result[0].owner_id is None
    assert result[0].gap == Decimal(0)


def test_the_gateway_recording_more_than_the_provider_billed_is_never_a_negative_gap() -> None:
    row = GapRow("openai", "acct", DAY, Decimal("3"), Decimal("4"))
    result = attribute((row,), (), settled_before=SETTLED)
    assert result[0].state == "matched"
    assert result[0].gap == Decimal("0")


def test_a_zero_gap_is_matched_not_owned_even_with_a_matching_rule() -> None:
    row = GapRow("openai", "acct", DAY, Decimal("5"), Decimal("5"))
    rules = (AttributionRule("r-acct", "openai", "cloud_account", "acct", "team", "t-1"),)
    result = attribute((row,), rules, settled_before=SETTLED)
    assert result[0].state == "matched"
    assert result[0].gap == Decimal(0)
    assert result[0].owner_id is None


def test_a_rule_for_another_provider_never_matches() -> None:
    row = GapRow("openai", "acct", DAY, Decimal("10"), Decimal("4"))
    rules = (AttributionRule("r", "anthropic", "cloud_account", "acct", "team", "t-1"),)
    assert attribute((row,), rules, settled_before=SETTLED)[0].state == "unallocated"


def test_money_never_passes_through_a_float() -> None:
    row = GapRow("openai", "acct", DAY, Decimal("0.30000000000000004"), Decimal("0.1"))
    assert attribute((row,), (), settled_before=SETTLED)[0].gap == Decimal("0.20000000000000004")


def test_attribute_preserves_row_order_and_handles_multiple_rows() -> None:
    row_owned = GapRow("openai", "acct", DAY, Decimal("10"), Decimal("4"))
    row_unallocated = GapRow("anthropic", "other-acct", DAY, Decimal("5"), Decimal("1"))
    rules = (AttributionRule("r-acct", "openai", "cloud_account", "acct", "project", "p-1"),)
    result = attribute((row_owned, row_unallocated), rules, settled_before=SETTLED)
    assert [r.state for r in result] == ["owned", "unallocated"]
    assert result[0].owner_type == "project"
    assert result[0].owner_id == "p-1"
