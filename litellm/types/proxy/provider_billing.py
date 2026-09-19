"""What a provider says our usage cost, in one shape for every provider.

A leaf module on purpose: the connectors, the repository and the read endpoint all need
these names, and anything heavier here would close a circular import between them.

`evidence` is the honest part. Providers answer at different grains and with different
authority, and blending those into one number would hide which figures the provider
asserted and which we derived ourselves.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, TypeAlias

UsageGrain = Literal["request", "day"]

EvidenceLevel = Literal["reconciled", "priced", "allocated"]
"""reconciled: the provider asserted dollars at this scope.
priced: the provider asserted tokens and we applied rates.
allocated: only our own gateway events exist here."""


@dataclass(frozen=True, slots=True)
class ProviderUsageFact:
    fact_key: str
    provider: str
    credential_name: str
    grain: UsageGrain
    bucket_start: datetime
    evidence: EvidenceLevel
    billed_cost: Decimal
    billing_currency: str = "USD"
    provider_request_id: str | None = None
    provider_api_key_id: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None
    raw: Mapping[str, object] | None = None
    fetched_at: datetime | None = None


BillingTokenFactory: TypeAlias = Callable[[str, Mapping[str, str]], Awaitable[str | None]]
"""Given a credential's name and its stored values, the bearer token that reads that provider's
bill, or None when no identity is available. The name is there so a failure can be logged
against the credential an admin would recognise."""


@dataclass(frozen=True, slots=True)
class BillingCredential:
    """One stored credential a connector may read a provider's bill with."""

    name: str
    values: Mapping[str, str]


SyncOutcome = Literal["fetched", "not_configured", "failed"]
"""fetched: the provider answered and whatever it returned was stored.
not_configured: the credential cannot be used, for example it carries no api_key.
failed: the provider refused, rate limited, or the connector raised."""

ConnectionState = Literal["not_connected", "waiting_for_first_data", "healthy", "needs_attention"]
"""What state a provider connection is in, decided only from evidence we hold.

Kept pure and separate from the endpoint so the rules can be read and tested on their own:
every branch here is something a customer will act on."""


@dataclass(frozen=True, slots=True)
class ProviderSyncRun:
    provider: str
    credential_name: str
    started_at: datetime
    finished_at: datetime
    outcome: SyncOutcome
    facts_written: int
    window_start: datetime
    window_end: datetime
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class SummaryRow:
    model: str | None
    credential_name: str
    evidence: EvidenceLevel
    billed_cost: Decimal
    facts: int


@dataclass(frozen=True, slots=True)
class TokenTotals:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int


@dataclass(frozen=True, slots=True)
class RecentFactsPage:
    """One page of `recent_facts`.

    `next_cursor` is read straight off the database's own last row, not off `facts`: a row
    that fails `_fact_or_none` is dropped from `facts` but the database still returned it,
    so a page can be full (and have more rows behind it) even when fewer facts survive than
    were requested. Deciding "was this page full" from `len(facts)` instead would make a
    single unreadable row look identical to the end of the table, truncating everything
    behind it.
    """

    facts: tuple[ProviderUsageFact, ...]
    next_cursor: tuple[datetime, str] | None


@dataclass(frozen=True, slots=True)
class Fetched:
    facts: tuple[ProviderUsageFact, ...]
    watermark: datetime


@dataclass(frozen=True, slots=True)
class NotConfigured:
    reason: str


@dataclass(frozen=True, slots=True)
class FetchFailed:
    reason: str
    retryable: bool


FetchResult = Fetched | NotConfigured | FetchFailed
