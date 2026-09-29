"""Request and response shapes for the Ledger screen.

Every amount crosses as a string. These figures are compared against a bill a person read off a
provider's invoice, and a rounded number would manufacture a discrepancy that does not exist.

The unexplained remainder is a required field, never optional and never omitted when zero. A
screen that showed it only when awkward would let a reader assume its absence meant agreement.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from litellm.ledger.reconciliation import ReconciliationOutcome
from litellm.types.proxy.invoice import AdjustmentKind
from litellm.types.proxy.provider_billing import EvidenceLevel


class AdjustmentBody(BaseModel):
    kind: AdjustmentKind
    amount: str
    note: str | None = None


class InvoiceBody(BaseModel):
    """What an admin sends after reading a bill.

    `kind` is the literal type, so an adjustment nobody can name is refused by validation rather
    than stored and then silently skipped on read.
    """

    provider: str
    period_start: str
    period_end: str
    currency: str = "USD"
    total: str
    adjustments: tuple[AdjustmentBody, ...] = ()
    note: str | None = None


class InvoiceResponse(BaseModel):
    invoice_id: str
    provider: str
    period_start: str
    period_end: str
    currency: str
    total: str
    adjustments: tuple[AdjustmentBody, ...]
    note: str | None


class InvoiceListResponse(BaseModel):
    invoices: tuple[InvoiceResponse, ...]


class InvoiceDeletedResponse(BaseModel):
    deleted: bool


class LedgerLineResponse(BaseModel):
    day: str
    provider: str
    display_name: str
    credential_name: str
    model: str | None
    evidence: EvidenceLevel
    currency: str
    amount: str
    owner_type: str | None
    owner_id: str | None


class LedgerLinesResponse(BaseModel):
    lines: tuple[LedgerLineResponse, ...]
    next_cursor: str | None
    totals_by_currency: Mapping[str, str]


class ReconciliationResponse(BaseModel):
    provider: str
    period_start: str
    period_end: str
    outcome: ReconciliationOutcome
    currency: str | None
    invoice_total: str | None
    ledger_total: str | None
    explained: tuple[AdjustmentBody, ...]
    explained_total: str
    unexplained: str
    note: str
