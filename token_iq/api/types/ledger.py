"""Request and response shapes for the Ledger screen.

Every amount crosses as a string. These figures are compared against a bill a person read off a
provider's invoice, and a rounded number would manufacture a discrepancy that does not exist.

The unexplained remainder is a required field, never optional and never omitted when zero. A
screen that showed it only when awkward would let a reader assume its absence meant agreement.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, TypeAlias

from pydantic import BaseModel

from token_iq.ledger.reconciliation import ReconciliationOutcome
from token_iq.types.invoice import AdjustmentKind
from token_iq.types.provider_billing import EvidenceLevel


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
    evidence: EvidenceLevel | None
    """What the figure rests on, or null for a line nobody asserted.

    The grades describe what a provider said. A seat or an entered invoice is a figure a person
    read off a contract, so claiming a grade for one would be a claim about evidence that does not
    exist. Null rather than a fourth grade, because the three are the provider's own vocabulary.
    """

    currency: str
    amount: str
    owner_type: str | None
    owner_id: str | None
    not_in_total: str | None = None
    """Why this line is not money, for a line that says who spent money counted elsewhere.

    Null for ordinary spend. A reader looking at a figure that is missing from the total above it
    would otherwise have to guess whether the total or the line was wrong.
    """


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


class ForwardingConfigured(BaseModel):
    kind: Literal["configured"] = "configured"
    address: str


class ForwardingNotConfigured(BaseModel):
    kind: Literal["not_configured"] = "not_configured"
    setting: str


class ForwardingUnusable(BaseModel):
    """Somebody set an address and it cannot receive mail.

    Its own state rather than a blank. Shown as though it worked, a typo sends a finance team's
    invoices nowhere and nothing says so until a month-end close has nothing to reconcile.
    """

    kind: Literal["unusable"] = "unusable"
    setting: str
    value: str
    problem: str


InvoiceForwardingResponse: TypeAlias = ForwardingConfigured | ForwardingNotConfigured | ForwardingUnusable


class EnteredBillRow(BaseModel):
    kind: Literal["entered"] = "entered"
    invoice_id: str
    provider: str
    display_name: str
    period_start: str
    period_end: str
    currency: str
    total: str
    note: str | None


class BillNotEnteredRow(BaseModel):
    """A provider that billed in the window with no invoice covering it.

    No total, and not an optional one. There is no bill, so the only figure available would be the
    ledger's own, and a figure Token IQ worked out sitting in an invoice column is how a provider
    total and an attribution total get added together by accident.
    """

    kind: Literal["not_entered"] = "not_entered"
    provider: str
    display_name: str


UploadRowResponse: TypeAlias = EnteredBillRow | BillNotEnteredRow


class ProviderOption(BaseModel):
    """A provider a bill may be entered for: exactly the set the upsert accepts."""

    provider: str
    display_name: str


class UploadsResponse(BaseModel):
    checked_from: str
    checked_to: str
    forwarding: InvoiceForwardingResponse
    providers: tuple[ProviderOption, ...]
    rows: tuple[UploadRowResponse, ...]
