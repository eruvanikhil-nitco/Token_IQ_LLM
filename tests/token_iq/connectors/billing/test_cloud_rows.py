from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal


def test_a_row_is_read_by_column_name_never_by_position():
    """Azure and BigQuery both return bare arrays whose meaning comes from a separate
    column list. Reading by position works until the provider reorders them, and then it
    reports the wrong number instead of failing."""
    from token_iq.connectors.billing.cloud_rows import by_column_name

    columns = [{"name": "Cost", "type": "Number"}, {"name": "UsageDate", "type": "Number"}]

    assert by_column_name(columns, [12.5, 20260912]) == {"Cost": 12.5, "UsageDate": 20260912}


def test_a_reordered_response_still_reads_correctly():
    from token_iq.connectors.billing.cloud_rows import by_column_name

    columns = [{"name": "UsageDate"}, {"name": "Cost"}]

    assert by_column_name(columns, [20260912, 12.5])["Cost"] == 12.5


def test_a_row_shorter_than_its_columns_is_not_guessed_at():
    """A truncated row means the response is not the shape we believe it is. Filling the
    gap with None would put a null cost in a billing table."""
    from token_iq.connectors.billing.cloud_rows import by_column_name

    assert by_column_name([{"name": "a"}, {"name": "b"}], [1]) == {}


def test_bigquery_style_schema_fields_are_supported():
    """BigQuery calls the key 'name' too, but its columns arrive under schema.fields."""
    from token_iq.connectors.billing.cloud_rows import by_column_name

    fields = [{"name": "day", "type": "DATE"}, {"name": "cost", "type": "NUMERIC"}]

    assert by_column_name(fields, ["2026-09-12", "1.25"]) == {"day": "2026-09-12", "cost": "1.25"}


def test_an_iso_day_becomes_a_utc_datetime():
    from token_iq.connectors.billing.cloud_rows import day_from_iso

    parsed = day_from_iso("2026-09-12")

    assert parsed is not None
    assert parsed.date().isoformat() == "2026-09-12"
    assert parsed.tzinfo == timezone.utc


def test_a_full_timestamp_is_reduced_to_its_day():
    from token_iq.connectors.billing.cloud_rows import day_from_iso

    parsed = day_from_iso("2026-09-12T15:04:05Z")

    assert parsed is not None
    assert parsed.date().isoformat() == "2026-09-12"
    assert parsed.hour == 0


def test_nonsense_is_none_rather_than_today():
    """Defaulting a bad date to now would file an unparseable charge under the current day
    and quietly corrupt the comparison."""
    from token_iq.connectors.billing.cloud_rows import day_from_iso

    assert day_from_iso("not a date") is None
    assert day_from_iso(None) is None
    assert day_from_iso(20260912) is None


def test_a_string_amount_keeps_its_digits():
    """AWS returns Amount as a string precisely so it does not lose precision. Passing it
    through float would undo that."""
    from token_iq.connectors.billing.cloud_rows import decimal_or_none

    assert decimal_or_none("0.000001234567") == Decimal("0.000001234567")


def test_a_float_amount_goes_through_str():
    from token_iq.connectors.billing.cloud_rows import decimal_or_none

    assert decimal_or_none(0.1) == Decimal("0.1")


def test_an_exact_amount_is_handed_back_untouched():
    """Azure's body is decoded with exact numbers, so the amount arrives already exact.
    Rebuilding it through str() would work today and break the first time a provider sends
    a precision this round trip cannot carry."""
    from token_iq.connectors.billing.cloud_rows import decimal_or_none

    exact = Decimal("1.0000000000000002E-5")

    assert decimal_or_none(exact) is exact


def test_a_json_number_is_decoded_without_ever_being_a_float():
    """Azure returns a cost as a JSON number and json.loads decodes one to a binary float
    unless told otherwise. The digits are gone by then; no Decimal built afterwards can
    recover what the float never held."""
    from token_iq.connectors.billing.cloud_rows import exact_json

    decoded = exact_json('{"Cost": 1.0000000000000002e-05}')

    assert decoded == {"Cost": Decimal("1.0000000000000002e-05")}


def test_an_exact_amount_is_carried_into_raw_as_its_own_digits():
    """A fact's raw payload is stored as JSON and Decimal has no JSON encoder, so one
    exactly decoded amount would fail the write for the whole fact."""
    from token_iq.connectors.billing.cloud_rows import json_safe_row

    assert json_safe_row({"Cost": Decimal("1.50"), "UsageDate": 20260912}) == {
        "Cost": "1.50",
        "UsageDate": 20260912,
    }


def test_an_exact_amount_nested_anywhere_in_the_row_is_carried_as_its_own_digits_too():
    """The row is handed to json.dumps whole, so an exact amount one level down fails the
    write for the whole fact exactly as a top-level one would. Nothing either cloud
    documents nests today, and this connector has already been bitten twice by a json.dumps
    encoder gap, so the next shape change must not land on a third."""
    from token_iq.connectors.billing.cloud_rows import json_safe_row

    row = json_safe_row(
        {
            "Cost": Decimal("1.50"),
            "detail": {"rate": Decimal("0.25"), "tiers": [Decimal("0.1"), {"unit": Decimal("2")}]},
        }
    )

    assert json.loads(json.dumps(dict(row))) == {
        "Cost": "1.50",
        "detail": {"rate": "0.25", "tiers": ["0.1", {"unit": "2"}]},
    }


def test_a_window_is_floored_to_the_day_it_starts_in():
    """A connector that reports by day has to ask for whole days. A window starting mid-day
    sums only the tail of that day, and the day-keyed fact it writes overwrites the complete
    total an earlier run already stored."""
    from token_iq.connectors.billing.cloud_rows import utc_day_start

    floored = utc_day_start(datetime(2026, 9, 18, 14, 37, 11, 500, tzinfo=timezone.utc))

    assert floored == datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc)


def test_a_window_in_another_timezone_is_floored_to_its_utc_day():
    """The gateway stores spend in UTC, so the cloud side has to agree with it rather than
    with whatever offset the instant arrived in."""
    from token_iq.connectors.billing.cloud_rows import utc_day_start

    early = datetime(2026, 9, 19, 1, 30, tzinfo=timezone(timedelta(hours=9)))

    assert utc_day_start(early) == datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc)


def test_the_currency_the_provider_named_wins_over_the_default():
    """A euro bill stored as dollars is compared against dollar gateway spend, and the
    difference reads as a leak that does not exist."""
    from token_iq.connectors.billing.cloud_rows import currency_or_default

    assert currency_or_default("EUR") == "EUR"
    assert currency_or_default("") == "USD"
    assert currency_or_default(None) == "USD"


def test_a_bad_amount_is_none_rather_than_zero():
    """Zero is a claim that the provider charged nothing. None is a claim that we do not
    know, and only one of those is true here."""
    from token_iq.connectors.billing.cloud_rows import decimal_or_none

    assert decimal_or_none("n/a") is None
    assert decimal_or_none(None) is None
    assert decimal_or_none(True) is None


def test_the_settling_cutoff_excludes_days_the_cloud_has_not_finished_billing():
    """These bills land 24 to 48 hours late. A day still settling under-reports, and
    comparing it against our own figure would show a leak that does not exist."""
    from token_iq.connectors.billing.cloud_rows import settling_cutoff

    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

    assert settling_cutoff(now, hours=48) == now - timedelta(hours=48)
