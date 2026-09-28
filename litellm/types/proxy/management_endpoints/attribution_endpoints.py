"""Request and response shapes for the attribution rule endpoints.

Every amount crosses as a string. A JSON number is a double on the other side, and these
figures are the difference between what a provider billed and what the gateway recorded, so
rounding one in transit would show a customer a discrepancy that does not exist.
"""

from __future__ import annotations

from pydantic import BaseModel

from litellm.attribution.gap_owner import GapState
from litellm.types.proxy.attribution import MatchType, OwnerType


class AttributionRuleBody(BaseModel):
    """What an admin sends to create or reassign a rule.

    `match_type` and `owner_type` are the literal types, so an unknown value is refused by
    validation before anything is written. A rule nobody can interpret would otherwise be
    stored and then silently skipped when the rules are read back, leaving an admin looking
    at spend they believe they have assigned.
    """

    provider: str
    match_type: MatchType
    match_value: str
    owner_type: OwnerType
    owner_id: str
    note: str | None = None


class AttributionRuleResponse(BaseModel):
    rule_id: str
    provider: str
    match_type: MatchType
    match_value: str
    owner_type: OwnerType
    owner_id: str
    note: str | None


class AttributionRuleListResponse(BaseModel):
    rules: tuple[AttributionRuleResponse, ...]


class AttributionRuleDeletedResponse(BaseModel):
    deleted: bool


class UnallocatedLine(BaseModel):
    """One account's spend on one day, and who owns the part that bypassed the gateway."""

    day: str
    provider: str
    credential_name: str
    provider_cost: str | None
    gateway_cost: str
    gap: str
    state: GapState
    owner_type: OwnerType | None
    owner_id: str | None
    rule_id: str | None


class UnallocatedResponse(BaseModel):
    provider: str
    days: int
    total_unallocated: str
    total_owned: str
    lines: tuple[UnallocatedLine, ...]
