from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from token_iq.ledger.reconciliation import reconcile
from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.management_endpoints.ledger import reconciliation_response
from litellm.types.proxy.invoice import InvoiceAdjustment, ProviderInvoice
from litellm.types.proxy.management_endpoints.ledger_endpoints import InvoiceBody

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)
MEMBER: Final = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-test")
ADMIN: Final = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-test")


def _invoice(total: str, *, currency: str = "USD", adjustments: tuple[InvoiceAdjustment, ...] = ()) -> ProviderInvoice:
    return ProviderInvoice(
        invoice_id="i1",
        provider="openrouter",
        period_start=START,
        period_end=END,
        currency=currency,
        total=Decimal(total),
        adjustments=adjustments,
        note=None,
    )


def _body(invoice: ProviderInvoice | None, totals: dict[str, Decimal]):
    return reconciliation_response(
        provider="openrouter",
        period_start=START,
        period_end=END,
        result=reconcile(invoice=invoice, ledger_totals=totals),
        ledger_totals=totals,
    )


def test_every_amount_crosses_as_a_string() -> None:
    body: Final = _body(_invoice("100"), {"USD": Decimal("100")})
    assert isinstance(body.invoice_total, str)
    assert isinstance(body.unexplained, str)
    assert isinstance(body.explained_total, str)


def test_the_unexplained_remainder_is_always_present_even_when_zero() -> None:
    body: Final = _body(_invoice("100"), {"USD": Decimal("100")})
    assert body.outcome == "balanced"
    assert body.unexplained == "0"


def test_a_remainder_nobody_explains_is_reported_with_its_sign() -> None:
    body: Final = _body(_invoice("80"), {"USD": Decimal("100")})
    assert body.outcome == "unexplained_difference"
    assert body.unexplained == "-20"


def test_a_currency_mismatch_names_both_currencies_rather_than_one_number() -> None:
    body: Final = _body(_invoice("90", currency="EUR"), {"USD": Decimal("100")})
    assert body.outcome == "currency_mismatch"
    assert "EUR" in body.note
    assert "USD" in body.note
    assert body.ledger_total is None


def test_a_missing_bill_asks_for_one_rather_than_blaming_the_ledger() -> None:
    body: Final = _body(None, {"USD": Decimal("100")})
    assert body.outcome == "no_invoice"
    assert body.unexplained == "0"
    assert "no bill entered" in body.note.lower()


def test_each_adjustment_survives_into_the_response() -> None:
    invoice: Final = _invoice(
        "100",
        adjustments=(InvoiceAdjustment("credit", Decimal("-10"), "goodwill"), InvoiceAdjustment("tax", Decimal("15"))),
    )
    body: Final = _body(invoice, {"USD": Decimal("95")})
    assert tuple(a.kind for a in body.explained) == ("credit", "tax")
    assert body.explained_total == "5"
    assert body.unexplained == "0"


def test_a_tiny_remainder_is_readable_rather_than_scientific() -> None:
    body: Final = _body(_invoice("0.0000072"), {"USD": Decimal("0")})
    assert body.unexplained == "0.0000072"
    assert "E" not in body.unexplained


def test_the_period_is_reported_back_so_a_reader_knows_what_was_compared() -> None:
    body: Final = _body(_invoice("100"), {"USD": Decimal("100")})
    assert body.period_start == "2026-09-01"
    assert body.period_end == "2026-09-30"


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_another_team_s_ledger() -> None:
    from litellm.proxy.management_endpoints.ledger import ledger_lines

    with pytest.raises(HTTPException) as caught:
        await ledger_lines(
            provider=None,
            period_start="2026-09-01",
            period_end="2026-09-30",
            limit=50,
            cursor=None,
            user_api_key_dict=MEMBER,
        )
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_a_non_admin_cannot_enter_a_bill() -> None:
    from litellm.proxy.management_endpoints.ledger import upsert_invoice

    body: Final = InvoiceBody(provider="openrouter", period_start="2026-09-01", period_end="2026-09-30", total="100")
    with pytest.raises(HTTPException) as caught:
        await upsert_invoice(body=body, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_rather_than_reconciled_as_empty() -> None:
    from litellm.proxy.management_endpoints.ledger import ledger_reconciliation

    with pytest.raises(HTTPException) as caught:
        await ledger_reconciliation(
            provider="opnerouter",
            period_start="2026-09-01",
            period_end="2026-09-30",
            user_api_key_dict=ADMIN,
        )
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_a_period_that_is_not_a_date_is_refused_rather_than_defaulted() -> None:
    from litellm.proxy.management_endpoints.ledger import ledger_reconciliation

    with pytest.raises(HTTPException) as caught:
        await ledger_reconciliation(
            provider="openrouter",
            period_start="the first of September",
            period_end="2026-09-30",
            user_api_key_dict=ADMIN,
        )
    assert caught.value.status_code == 400


def test_an_invoice_with_an_unknown_adjustment_kind_is_refused_by_validation() -> None:
    with pytest.raises(ValidationError):
        InvoiceBody(
            provider="openrouter",
            period_start="2026-09-01",
            period_end="2026-09-30",
            total="100",
            adjustments=({"kind": "vibes", "amount": "1"},),  # pyright: ignore[reportArgumentType]  # the point of the test
        )


def test_a_cursor_round_trips_through_its_two_halves() -> None:
    from litellm.proxy.management_endpoints.ledger import _decode_cursor, _encode_cursor

    cursor: Final = (datetime(2026, 9, 15, tzinfo=timezone.utc), "openrouter:acct:2026-09-15")
    assert _decode_cursor(_encode_cursor(cursor)) == cursor


def test_a_cursor_we_cannot_read_is_none_rather_than_a_guessed_position() -> None:
    from litellm.proxy.management_endpoints.ledger import _decode_cursor

    assert _decode_cursor("nonsense") is None
    assert _decode_cursor("not-a-date|key") is None


def test_a_period_end_given_as_a_date_covers_that_whole_day() -> None:
    """A reader who types the thirtieth means all of it. Parsing to midnight and comparing with
    <= drops almost the entire final day, which would report a difference the size of that day's
    usage and blame the provider for it."""
    from litellm.proxy.management_endpoints.ledger import _period_end_or_400

    end: Final = _period_end_or_400("2026-09-30", "period_end")
    assert end.hour == 23
    assert end.minute == 59
    assert end.second == 59


def test_a_period_end_that_names_a_time_is_taken_at_its_word() -> None:
    from litellm.proxy.management_endpoints.ledger import _period_end_or_400

    end: Final = _period_end_or_400("2026-09-30T12:00:00+00:00", "period_end")
    assert end.hour == 12
    assert end.minute == 0


def test_a_period_start_is_still_the_first_instant_of_its_day() -> None:
    from litellm.proxy.management_endpoints.ledger import _day_or_400

    start: Final = _day_or_400("2026-09-01", "period_start")
    assert start.hour == 0
    assert start.minute == 0
