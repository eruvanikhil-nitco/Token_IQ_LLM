from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal


def test_a_row_is_read_by_column_name_never_by_position():
    """Azure and BigQuery both return bare arrays whose meaning comes from a separate
    column list. Reading by position works until the provider reorders them, and then it
    reports the wrong number instead of failing."""
    from litellm.provider_billing.cloud_rows import by_column_name

    columns = [{"name": "Cost", "type": "Number"}, {"name": "UsageDate", "type": "Number"}]

    assert by_column_name(columns, [12.5, 20260912]) == {"Cost": 12.5, "UsageDate": 20260912}


def test_a_reordered_response_still_reads_correctly():
    from litellm.provider_billing.cloud_rows import by_column_name

    columns = [{"name": "UsageDate"}, {"name": "Cost"}]

    assert by_column_name(columns, [20260912, 12.5])["Cost"] == 12.5


def test_a_row_shorter_than_its_columns_is_not_guessed_at():
    """A truncated row means the response is not the shape we believe it is. Filling the
    gap with None would put a null cost in a billing table."""
    from litellm.provider_billing.cloud_rows import by_column_name

    assert by_column_name([{"name": "a"}, {"name": "b"}], [1]) == {}


def test_bigquery_style_schema_fields_are_supported():
    """BigQuery calls the key 'name' too, but its columns arrive under schema.fields."""
    from litellm.provider_billing.cloud_rows import by_column_name

    fields = [{"name": "day", "type": "DATE"}, {"name": "cost", "type": "NUMERIC"}]

    assert by_column_name(fields, ["2026-09-12", "1.25"]) == {"day": "2026-09-12", "cost": "1.25"}


def test_an_iso_day_becomes_a_utc_datetime():
    from litellm.provider_billing.cloud_rows import day_from_iso

    parsed = day_from_iso("2026-09-12")

    assert parsed is not None
    assert parsed.date().isoformat() == "2026-09-12"
    assert parsed.tzinfo == timezone.utc


def test_a_full_timestamp_is_reduced_to_its_day():
    from litellm.provider_billing.cloud_rows import day_from_iso

    parsed = day_from_iso("2026-09-12T15:04:05Z")

    assert parsed is not None
    assert parsed.date().isoformat() == "2026-09-12"
    assert parsed.hour == 0


def test_nonsense_is_none_rather_than_today():
    """Defaulting a bad date to now would file an unparseable charge under the current day
    and quietly corrupt the comparison."""
    from litellm.provider_billing.cloud_rows import day_from_iso

    assert day_from_iso("not a date") is None
    assert day_from_iso(None) is None
    assert day_from_iso(20260912) is None


def test_a_string_amount_keeps_its_digits():
    """AWS returns Amount as a string precisely so it does not lose precision. Passing it
    through float would undo that."""
    from litellm.provider_billing.cloud_rows import decimal_or_none

    assert decimal_or_none("0.000001234567") == Decimal("0.000001234567")


def test_a_float_amount_goes_through_str():
    from litellm.provider_billing.cloud_rows import decimal_or_none

    assert decimal_or_none(0.1) == Decimal("0.1")


def test_a_bad_amount_is_none_rather_than_zero():
    """Zero is a claim that the provider charged nothing. None is a claim that we do not
    know, and only one of those is true here."""
    from litellm.provider_billing.cloud_rows import decimal_or_none

    assert decimal_or_none("n/a") is None
    assert decimal_or_none(None) is None
    assert decimal_or_none(True) is None


def test_the_settling_cutoff_excludes_days_the_cloud_has_not_finished_billing():
    """These bills land 24 to 48 hours late. A day still settling under-reports, and
    comparing it against our own figure would show a leak that does not exist."""
    from litellm.provider_billing.cloud_rows import settling_cutoff

    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

    assert settling_cutoff(now, hours=48) == now - timedelta(hours=48)
