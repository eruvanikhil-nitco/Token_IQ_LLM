"""Request and response shapes for the Combined usage views.

Every amount crosses as a string. These figures are differences between two bills, so a JSON
number would round them into a discrepancy nobody can explain.

The gateway figure and the provider figure are always carried side by side and never summed.
That is the counting rule: the provider says how much was spent, the gateway says who spent it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from litellm.types.proxy.attribution import OwnerType

ComparisonStatus = Literal["matched", "gap", "not_settled", "no_provider_data"]
"""matched: the gateway recorded at least what the provider billed.
gap: the provider charged more than the gateway saw, whether or not a rule claims it.
not_settled: the provider has not finished billing this day.
no_provider_data: the provider has reported nothing for this day, so no comparison is possible."""


class ComparisonDay(BaseModel):
    day: str
    provider: str
    display_name: str
    credential_name: str
    gateway_cost: str
    provider_cost: str | None
    gap: str
    status: ComparisonStatus
    owner_type: OwnerType | None
    owner_id: str | None


class ComparisonResponse(BaseModel):
    days: int
    rows: tuple[ComparisonDay, ...]
    total_gateway: str
    total_provider: str
    total_gap: str
