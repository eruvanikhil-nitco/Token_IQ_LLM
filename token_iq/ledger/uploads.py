"""What Data Sources > Uploads lists: the bills entered, and the bills that are missing.

The missing ones are the whole point of the tab. A bill nobody entered is invisible everywhere
else: reconciliation for that month reports no bill rather than a difference, and the Overview
tab's coverage figure says how many are missing without saying which. So they are listed first,
because they are the only rows on the tab anybody has to act on.

A missing row carries no total. There is no bill, so any figure beside it could only be the
ledger's own, and a gateway or connector figure printed in an invoice column is exactly how a
provider total and an attribution total get added together by accident.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Sequence
from typing import Final, TypeAlias

from token_iq.types.invoice import ProviderInvoice

INVOICE_WINDOW_DAYS: Final = 30
"""How far back the tab looks for a provider that billed with no invoice covering it.

Long enough that a monthly bill has had a chance to arrive. The same window the Overview tab's
coverage figure uses, so the two screens cannot disagree about which providers are missing one.
"""


@dataclasses.dataclass(frozen=True, slots=True)
class BillNotEntered:
    provider: str


UploadRow: TypeAlias = ProviderInvoice | BillNotEntered


def upload_rows(
    *,
    invoices: Sequence[ProviderInvoice],
    providers_missing_invoice: Collection[str],
) -> tuple[UploadRow, ...]:
    """Every row the tab shows, the ones needing action first.

    A provider can appear twice: missing for the period just billed and entered for the month
    before. That is not a contradiction, and collapsing the two would hide whichever one was
    dropped.
    """
    missing: Final = tuple(BillNotEntered(provider=provider) for provider in sorted(providers_missing_invoice))
    return missing + tuple(invoices)
