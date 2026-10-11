"""What the Data Sources > Overview tab reads.

An issue is either counted or declared unmeasurable, and the wire shape keeps those apart rather
than flattening them into a nullable number. A client that received `count: null` would have to
guess whether that meant none or unknown, and on a tab asking "Can the data be trusted?" guessing
towards none is the dangerous direction.
"""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel


class MeasuredIssue(BaseModel):
    kind: Literal["measured"] = "measured"
    key: str
    title: str
    fix_on: str
    count: int


class UnmeasurableIssue(BaseModel):
    kind: Literal["unmeasurable"] = "unmeasurable"
    key: str
    title: str
    fix_on: str
    reason: str
    """Why nobody can answer it yet, which is the part somebody has to act on."""


IssueResponse: TypeAlias = MeasuredIssue | UnmeasurableIssue


class CoveredInvoices(BaseModel):
    kind: Literal["covered"] = "covered"
    providers_billed: int
    providers_invoiced: int


class NothingBilledYet(BaseModel):
    kind: Literal["nothing_billed"] = "nothing_billed"


InvoiceCoverageResponse: TypeAlias = CoveredInvoices | NothingBilledYet
"""Kept apart for the same reason the issue states are.

"0 of 0 invoiced" is a fraction a screen can render as either perfect coverage or total failure, and
a period in which nobody billed is neither.
"""


class DataQualityResponse(BaseModel):
    period_start: str
    period_end: str
    invoice_coverage: InvoiceCoverageResponse
    issues: tuple[IssueResponse, ...]
    issues_to_fix: int
    """How many issues have something to act on. Unmeasurable ones are outside this number, neither
    counted as problems nor as healthy, and the list still carries them so it is not mistaken for
    the whole picture."""
