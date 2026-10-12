"""What the Uploads tab lists, and in what order.

The rows needing action are the bills nobody entered. They are invisible everywhere else:
reconciliation for that month reports no bill rather than a difference, and the Overview tab's
coverage figure says how many are missing without saying which. A list that buried them under
twelve months of entered bills would be a list of the work already done.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

from token_iq.ledger.uploads import BillNotEntered, upload_rows
from token_iq.types.invoice import ProviderInvoice

SEPTEMBER: Final = (datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc))
AUGUST: Final = (datetime(2026, 8, 1, tzinfo=timezone.utc), datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc))


def _invoice(provider: str, period: tuple[datetime, datetime], total: str = "100") -> ProviderInvoice:
    return ProviderInvoice(
        invoice_id=f"{provider}-{period[0].date().isoformat()}",
        provider=provider,
        period_start=period[0],
        period_end=period[1],
        currency="USD",
        total=Decimal(total),
    )


class TestTheRowsNeedingActionComeFirst:
    def test_a_missing_bill_is_listed_above_the_bills_already_entered(self) -> None:
        rows: Final = upload_rows(
            invoices=(_invoice("openrouter", SEPTEMBER), _invoice("anthropic", AUGUST)),
            providers_missing_invoice=("bedrock",),
        )

        assert rows[0] == BillNotEntered(provider="bedrock")

    def test_every_entered_bill_is_still_listed(self) -> None:
        invoices: Final = (_invoice("openrouter", SEPTEMBER), _invoice("anthropic", AUGUST))
        rows: Final = upload_rows(invoices=invoices, providers_missing_invoice=("bedrock",))

        assert tuple(row for row in rows if not isinstance(row, BillNotEntered)) == invoices

    def test_the_order_the_bills_arrived_in_is_kept(self) -> None:
        # The repository returns them newest period first, and re-sorting here would mean two
        # orders to keep in step with each other.
        invoices: Final = (_invoice("openrouter", SEPTEMBER), _invoice("anthropic", AUGUST))
        rows: Final = upload_rows(invoices=invoices, providers_missing_invoice=())

        assert rows == invoices

    def test_several_missing_bills_are_listed_in_a_stable_order(self) -> None:
        # A set from the database has no order of its own, so an unsorted list would reshuffle the
        # top of the table on every reload and make the row somebody was reading move.
        rows: Final = upload_rows(invoices=(), providers_missing_invoice={"openai", "bedrock", "azure"})

        assert rows == (
            BillNotEntered(provider="azure"),
            BillNotEntered(provider="bedrock"),
            BillNotEntered(provider="openai"),
        )


class TestWhatTheTabSaysWhenThereIsNothingToSay:
    def test_nothing_entered_and_nothing_missing_is_an_empty_list(self) -> None:
        assert upload_rows(invoices=(), providers_missing_invoice=()) == ()

    def test_a_provider_with_nothing_missing_produces_no_row_of_its_own(self) -> None:
        rows: Final = upload_rows(invoices=(_invoice("openrouter", SEPTEMBER),), providers_missing_invoice=())

        assert not any(isinstance(row, BillNotEntered) for row in rows)


class TestAProviderCanBeBothAtOnce:
    def test_a_bill_missing_this_month_does_not_hide_last_month_s(self) -> None:
        """Not a contradiction. A provider that billed since the last invoice was entered is
        missing one now and has one for the month before, and collapsing the two would drop
        whichever was judged the duplicate.
        """
        rows: Final = upload_rows(
            invoices=(_invoice("openrouter", AUGUST),),
            providers_missing_invoice=("openrouter",),
        )

        assert rows == (BillNotEntered(provider="openrouter"), _invoice("openrouter", AUGUST))
