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


class DataQualityResponse(BaseModel):
    period_start: str
    period_end: str
    issues: tuple[IssueResponse, ...]
    issues_to_fix: int
    """How many issues have something to act on. Unmeasurable ones are outside this number, neither
    counted as problems nor as healthy, and the list still carries them so it is not mistaken for
    the whole picture."""
