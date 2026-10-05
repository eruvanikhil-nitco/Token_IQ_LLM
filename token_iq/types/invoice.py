"""A provider bill as an admin entered it, and the things that explain a difference from usage.

Almost no provider publishes invoices through an API, so this is typed information a person read
off a real bill. `total` is exact digits: the amount is compared against a ledger total, and a
rounded bill would manufacture a discrepancy that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

AdjustmentKind = Literal["credit", "discount", "tax", "commitment"]
"""The four reasons a bill legitimately differs from what usage says it should be.

credit: money the provider gave back.
discount: an agreed reduction on list price.
tax: an amount added on top of usage.
commitment: prepaid or reserved capacity drawn down, rather than charged per request."""


@dataclass(frozen=True, slots=True)
class InvoiceAdjustment:
    kind: AdjustmentKind
    amount: Decimal
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderInvoice:
    invoice_id: str
    provider: str
    period_start: datetime
    period_end: datetime
    currency: str
    total: Decimal
    adjustments: tuple[InvoiceAdjustment, ...] = field(default_factory=tuple)
    note: str | None = None
