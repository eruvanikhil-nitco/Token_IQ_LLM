"""Compare a provider's bill against the cost ledger and account for the difference.

A pure function: no database, no clock. The caller reads the invoice and the ledger totals and
passes them in, which is what lets every branch below be tested directly.

The unexplained remainder is the point of this module. Every other figure here can be
recomputed from the inputs; the remainder is the one that exists to be awkward, and the easiest
way to make a reconciliation screen look finished is to fold it into something else. It is
always reported, with its sign, because a bill larger than the ledger and a bill smaller than it
are different problems for a customer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from litellm.types.proxy.invoice import InvoiceAdjustment, ProviderInvoice

ReconciliationOutcome = Literal["balanced", "unexplained_difference", "currency_mismatch", "no_invoice"]
"""balanced: the bill, its adjustments and the ledger agree exactly.
unexplained_difference: something is left over that no adjustment accounts for.
currency_mismatch: the bill is in a currency the ledger holds nothing in, so no comparison is made.
no_invoice: nobody has entered a bill for this period yet."""


@dataclass(frozen=True, slots=True)
class Reconciliation:
    outcome: ReconciliationOutcome
    currency: str | None
    invoice_total: Decimal | None
    ledger_total: Decimal | None
    explained: tuple[InvoiceAdjustment, ...]
    explained_total: Decimal
    unexplained: Decimal


def _nothing(outcome: ReconciliationOutcome, *, currency: str | None, invoice_total: Decimal | None) -> Reconciliation:
    return Reconciliation(
        outcome=outcome,
        currency=currency,
        invoice_total=invoice_total,
        ledger_total=None,
        explained=(),
        explained_total=Decimal(0),
        unexplained=Decimal(0),
    )


def reconcile(*, invoice: ProviderInvoice | None, ledger_totals: Mapping[str, Decimal]) -> Reconciliation:
    """What the bill says, what the ledger says, and what is left over.

    The order of the checks is the behaviour. No bill at all is reported as such rather than as
    a difference the size of the whole ledger. A bill in a currency the ledger holds nothing in
    is refused rather than converted: a rate nobody chose, applied silently, produces a number
    that looks authoritative and is not.
    """
    if invoice is None:
        return _nothing("no_invoice", currency=None, invoice_total=None)

    if invoice.currency not in ledger_totals and ledger_totals:
        return _nothing("currency_mismatch", currency=invoice.currency, invoice_total=invoice.total)

    ledger_total: Final = ledger_totals.get(invoice.currency, Decimal(0))
    explained_total: Final = sum((a.amount for a in invoice.adjustments), Decimal(0))
    unexplained: Final = invoice.total - explained_total - ledger_total

    return Reconciliation(
        outcome="balanced" if unexplained == 0 else "unexplained_difference",
        currency=invoice.currency,
        invoice_total=invoice.total,
        ledger_total=ledger_total,
        explained=invoice.adjustments,
        explained_total=explained_total,
        unexplained=unexplained,
    )
