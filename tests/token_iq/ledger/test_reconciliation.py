from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

from token_iq.ledger.reconciliation import reconcile
from token_iq.types.invoice import InvoiceAdjustment, ProviderInvoice

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)


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


def test_a_bill_that_matches_the_ledger_once_credits_are_applied_is_balanced() -> None:
    invoice: Final = _invoice("90", adjustments=(InvoiceAdjustment("credit", Decimal("-10")),))
    result: Final = reconcile(invoice=invoice, ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "balanced"
    assert result.unexplained == Decimal(0)
    assert result.explained_total == Decimal("-10")


def test_whatever_no_adjustment_explains_is_reported_not_absorbed() -> None:
    invoice: Final = _invoice("80", adjustments=(InvoiceAdjustment("credit", Decimal("-10")),))
    result: Final = reconcile(invoice=invoice, ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "unexplained_difference"
    assert result.unexplained == Decimal("-10")


def test_a_bill_larger_than_the_ledger_reports_a_positive_remainder() -> None:
    result: Final = reconcile(invoice=_invoice("120"), ledger_totals={"USD": Decimal("100")})
    assert result.unexplained == Decimal("20")


def test_a_bill_smaller_than_the_ledger_reports_a_negative_remainder() -> None:
    result: Final = reconcile(invoice=_invoice("80"), ledger_totals={"USD": Decimal("100")})
    assert result.unexplained == Decimal("-20")


def test_a_bill_in_another_currency_is_refused_rather_than_converted() -> None:
    result: Final = reconcile(invoice=_invoice("90", currency="EUR"), ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "currency_mismatch"
    assert result.unexplained == Decimal(0)
    assert result.currency == "EUR"
    assert result.ledger_total is None


def test_no_invoice_says_so_rather_than_reporting_the_whole_ledger_as_unexplained() -> None:
    result: Final = reconcile(invoice=None, ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "no_invoice"
    assert result.unexplained == Decimal(0)
    assert result.invoice_total is None


def test_a_ledger_with_nothing_in_it_still_reconciles_against_a_bill() -> None:
    result: Final = reconcile(invoice=_invoice("50"), ledger_totals={})
    assert result.outcome == "unexplained_difference"
    assert result.unexplained == Decimal("50")
    assert result.ledger_total == Decimal(0)


def test_every_adjustment_counts_toward_what_is_explained() -> None:
    invoice: Final = _invoice(
        "100",
        adjustments=(
            InvoiceAdjustment("credit", Decimal("-10")),
            InvoiceAdjustment("tax", Decimal("15")),
            InvoiceAdjustment("commitment", Decimal("-5")),
        ),
    )
    result: Final = reconcile(invoice=invoice, ledger_totals={"USD": Decimal("100")})
    assert result.explained_total == Decimal("0")
    assert len(result.explained) == 3


def test_money_never_passes_through_a_float() -> None:
    result: Final = reconcile(invoice=_invoice("0.1"), ledger_totals={"USD": Decimal("0.30000000000000004")})
    assert result.unexplained == Decimal("-0.20000000000000004")


def test_the_ledger_total_for_the_bill_s_own_currency_is_the_one_used() -> None:
    result: Final = reconcile(invoice=_invoice("100"), ledger_totals={"USD": Decimal("100"), "EUR": Decimal("999")})
    assert result.outcome == "balanced"
    assert result.ledger_total == Decimal("100")
