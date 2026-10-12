from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from token_iq.ledger.reconciliation import reconcile
from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth
from token_iq.api.ledger import reconciliation_response
from token_iq.types.attribution import AttributionRule
from token_iq.types.invoice import InvoiceAdjustment, ProviderInvoice
from token_iq.api.types.ledger import InvoiceBody

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)
MEMBER: Final = UserAPIKeyAuth(user_role=GatewayUserRoles.INTERNAL_USER, api_key="sk-test")
ADMIN: Final = UserAPIKeyAuth(user_role=GatewayUserRoles.PROXY_ADMIN, api_key="sk-test")


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
    from token_iq.api.ledger import ledger_lines

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
    from token_iq.api.ledger import upsert_invoice

    body: Final = InvoiceBody(provider="openrouter", period_start="2026-09-01", period_end="2026-09-30", total="100")
    with pytest.raises(HTTPException) as caught:
        await upsert_invoice(body=body, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_rather_than_reconciled_as_empty() -> None:
    from token_iq.api.ledger import ledger_reconciliation

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
    from token_iq.api.ledger import ledger_reconciliation

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
    from token_iq.api.ledger import _decode_cursor, _encode_cursor

    cursor: Final = (datetime(2026, 9, 15, tzinfo=timezone.utc), "openrouter:acct:2026-09-15")
    assert _decode_cursor(_encode_cursor(cursor)) == cursor


def test_a_cursor_we_cannot_read_is_none_rather_than_a_guessed_position() -> None:
    from token_iq.api.ledger import _decode_cursor

    assert _decode_cursor("nonsense") is None
    assert _decode_cursor("not-a-date|key") is None


def test_a_period_end_given_as_a_date_covers_that_whole_day() -> None:
    """A reader who types the thirtieth means all of it. Parsing to midnight and comparing with
    <= drops almost the entire final day, which would report a difference the size of that day's
    usage and blame the provider for it."""
    from token_iq.api.ledger import _period_end_or_400

    end: Final = _period_end_or_400("2026-09-30", "period_end")
    assert end.hour == 23
    assert end.minute == 59
    assert end.second == 59


def test_a_period_end_that_names_a_time_is_taken_at_its_word() -> None:
    from token_iq.api.ledger import _period_end_or_400

    end: Final = _period_end_or_400("2026-09-30T12:00:00+00:00", "period_end")
    assert end.hour == 12
    assert end.minute == 0


def test_a_period_start_is_still_the_first_instant_of_its_day() -> None:
    from token_iq.api.ledger import _day_or_400

    start: Final = _day_or_400("2026-09-01", "period_start")
    assert start.hour == 0
    assert start.minute == 0


class TestABillEnteredIsTheBillReconciliationLooksUp:
    """The entered bill and the period a read asks about have to be the same instants.

    `for_period` matches a period exactly. A bill stored with its end left at midnight is not the
    bill a reconciliation request for that same date looks up, so the month reports "no bill entered
    for this period yet" while the bill sits in the table, and the coverage query counts a fully
    invoiced provider as missing because its final day falls outside its own invoice. Nothing in a
    status code or a response field shows it: both calls succeed.
    """

    def test_a_month_entered_as_dates_covers_its_final_day(self) -> None:
        from token_iq.api.ledger import invoice_from_body

        entered: Final = invoice_from_body(
            InvoiceBody(provider="openrouter", period_start="2026-09-01", period_end="2026-09-30", total="123.45")
        )

        assert entered.period_end == datetime(2026, 9, 30, 23, 59, 59, 999000, tzinfo=timezone.utc)

    def test_the_stored_period_is_the_period_a_read_of_the_same_dates_asks_for(self) -> None:
        from token_iq.api.ledger import _day_or_400, _period_end_or_400, invoice_from_body

        entered: Final = invoice_from_body(
            InvoiceBody(provider="openrouter", period_start="2026-09-01", period_end="2026-09-30", total="1")
        )

        assert (entered.period_start, entered.period_end) == (
            _day_or_400("2026-09-01", "period_start"),
            _period_end_or_400("2026-09-30", "period_end"),
        )

    def test_the_first_day_of_the_month_is_inside_the_period_it_was_entered_for(self) -> None:
        # The coverage query asks `period_start <= bucket_start`, so a start pushed past midnight
        # would leave the first day of the month uncovered by its own invoice.
        from token_iq.api.ledger import invoice_from_body

        entered: Final = invoice_from_body(
            InvoiceBody(provider="openrouter", period_start="2026-09-01", period_end="2026-09-30", total="1")
        )

        assert entered.period_start == datetime(2026, 9, 1, tzinfo=timezone.utc)

    def test_an_end_that_names_a_time_is_stored_as_the_time_it_names(self) -> None:
        from token_iq.api.ledger import invoice_from_body

        entered: Final = invoice_from_body(
            InvoiceBody(
                provider="openrouter",
                period_start="2026-09-01",
                period_end="2026-09-15T12:00:00+00:00",
                total="1",
            )
        )

        assert entered.period_end == datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    def test_every_figure_on_the_bill_survives_as_exact_digits(self) -> None:
        from token_iq.api.ledger import invoice_from_body

        entered: Final = invoice_from_body(
            InvoiceBody(
                provider="openrouter",
                period_start="2026-09-01",
                period_end="2026-09-30",
                total="48210.07",
                adjustments=({"kind": "credit", "amount": "400.01"},),  # pyright: ignore[reportArgumentType]  # pydantic coerces the mapping
                note="task 4",
            )
        )

        assert entered.total == Decimal("48210.07")
        assert entered.adjustments[0].amount == Decimal("400.01")


class TestWhatTheUploadsTabReads:
    """The shaping the Uploads tab depends on.

    The rules are tested in `tests/token_iq/ledger/`. What is asserted here is the part that only
    exists at the boundary: a missing bill carrying no total, the provider list being exactly the
    set the save accepts, and every forwarding state reaching the client as itself.
    """

    def test_a_missing_bill_carries_no_total_at_all(self) -> None:
        """Not a total of zero and not an empty string. There is no bill, so the only figure
        available would be one Token IQ worked out, and a figure it worked out sitting in an
        invoice column is how a provider total and an attribution total get added together."""
        from token_iq.api.ledger import upload_row_to_wire
        from token_iq.ledger.uploads import BillNotEntered

        row: Final = upload_row_to_wire(BillNotEntered(provider="bedrock"))

        assert row.kind == "not_entered"
        assert not hasattr(row, "total")

    def test_a_missing_bill_names_the_provider_as_a_reader_knows_it(self) -> None:
        from token_iq.api.ledger import upload_row_to_wire
        from token_iq.ledger.uploads import BillNotEntered

        row: Final = upload_row_to_wire(BillNotEntered(provider="bedrock"))

        assert row.display_name == "Amazon Bedrock"

    def test_an_entered_bill_crosses_with_its_exact_digits(self) -> None:
        from token_iq.api.ledger import upload_row_to_wire

        row: Final = upload_row_to_wire(_invoice("48210.07"))

        assert row.kind == "entered"
        assert row.total == "48210.07"

    def test_an_entered_bill_reports_the_period_as_the_days_it_covers(self) -> None:
        from token_iq.api.ledger import upload_row_to_wire

        row: Final = upload_row_to_wire(_invoice("100"))

        assert (row.period_start, row.period_end) == ("2026-09-01", "2026-09-30")

    def test_every_provider_offered_for_a_bill_is_one_the_save_accepts(self) -> None:
        # The form offering a provider the upsert answers with a 404 is a dead end nothing else
        # catches, because both calls succeed on their own terms.
        from token_iq.api.ledger import _known_provider_or_404, provider_options

        for option in provider_options():
            _known_provider_or_404(option.provider)

    def test_every_provider_offered_is_named_in_words(self) -> None:
        from token_iq.api.ledger import provider_options

        for option in provider_options():
            assert option.display_name != ""

    def test_a_configured_address_reaches_the_client(self) -> None:
        from token_iq.api.ledger import forwarding_to_wire
        from token_iq.ledger.invoice_forwarding import ForwardingAddress

        wire: Final = forwarding_to_wire(ForwardingAddress(address="invoices@example.com"))

        assert (wire.kind, wire.address) == ("configured", "invoices@example.com")

    def test_an_unset_address_names_the_setting_to_set(self) -> None:
        from token_iq.api.ledger import forwarding_to_wire
        from token_iq.ledger.invoice_forwarding import NoForwardingAddress

        wire: Final = forwarding_to_wire(NoForwardingAddress(setting="TOKEN_IQ_INVOICE_FORWARDING_ADDRESS"))

        assert (wire.kind, wire.setting) == ("not_configured", "TOKEN_IQ_INVOICE_FORWARDING_ADDRESS")

    def test_an_unusable_address_reaches_the_client_as_its_own_state(self) -> None:
        """Collapsed into "not configured" it would read as nobody having tried, and shown as
        configured it would send a finance team's invoices nowhere."""
        from token_iq.api.ledger import forwarding_to_wire
        from token_iq.ledger.invoice_forwarding import UnusableForwardingAddress

        wire: Final = forwarding_to_wire(
            UnusableForwardingAddress(setting="S", value="invoices", problem="no @.")
        )

        assert (wire.kind, wire.value, wire.problem) == ("unusable", "invoices", "no @.")


class TestTheWindowTheUploadsTabAsksAbout:
    def test_a_window_nobody_passed_is_the_shared_one(self) -> None:
        """The same window the Overview tab's coverage figure uses. Two windows would have the two
        screens disagree about which providers are missing a bill."""
        from token_iq.api.data_quality import DEFAULT_DAYS
        from token_iq.ledger.uploads import INVOICE_WINDOW_DAYS

        assert DEFAULT_DAYS == INVOICE_WINDOW_DAYS


class TestTheLedgerReadsOneComposition:
    """The ledger is the screen closest to the truth layer, so it reads it rather than composing
    its own version. What is asserted here is that moving it changed no figure, and that the one
    rule the layer exists to protect still holds at this boundary."""

    def test_a_provider_fact_becomes_a_line_with_its_owner(self) -> None:
        from token_iq.api.ledger import compose_ledger_lines
        from token_iq.truth.cost_line import Owner, ProviderCostFact, Spend

        fact: Final = ProviderCostFact(
            day=START,
            provider="openrouter",
            credential_name="openrouter-main",
            model="openai/gpt-4o",
            meter="input",
            evidence="reconciled",
            currency="USD",
            amount=Decimal("0.00774700"),
        )
        rule: Final = AttributionRule(
            rule_id="r1",
            provider="openrouter",
            match_type="cloud_account",
            match_value="openrouter-main",
            owner_type="team",
            owner_id="platform-team",
        )

        lines: Final = compose_ledger_lines((fact,), (rule,))

        assert isinstance(lines[0], Spend)
        assert lines[0].facts.owner == Owner(owner_type="team", owner_id="platform-team")
        assert lines[0].facts.amount == Decimal("0.00774700")

    def test_the_ledger_lists_no_gateway_line_however_the_layer_grows(self) -> None:
        """A gateway figure describes the same spend as the provider's, so a ledger listing both
        would double count. This screen passes no gateway rows, which is its own answer to the
        rule rather than a second place the rule is applied."""
        from token_iq.api.ledger import compose_ledger_lines
        from token_iq.truth.cost_line import WhoSpent

        lines: Final = compose_ledger_lines((), ())

        assert not any(isinstance(line, WhoSpent) for line in lines)

    def test_a_line_no_rule_claims_reaches_the_wire_owned_by_nobody(self) -> None:
        from token_iq.api.ledger import _line_response, compose_ledger_lines
        from token_iq.truth.cost_line import ProviderCostFact

        fact: Final = ProviderCostFact(
            day=START,
            provider="openrouter",
            credential_name="nobody-claims-this",
            model=None,
            meter=None,
            evidence="reconciled",
            currency="USD",
            amount=Decimal("1.50"),
        )

        wire: Final = _line_response(compose_ledger_lines((fact,), ())[0])

        assert (wire.owner_type, wire.owner_id) == (None, None)
        assert wire.amount == "1.50"
        assert wire.not_in_total is None
