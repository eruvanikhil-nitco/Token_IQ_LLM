"""One rule mapping a provider account to the team, project or user that owns its spend.

A leaf module on purpose: the repository, the gap calculation and the CRUD endpoint all
need these names, and anything heavier here would close a circular import between them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MatchType = Literal["cloud_account"]
"""cloud_account: the stored credential a fact was fetched with.

One member on purpose. A provider_api_key kind would need `provider_api_key_id`, which no
connector writes today, so a rule of that kind could never match a fact."""

OwnerType = Literal["team", "project", "user"]


@dataclass(frozen=True, slots=True)
class AttributionRule:
    rule_id: str
    provider: str
    match_type: MatchType
    match_value: str
    owner_type: OwnerType
    owner_id: str
    note: str | None = None
