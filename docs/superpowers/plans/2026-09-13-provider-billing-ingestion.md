# Provider Billing Ingestion, Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store what providers say a request cost, next to what this gateway recorded, and expose the difference for OpenRouter at per-request granularity.

**Architecture:** One provider-agnostic fact table holds provider-reported usage and cost. A connector per provider translates that provider's API into the fact shape, returning a tagged union rather than raising. A scheduled runner drives every registered connector behind a pod lock so only one replica polls. A read endpoint joins gateway spend rows to facts and reports the delta with an evidence level.

**Tech Stack:** Python 3.12, FastAPI, Prisma/Postgres, APScheduler, pytest. The proxy's own `get_async_httpx_client` for outbound calls.

**Spec:** `docs/superpowers/specs/2026-09-13-provider-billing-ingestion-design.md`

## Global Constraints

- Python max line length is 120.
- All Python work uses `C:\Users\NikhilEruva\litellm\.venv`, never system Python.
- Migrations change schema only. No `UPDATE`, `DELETE`, `MERGE`, or `INSERT ... SELECT`. Enforced by `tests/code_coverage_tests/check_migrations_no_data_rewrites.py`.
- Adding a column to a table means adding it to every archive table that mirrors it, or `/team/delete` and `/key/delete` return 500. Guarded by `TestArchiveDataMatchesTheSchemaItWritesTo` in `tests/test_litellm/repositories/test_repositories.py`.
- After changing `schema.prisma`, regenerate the client: `PATH="/c/Users/NikhilEruva/litellm/.venv/Scripts:$PATH" .venv/Scripts/python.exe -m prisma generate --schema schema.prisma`. The migration alone is not enough; the generated client validates field names.
- No comments except where they explain genuinely complex business logic, or are tool directives, or are a TODO/FIXME with a reason.
- Model failures as values, not exceptions. Tagged unions plus `match`. Annotate every variable `: Final` (LIT010). No mutation, no rebinding parameters (LIT011). Every TypedDict field `ReadOnly` (LIT012).
- No `Any`, no bare `dict`. Every parameter strongly typed.
- Never put a customer or company name in code, commits, or docs.
- Commit after every task. Branch prefix `litellm_`, no `/` in the branch name.
- Never decrypt a stored provider credential to inspect it. Use the API's own copy mechanisms.

---

## File Structure

| File | Responsibility |
|---|---|
| `schema.prisma` | `LiteLLM_ProviderUsageFact` model |
| `litellm-proxy-extras/litellm_proxy_extras/migrations/20260913000000_provider_usage_fact/migration.sql` | Create the table |
| `litellm/types/proxy/provider_billing.py` | Leaf types: grain, evidence level, the fact dataclass, the fetch result union |
| `litellm/provider_billing/__init__.py` | Package marker |
| `litellm/provider_billing/connector.py` | The connector Protocol and the registry |
| `litellm/provider_billing/openrouter.py` | The OpenRouter connector |
| `litellm/provider_billing/runner.py` | Drives connectors, upserts facts |
| `litellm/repositories/provider_usage_fact_repository.py` | Persistence for facts |
| `litellm/proxy/management_endpoints/provider_reconciliation.py` | Read endpoint |
| `litellm/proxy/proxy_server.py` | Register the scheduled job |

Tests mirror the source path under `tests/test_litellm/`.

---

### Task 1: The fact table

**Files:**
- Modify: `schema.prisma`
- Create: `litellm-proxy-extras/litellm_proxy_extras/migrations/20260913000000_provider_usage_fact/migration.sql`
- Test: `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`

**Interfaces:**
- Consumes: nothing
- Produces: table `LiteLLM_ProviderUsageFact` with unique column `fact_key`

- [ ] **Step 1: Add the model to `schema.prisma`**

Place it immediately after `model LiteLLM_CredentialsTable { ... }`:

```prisma
model LiteLLM_ProviderUsageFact {
    id                   String   @id @default(uuid())
    fact_key             String   @unique // connector-computed, makes re-fetching idempotent
    provider             String
    credential_name      String
    grain                String   // request | day
    bucket_start         DateTime
    evidence             String   // reconciled | priced | allocated
    provider_request_id  String?
    provider_api_key_id  String?
    model                String?
    billed_cost          Decimal  @default(0.0)
    billing_currency     String   @default("USD")
    input_tokens         BigInt?
    output_tokens        BigInt?
    cached_input_tokens  BigInt?
    cache_write_tokens   BigInt?
    raw                  Json?
    fetched_at           DateTime @default(now())

    @@index([provider, bucket_start])
    @@index([provider_request_id])
    @@index([credential_name, bucket_start])
}
```

`billed_cost` and `billing_currency` are FOCUS's `BilledCost` and `BillingCurrency`. Keep
them: `litellm/integrations/focus/transformer.py` already emits those columns, and plan 5
will feed this table into it. Today that transformer maps `BilledCost`, `ContractedCost`,
`EffectiveCost`, `ListCost` and `PricingCurrencyEffectiveCost` all from the gateway's own
`spend` estimate, so the export tells CloudZero and Vantage that our estimate is the billed
cost. This table is what will make that claim true. Do not rename these columns.

- [ ] **Step 2: Write the migration**

Create the directory and file with exactly this content:

```sql
-- Provider-reported usage and cost, one row per fact at whatever grain the provider offers.
-- fact_key is connector-computed and unique so a re-fetch overwrites rather than duplicates.
CREATE TABLE IF NOT EXISTS "LiteLLM_ProviderUsageFact" (
    "id"                  TEXT PRIMARY KEY,
    "fact_key"            TEXT NOT NULL,
    "provider"            TEXT NOT NULL,
    "credential_name"     TEXT NOT NULL,
    "grain"               TEXT NOT NULL,
    "bucket_start"        TIMESTAMP(3) NOT NULL,
    "evidence"            TEXT NOT NULL,
    "provider_request_id" TEXT,
    "provider_api_key_id" TEXT,
    "model"               TEXT,
    "billed_cost"         DECIMAL(65,30) NOT NULL DEFAULT 0.0,
    "billing_currency"    TEXT NOT NULL DEFAULT 'USD',
    "input_tokens"        BIGINT,
    "output_tokens"       BIGINT,
    "cached_input_tokens" BIGINT,
    "cache_write_tokens"  BIGINT,
    "raw"                 JSONB,
    "fetched_at"          TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_fact_key_key"
    ON "LiteLLM_ProviderUsageFact"("fact_key");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_provider_bucket_idx"
    ON "LiteLLM_ProviderUsageFact"("provider", "bucket_start");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_request_idx"
    ON "LiteLLM_ProviderUsageFact"("provider_request_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_ProviderUsageFact_credential_bucket_idx"
    ON "LiteLLM_ProviderUsageFact"("credential_name", "bucket_start");
```

- [ ] **Step 3: Verify the migration gate passes**

Run: `.venv/Scripts/python.exe tests/code_coverage_tests/check_migrations_no_data_rewrites.py`
Expected: `No data-rewriting statements in N migrations.`

- [ ] **Step 4: Regenerate the Prisma client**

Run: `PATH="/c/Users/NikhilEruva/litellm/.venv/Scripts:$PATH" .venv/Scripts/python.exe -m prisma generate --schema schema.prisma`
Expected: `Generated Prisma Client Python`

- [ ] **Step 5: Apply the migration locally**

Run:
```bash
docker exec -i tokeniq_db psql -U llmproxy -d litellm < litellm-proxy-extras/litellm_proxy_extras/migrations/20260913000000_provider_usage_fact/migration.sql
```
Expected: `CREATE TABLE` then four `CREATE INDEX`.

- [ ] **Step 6: Commit**

```bash
git add schema.prisma litellm-proxy-extras/litellm_proxy_extras/migrations/20260913000000_provider_usage_fact/
git commit -m "feat(billing): a table for what providers say a request cost"
```

---

### Task 2: The fact and result types

**Files:**
- Create: `litellm/types/proxy/provider_billing.py`
- Test: `tests/test_litellm/types/proxy/test_provider_billing.py`

**Interfaces:**
- Consumes: nothing
- Produces: `UsageGrain`, `EvidenceLevel`, `ProviderUsageFact`, `Fetched`, `NotConfigured`, `FetchFailed`, `FetchResult`

This is a leaf module with no litellm imports, so the connector and the repository can both
depend on it without a circular import. That pattern is already used by
`litellm/types/proxy/team_api_access.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/types/proxy/test_provider_billing.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest


def test_a_fact_is_immutable_because_it_is_an_audit_record():
    """These rows exist to be compared against our own figures later. A fact that can be
    edited after it is fetched is not evidence of anything."""
    from litellm.types.proxy.provider_billing import ProviderUsageFact

    fact = ProviderUsageFact(
        fact_key="openrouter:gen-1",
        provider="openrouter",
        credential_name="acme-openrouter",
        grain="request",
        bucket_start=datetime.now(timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("0.0000025"),
    )

    with pytest.raises(Exception):
        fact.billed_cost = Decimal("99")  # pyright: ignore[reportAttributeAccessIssue]  # proving frozen


def test_cost_is_a_decimal_not_a_float():
    """Token costs run to ten decimal places and get summed across millions of rows.
    Floats lose money here, and the whole point of this table is to be the accurate one."""
    from litellm.types.proxy.provider_billing import ProviderUsageFact

    fact = ProviderUsageFact(
        fact_key="openrouter:gen-2",
        provider="openrouter",
        credential_name="acme-openrouter",
        grain="request",
        bucket_start=datetime.now(timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("0.0000025"),
    )

    assert isinstance(fact.billed_cost, Decimal)


def test_a_failure_is_a_value_a_caller_must_handle():
    """The runner drives many connectors. One provider being down must not end the run,
    which it would if connectors raised."""
    from litellm.types.proxy.provider_billing import FetchFailed, Fetched, NotConfigured

    for result in (
        Fetched(facts=(), watermark=datetime.now(timezone.utc)),
        NotConfigured(reason="no credential named"),
        FetchFailed(reason="429 from provider", retryable=True),
    ):
        assert result is not None


def test_a_retryable_failure_is_distinguishable_from_a_permanent_one():
    """A 429 should be tried again next tick. A 401 should not, and should surface to an
    operator instead of retrying forever against a revoked key."""
    from litellm.types.proxy.provider_billing import FetchFailed

    assert FetchFailed(reason="429", retryable=True).retryable is True
    assert FetchFailed(reason="401 revoked", retryable=False).retryable is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/types/proxy/test_provider_billing.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'litellm.types.proxy.provider_billing'`

- [ ] **Step 3: Write the module**

Create `litellm/types/proxy/provider_billing.py`:

```python
"""What a provider says our usage cost, in one shape for every provider.

A leaf module on purpose: the connectors, the repository and the read endpoint all need
these names, and anything heavier here would close a circular import between them.

`evidence` is the honest part. Providers answer at different grains and with different
authority, and blending those into one number would hide which figures are asserted by the
provider and which we derived ourselves.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/types/proxy/test_provider_billing.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add litellm/types/proxy/provider_billing.py tests/test_litellm/types/proxy/test_provider_billing.py
git commit -m "feat(billing): one shape for every provider's reported usage"
```

---

### Task 3: Persisting facts idempotently

**Files:**
- Create: `litellm/repositories/provider_usage_fact_repository.py`
- Test: `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`

**Interfaces:**
- Consumes: `ProviderUsageFact` from Task 2
- Produces: `ProviderUsageFactRepository(prisma_client)` with
  `async def upsert_many(facts: Sequence[ProviderUsageFact]) -> int` returning the count written,
  and `async def request_ids_already_fetched(provider: str, request_ids: Sequence[str]) -> frozenset[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/repositories/test_provider_usage_fact_repository.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.types.proxy.provider_billing import ProviderUsageFact


def _fact(key: str = "openrouter:gen-1") -> ProviderUsageFact:
    return ProviderUsageFact(
        fact_key=key,
        provider="openrouter",
        credential_name="acme-openrouter",
        grain="request",
        bucket_start=datetime.now(timezone.utc),
        evidence="reconciled",
        billed_cost=Decimal("0.0000025"),
        provider_request_id=key.split(":", 1)[1],
    )


def _client() -> MagicMock:
    client = MagicMock()
    client.db.litellm_providerusagefact.upsert = AsyncMock(return_value=MagicMock())
    client.db.litellm_providerusagefact.find_many = AsyncMock(return_value=[])
    return client


@pytest.mark.asyncio
async def test_refetching_the_same_fact_updates_rather_than_duplicates():
    """Every connector re-reads overlapping windows, because a watermark that never
    overlaps loses anything that landed late. Without an upsert on fact_key that would
    double-count a customer's spend on every tick."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    written = await ProviderUsageFactRepository(client).upsert_many([_fact(), _fact()])

    assert written == 2
    assert client.db.litellm_providerusagefact.upsert.await_count == 2
    for call in client.db.litellm_providerusagefact.upsert.await_args_list:
        assert call.kwargs["where"] == {"fact_key": "openrouter:gen-1"}


@pytest.mark.asyncio
async def test_the_cost_reaches_the_database_as_a_string_not_a_float():
    """Prisma will accept a float and silently round it. These are ten-decimal-place
    figures whose whole purpose is to be more accurate than our own estimate."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    await ProviderUsageFactRepository(client).upsert_many([_fact()])

    created = client.db.litellm_providerusagefact.upsert.await_args_list[0].kwargs["data"]["create"]
    assert isinstance(created["billed_cost"], str)
    assert created["billed_cost"] == "0.0000025"


@pytest.mark.asyncio
async def test_writing_nothing_touches_the_database_not_at_all():
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()

    assert await ProviderUsageFactRepository(client).upsert_many([]) == 0
    client.db.litellm_providerusagefact.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_fetched_requests_are_reported_so_they_can_be_skipped():
    """OpenRouter prices one request per call and rate limits. Re-looking-up a request we
    already priced spends the budget we need for new ones."""
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    client = _client()
    client.db.litellm_providerusagefact.find_many = AsyncMock(
        return_value=[MagicMock(provider_request_id="gen-1")]
    )

    seen = await ProviderUsageFactRepository(client).request_ids_already_fetched(
        provider="openrouter", request_ids=["gen-1", "gen-2"]
    )

    assert seen == frozenset({"gen-1"})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_usage_fact_repository.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the repository**

Create `litellm/repositories/provider_usage_fact_repository.py`:

```python
"""Persistence for provider-reported usage facts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from litellm.types.proxy.provider_billing import ProviderUsageFact


def _row(fact: ProviderUsageFact) -> dict[str, object]:
    """Prisma rounds a float into a Decimal column, so cost crosses as a string."""
    return {
        "fact_key": fact.fact_key,
        "provider": fact.provider,
        "credential_name": fact.credential_name,
        "grain": fact.grain,
        "bucket_start": fact.bucket_start,
        "evidence": fact.evidence,
        "billed_cost": str(fact.billed_cost),
        "billing_currency": fact.billing_currency,
        "provider_request_id": fact.provider_request_id,
        "provider_api_key_id": fact.provider_api_key_id,
        "model": fact.model,
        "input_tokens": fact.input_tokens,
        "output_tokens": fact.output_tokens,
        "cached_input_tokens": fact.cached_input_tokens,
        "cache_write_tokens": fact.cache_write_tokens,
    }


class ProviderUsageFactRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _table(self):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]  # PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db.litellm_providerusagefact  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]

    async def upsert_many(self, facts: Sequence[ProviderUsageFact]) -> int:
        """Write facts, overwriting any already stored under the same fact_key."""
        for fact in facts:
            row: Final[Mapping[str, object]] = _row(fact)
            await self._table.upsert(  # pyright: ignore[reportUnknownMemberType]
                where={"fact_key": fact.fact_key},
                data={"create": dict(row), "update": dict(row)},
            )
        return len(facts)

    async def request_ids_already_fetched(
        self, provider: str, request_ids: Sequence[str]
    ) -> frozenset[str]:
        if not request_ids:
            return frozenset()
        rows: Final = await self._table.find_many(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            where={"provider": provider, "provider_request_id": {"in": list(request_ids)}}
        )
        return frozenset(
            found
            for row in rows  # pyright: ignore[reportUnknownVariableType]
            if isinstance(found := getattr(row, "provider_request_id", None), str)
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/repositories/test_provider_usage_fact_repository.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add litellm/repositories/provider_usage_fact_repository.py tests/test_litellm/repositories/test_provider_usage_fact_repository.py
git commit -m "feat(billing): store provider facts idempotently on a fact key"
```

---

### Task 4: The connector contract and registry

**Files:**
- Create: `litellm/provider_billing/__init__.py`
- Create: `litellm/provider_billing/connector.py`
- Test: `tests/test_litellm/provider_billing/test_connector.py`

**Interfaces:**
- Consumes: `FetchResult` from Task 2
- Produces: `BillingConnector` Protocol with attribute `provider: str` and
  `async def fetch(self, *, since: datetime, until: datetime, credential_name: str, credential_values: Mapping[str, str]) -> FetchResult`;
  plus `register_connector(connector)`, `registered_connectors() -> tuple[BillingConnector, ...]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/provider_billing/test_connector.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

import pytest

from litellm.types.proxy.provider_billing import Fetched, FetchResult


class _Stub:
    provider = "stub"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        return Fetched(facts=(), watermark=until)


def test_a_connector_satisfies_the_protocol_without_inheriting_from_it():
    """Composition over inheritance: a connector is anything with the right shape, so a
    test double is a plain object rather than a subclass of production code."""
    from litellm.provider_billing.connector import BillingConnector

    connector: BillingConnector = _Stub()
    assert connector.provider == "stub"


def test_registering_twice_under_one_provider_is_refused():
    """Two connectors for one provider would both write facts, and the second would
    overwrite the first on every tick. Better to fail at startup than to serve a number
    that flips."""
    from litellm.provider_billing.connector import (
        clear_registry_for_tests,
        register_connector,
    )

    clear_registry_for_tests()
    register_connector(_Stub())
    with pytest.raises(ValueError, match="stub"):
        register_connector(_Stub())
    clear_registry_for_tests()


def test_the_registry_reports_what_was_registered():
    from litellm.provider_billing.connector import (
        clear_registry_for_tests,
        register_connector,
        registered_connectors,
    )

    clear_registry_for_tests()
    register_connector(_Stub())

    assert [c.provider for c in registered_connectors()] == ["stub"]
    clear_registry_for_tests()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_connector.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'litellm.provider_billing'`

- [ ] **Step 3: Write the package and contract**

Create `litellm/provider_billing/__init__.py` containing exactly:

```python
"""Reading what providers say our usage cost, as opposed to what this gateway measured."""
```

Create `litellm/provider_billing/connector.py`:

```python
"""What a provider billing connector is, and which ones exist.

A connector never raises. The runner drives every provider in one pass, and one provider
being down or unconfigured must not stop the others, which is what an exception would do.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final, Protocol, runtime_checkable

from litellm.types.proxy.provider_billing import FetchResult


@runtime_checkable
class BillingConnector(Protocol):
    @property
    def provider(self) -> str: ...

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult: ...


_REGISTRY: Final[dict[str, BillingConnector]] = {}  # mutable-ok: a process-wide registry populated once at import


def register_connector(connector: BillingConnector) -> None:
    if connector.provider in _REGISTRY:
        raise ValueError(f"a billing connector for {connector.provider} is already registered")
    _REGISTRY[connector.provider] = connector


def registered_connectors() -> tuple[BillingConnector, ...]:
    return tuple(_REGISTRY.values())


def clear_registry_for_tests() -> None:
    _REGISTRY.clear()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_connector.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add litellm/provider_billing/ tests/test_litellm/provider_billing/
git commit -m "feat(billing): a connector contract that reports failure as a value"
```

---

### Task 5: The OpenRouter connector

**Files:**
- Create: `litellm/provider_billing/openrouter.py`
- Test: `tests/test_litellm/provider_billing/test_openrouter_connector.py`

**Interfaces:**
- Consumes: `ProviderUsageFact`, `Fetched`, `NotConfigured`, `FetchFailed` from Task 2; `BillingConnector` from Task 4
- Produces: `OpenRouterBillingConnector(unpriced_request_ids, http_client_factory)` with `provider = "openrouter"`.
  `unpriced_request_ids` is `Callable[[], Awaitable[Sequence[str]]]`, injected so the connector never reaches into the database itself.
- Fact key format: `openrouter:{generation_id}`

OpenRouter is the only provider that prices an individual request, via
`GET https://openrouter.ai/api/v1/generation?id=<generation_id>`. Its history window is 30
days. `MAX_LOOKUPS_PER_RUN` caps a run because that endpoint is rate limited per key.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/provider_billing/test_openrouter_connector.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _http(payload: dict, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json = MagicMock(return_value=payload)
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    return client


def _connector(ids: list[str], client: MagicMock):
    from litellm.provider_billing.openrouter import OpenRouterBillingConnector

    async def unpriced() -> list[str]:
        return ids

    return OpenRouterBillingConnector(unpriced_request_ids=unpriced, http_client_factory=lambda: client)


@pytest.mark.asyncio
async def test_a_generation_becomes_a_reconciled_fact():
    """OpenRouter states the dollars for this exact request, which is the strongest
    evidence any provider gives. Recording it as anything less would understate what we
    can prove to a customer."""
    from litellm.types.proxy.provider_billing import Fetched

    client = _http({"data": {"id": "gen-1", "total_cost": 0.0000025, "model": "openai/gpt-4o-mini",
                             "tokens_prompt": 7, "tokens_completion": 4}})
    result = await _connector(["gen-1"], client).fetch(
        since=NOW - timedelta(days=1), until=NOW,
        credential_name="acme-openrouter", credential_values={"api_key": "sk-or-x"},
    )

    assert isinstance(result, Fetched)
    fact = result.facts[0]
    assert fact.fact_key == "openrouter:gen-1"
    assert fact.evidence == "reconciled"
    assert fact.billed_cost == Decimal("0.0000025")
    assert fact.provider_request_id == "gen-1"
    assert fact.model == "openai/gpt-4o-mini"
    assert fact.input_tokens == 7
    assert fact.output_tokens == 4


@pytest.mark.asyncio
async def test_the_cost_survives_as_a_decimal_from_the_json():
    """json.loads gives a float. Converting through str keeps the digits OpenRouter sent
    instead of the nearest binary approximation of them."""
    from litellm.types.proxy.provider_billing import Fetched

    client = _http({"data": {"id": "gen-2", "total_cost": 0.000001234567}})
    result = await _connector(["gen-2"], client).fetch(
        since=NOW - timedelta(days=1), until=NOW,
        credential_name="acme-openrouter", credential_values={"api_key": "sk-or-x"},
    )

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.000001234567")


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from litellm.types.proxy.provider_billing import NotConfigured

    result = await _connector(["gen-1"], _http({})).fetch(
        since=NOW - timedelta(days=1), until=NOW,
        credential_name="acme-openrouter", credential_values={},
    )

    assert isinstance(result, NotConfigured)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retryable_and_a_revoked_key_is_not():
    """Retrying a 429 next tick is correct. Retrying a 401 forever hides a revoked key
    from the operator who needs to replace it."""
    from litellm.types.proxy.provider_billing import FetchFailed

    limited = await _connector(["gen-1"], _http({}, status=429)).fetch(
        since=NOW - timedelta(days=1), until=NOW,
        credential_name="acme-openrouter", credential_values={"api_key": "sk-or-x"},
    )
    revoked = await _connector(["gen-1"], _http({}, status=401)).fetch(
        since=NOW - timedelta(days=1), until=NOW,
        credential_name="acme-openrouter", credential_values={"api_key": "sk-or-x"},
    )

    assert isinstance(limited, FetchFailed) and limited.retryable is True
    assert isinstance(revoked, FetchFailed) and revoked.retryable is False


@pytest.mark.asyncio
async def test_one_run_is_capped_so_it_cannot_exhaust_the_rate_limit():
    """This endpoint prices one request per call. An unbounded run against a backlog would
    burn the customer's rate limit on our polling and degrade their real traffic."""
    from litellm.provider_billing.openrouter import MAX_LOOKUPS_PER_RUN
    from litellm.types.proxy.provider_billing import Fetched

    client = _http({"data": {"id": "gen-x", "total_cost": 0.000001}})
    result = await _connector([f"gen-{i}" for i in range(MAX_LOOKUPS_PER_RUN + 25)], client).fetch(
        since=NOW - timedelta(days=1), until=NOW,
        credential_name="acme-openrouter", credential_values={"api_key": "sk-or-x"},
    )

    assert isinstance(result, Fetched)
    assert client.get.await_count == MAX_LOOKUPS_PER_RUN


@pytest.mark.asyncio
async def test_nothing_to_price_is_a_successful_empty_run():
    from litellm.types.proxy.provider_billing import Fetched

    client = _http({})
    result = await _connector([], client).fetch(
        since=NOW - timedelta(days=1), until=NOW,
        credential_name="acme-openrouter", credential_values={"api_key": "sk-or-x"},
    )

    assert isinstance(result, Fetched)
    assert result.facts == ()
    client.get.assert_not_awaited()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_openrouter_connector.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the connector**

Create `litellm/provider_billing/openrouter.py`:

```python
"""What OpenRouter says one request cost.

The only provider that will price an individual call. Everyone else answers in daily
aggregates, so this is the one place a per-request comparison is possible at all, and the
gateway already stores the generation id it needs as the spend row's request_id.

The window is 30 days. Anything not fetched inside it is gone.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Final

from litellm.types.proxy.provider_billing import (
    FetchFailed,
    Fetched,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

GENERATION_URL: Final = "https://openrouter.ai/api/v1/generation"

MAX_LOOKUPS_PER_RUN: Final = 100
"""One HTTP call prices one request, against a per-key rate limit shared with the
customer's real traffic. A backlog is worked through over several runs rather than in one."""


def _decimal(value: object) -> Decimal | None:
    """json gives a float; str() keeps the digits the provider sent."""
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    return None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) else None


class OpenRouterBillingConnector:
    def __init__(
        self,
        unpriced_request_ids: Callable[[], Awaitable[Sequence[str]]],
        http_client_factory: Callable[[], object],
    ) -> None:
        self._unpriced_request_ids = unpriced_request_ids
        self._http_client_factory = http_client_factory

    @property
    def provider(self) -> str:
        return "openrouter"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        api_key: Final = credential_values.get("api_key")
        if not api_key:
            return NotConfigured(reason=f"credential {credential_name} carries no api_key")

        pending: Final = tuple(await self._unpriced_request_ids())[:MAX_LOOKUPS_PER_RUN]
        if not pending:
            return Fetched(facts=(), watermark=until)

        client: Final = self._http_client_factory()
        headers: Final = {"Authorization": f"Bearer {api_key}"}

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across awaits in a loop
        for generation_id in pending:
            response = await client.get(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
                GENERATION_URL, params={"id": generation_id}, headers=headers
            )
            status = getattr(response, "status_code", 0)
            if status == 429:
                return FetchFailed(reason="openrouter rate limited this key", retryable=True)
            if status in (401, 403):
                return FetchFailed(reason=f"openrouter refused credential {credential_name}", retryable=False)
            if status != 200:
                return FetchFailed(reason=f"openrouter returned {status}", retryable=True)

            payload = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            data = payload.get("data") if isinstance(payload, Mapping) else None
            if not isinstance(data, Mapping):
                continue
            cost = _decimal(data.get("total_cost"))
            if cost is None:
                continue

            facts.append(
                ProviderUsageFact(
                    fact_key=f"openrouter:{generation_id}",
                    provider="openrouter",
                    credential_name=credential_name,
                    grain="request",
                    bucket_start=until,
                    evidence="reconciled",
                    billed_cost=cost,
                    provider_request_id=generation_id,
                    model=_str(data.get("model")),
                    input_tokens=_int(data.get("tokens_prompt")),
                    output_tokens=_int(data.get("tokens_completion")),
                )
            )

        return Fetched(facts=tuple(facts), watermark=until)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_openrouter_connector.py -q`
Expected: `6 passed`

- [ ] **Step 5: Prove the rate cap test has teeth**

Temporarily change `MAX_LOOKUPS_PER_RUN` slicing to `[:]`, re-run, confirm
`test_one_run_is_capped_so_it_cannot_exhaust_the_rate_limit` FAILS, then restore it.

- [ ] **Step 6: Commit**

```bash
git add litellm/provider_billing/openrouter.py tests/test_litellm/provider_billing/test_openrouter_connector.py
git commit -m "feat(billing): read OpenRouter's own price for one request"
```

---

### Task 6: The runner

**Files:**
- Create: `litellm/provider_billing/runner.py`
- Test: `tests/test_litellm/provider_billing/test_runner.py`

**Interfaces:**
- Consumes: `registered_connectors` from Task 4, `ProviderUsageFactRepository` from Task 3
- Produces: `async def run_ingestion(repository, connectors, credentials_for, now) -> IngestionReport`
  where `credentials_for` is `Callable[[str], Awaitable[tuple[str, Mapping[str, str]] | None]]`
  returning credential name and values for a provider, and `IngestionReport` is a frozen
  dataclass with `written: int`, `skipped: tuple[str, ...]`, `failed: tuple[str, ...]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/provider_billing/test_runner.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from litellm.types.proxy.provider_billing import (
    FetchFailed,
    Fetched,
    NotConfigured,
    ProviderUsageFact,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _fact() -> ProviderUsageFact:
    return ProviderUsageFact(
        fact_key="p:1", provider="p", credential_name="c", grain="request",
        bucket_start=NOW, evidence="reconciled", billed_cost=Decimal("1"),
    )


class _Connector:
    def __init__(self, provider: str, result) -> None:
        self._provider = provider
        self._result = result

    @property
    def provider(self) -> str:
        return self._provider

    async def fetch(self, **_: object):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


async def _creds(_provider: str) -> tuple[str, Mapping[str, str]] | None:
    return ("c", {"api_key": "k"})


@pytest.mark.asyncio
async def test_facts_from_every_connector_are_written():
    from litellm.provider_billing.runner import run_ingestion

    repo = MagicMock()
    repo.upsert_many = AsyncMock(return_value=1)

    report = await run_ingestion(
        repository=repo,
        connectors=(_Connector("a", Fetched(facts=(_fact(),), watermark=NOW)),
                    _Connector("b", Fetched(facts=(_fact(),), watermark=NOW))),
        credentials_for=_creds,
        now=NOW,
    )

    assert report.written == 2


@pytest.mark.asyncio
async def test_one_provider_failing_does_not_stop_the_others():
    """The whole point of a shared runner. A customer with five providers should not lose
    four of them because one returned a 500."""
    from litellm.provider_billing.runner import run_ingestion

    repo = MagicMock()
    repo.upsert_many = AsyncMock(return_value=1)

    report = await run_ingestion(
        repository=repo,
        connectors=(_Connector("broken", FetchFailed(reason="500", retryable=True)),
                    _Connector("fine", Fetched(facts=(_fact(),), watermark=NOW))),
        credentials_for=_creds,
        now=NOW,
    )

    assert report.written == 1
    assert report.failed == ("broken",)


@pytest.mark.asyncio
async def test_a_connector_that_raises_anyway_is_contained():
    """Connectors are contracted not to raise, but a bug or an httpx timeout will. One
    unhandled exception must not end the run for every other provider."""
    from litellm.provider_billing.runner import run_ingestion

    repo = MagicMock()
    repo.upsert_many = AsyncMock(return_value=1)

    report = await run_ingestion(
        repository=repo,
        connectors=(_Connector("rude", RuntimeError("boom")),
                    _Connector("fine", Fetched(facts=(_fact(),), watermark=NOW))),
        credentials_for=_creds,
        now=NOW,
    )

    assert report.written == 1
    assert report.failed == ("rude",)


@pytest.mark.asyncio
async def test_a_provider_with_no_credential_is_skipped_quietly():
    """Most customers configure one or two providers. Treating the rest as failures would
    make a healthy run look broken every tick."""
    from litellm.provider_billing.runner import run_ingestion

    repo = MagicMock()
    repo.upsert_many = AsyncMock(return_value=0)

    async def no_creds(_provider: str):
        return None

    report = await run_ingestion(
        repository=repo,
        connectors=(_Connector("a", Fetched(facts=(_fact(),), watermark=NOW)),),
        credentials_for=no_creds,
        now=NOW,
    )

    assert report.skipped == ("a",)
    assert report.failed == ()
    repo.upsert_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_not_configured_result_is_a_skip_not_a_failure():
    from litellm.provider_billing.runner import run_ingestion

    repo = MagicMock()
    repo.upsert_many = AsyncMock(return_value=0)

    report = await run_ingestion(
        repository=repo,
        connectors=(_Connector("a", NotConfigured(reason="no api_key")),),
        credentials_for=_creds,
        now=NOW,
    )

    assert report.skipped == ("a",)
    assert report.failed == ()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_runner.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the runner**

Create `litellm/provider_billing/runner.py`:

```python
"""Drive every registered connector once and record what came back.

A connector is contracted to return failure rather than raise, but a bug or a socket
timeout will raise anyway, so the loop contains that too. The alternative is one provider
ending the run for all of them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from litellm._logging import verbose_proxy_logger
from litellm.provider_billing.connector import BillingConnector
from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository
from litellm.types.proxy.provider_billing import FetchFailed, Fetched, NotConfigured

LOOKBACK: Final = timedelta(days=1)
"""Each run re-reads the last day. A watermark with no overlap loses anything a provider
recorded after we last asked, and the fact key makes the overlap free."""


@dataclass(frozen=True, slots=True)
class IngestionReport:
    written: int
    skipped: tuple[str, ...]
    failed: tuple[str, ...]


async def run_ingestion(
    *,
    repository: ProviderUsageFactRepository,
    connectors: Sequence[BillingConnector],
    credentials_for: Callable[[str], Awaitable[tuple[str, Mapping[str, str]] | None]],
    now: datetime,
) -> IngestionReport:
    written: int = 0  # mutable-ok: accumulated across awaits
    skipped: list[str] = []  # mutable-ok: accumulated across awaits
    failed: list[str] = []  # mutable-ok: accumulated across awaits

    for connector in connectors:
        credential = await credentials_for(connector.provider)
        if credential is None:
            skipped.append(connector.provider)
            continue
        credential_name, credential_values = credential

        try:
            result = await connector.fetch(
                since=now - LOOKBACK,
                until=now,
                credential_name=credential_name,
                credential_values=credential_values,
            )
        except Exception as exc:  # noqa: BLE001  # a connector bug must not end the run for other providers
            verbose_proxy_logger.exception("billing connector %s raised: %s", connector.provider, exc)
            failed.append(connector.provider)
            continue

        match result:
            case Fetched(facts=facts):
                written += await repository.upsert_many(facts)
            case NotConfigured(reason=reason):
                verbose_proxy_logger.debug("billing connector %s skipped: %s", connector.provider, reason)
                skipped.append(connector.provider)
            case FetchFailed(reason=reason, retryable=retryable):
                verbose_proxy_logger.warning(
                    "billing connector %s failed (retryable=%s): %s", connector.provider, retryable, reason
                )
                failed.append(connector.provider)

    return IngestionReport(written=written, skipped=tuple(skipped), failed=tuple(failed))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_runner.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add litellm/provider_billing/runner.py tests/test_litellm/provider_billing/test_runner.py
git commit -m "feat(billing): run every connector without letting one break the rest"
```

---

### Task 7: The reconciliation read

**Files:**
- Create: `litellm/proxy/management_endpoints/provider_reconciliation.py`
- Modify: `litellm/types/proxy/management_endpoints/team_endpoints.py` (append the two response models)
- Test: `tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py`

**Interfaces:**
- Consumes: the fact table from Task 1
- Produces: `GET /provider/reconciliation` returning `ReconciliationResponse` with fields
  `rows: list[ReconciliationRow]`, `our_total: str`, `their_total: str`, `delta: str`,
  `unmatched_our_rows: int`. `ReconciliationRow` has `request_id`, `model`,
  `credential_name`, `our_cost`, `their_cost`, `delta`, `evidence`.
- Costs cross the wire as decimal strings, never floats.

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py`:

```python
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth

ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-admin", user_id="admin")


def _prisma(rows: list[dict]) -> MagicMock:
    client = MagicMock()
    client.db.query_raw = AsyncMock(return_value=rows)
    return client


async def _call(rows: list[dict], caller: UserAPIKeyAuth = ADMIN):
    from litellm.proxy.management_endpoints.provider_reconciliation import provider_reconciliation

    with patch("litellm.proxy.proxy_server.prisma_client", _prisma(rows)):
        return await provider_reconciliation(provider="openrouter", days=7, user_api_key_dict=caller)


@pytest.mark.asyncio
async def test_the_delta_is_what_the_page_exists_to_show():
    """Two totals side by side is a report. The difference between them is the product."""
    result = await _call([
        {"request_id": "gen-1", "model": "openai/gpt-4o-mini", "credential_name": "acme",
         "our_cost": Decimal("0.0000030"), "their_cost": Decimal("0.0000025"), "evidence": "reconciled"},
    ])

    assert result.rows[0].delta == "0.0000005"
    assert result.delta == "0.0000005"


@pytest.mark.asyncio
async def test_costs_cross_the_wire_as_strings():
    """A ten-decimal-place figure serialised as a JSON float arrives at the dashboard
    already rounded, which would make the gateway look wrong about its own number."""
    result = await _call([
        {"request_id": "gen-1", "model": "m", "credential_name": "acme",
         "our_cost": Decimal("0.000001234567"), "their_cost": Decimal("0.000001234567"),
         "evidence": "reconciled"},
    ])

    assert result.rows[0].our_cost == "0.000001234567"
    assert isinstance(result.our_total, str)


@pytest.mark.asyncio
async def test_a_request_the_provider_has_not_priced_yet_is_counted_not_hidden():
    """A row we have and they have not is either a backlog we have not polled or spend
    they never billed. Dropping it would hide both."""
    result = await _call([
        {"request_id": "gen-1", "model": "m", "credential_name": "acme",
         "our_cost": Decimal("0.000003"), "their_cost": None, "evidence": "allocated"},
    ])

    assert result.unmatched_our_rows == 1
    assert result.rows[0].their_cost is None
    assert result.rows[0].evidence == "allocated"


@pytest.mark.asyncio
async def test_an_unmatched_row_does_not_pollute_their_total():
    """Treating a missing provider figure as zero would report a fictitious saving."""
    result = await _call([
        {"request_id": "gen-1", "model": "m", "credential_name": "acme",
         "our_cost": Decimal("0.000003"), "their_cost": None, "evidence": "allocated"},
        {"request_id": "gen-2", "model": "m", "credential_name": "acme",
         "our_cost": Decimal("0.000002"), "their_cost": Decimal("0.000002"), "evidence": "reconciled"},
    ])

    assert result.their_total == "0.000002"
    assert result.our_total == "0.000005"


@pytest.mark.asyncio
async def test_only_an_admin_may_read_it():
    """This names every provider account and what it was charged, across all teams."""
    from fastapi import HTTPException

    member = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-u", user_id="u")
    with pytest.raises(HTTPException) as exc:
        await _call([], caller=member)

    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Append the response models**

Append to `litellm/types/proxy/management_endpoints/team_endpoints.py`:

```python
class ReconciliationRow(BaseModel):
    """One request, priced twice"""

    request_id: str
    model: str | None
    credential_name: str
    our_cost: str
    their_cost: str | None
    delta: str | None
    evidence: str


class ReconciliationResponse(BaseModel):
    """What we recorded against what the provider charged, over a window"""

    provider: str
    rows: list[ReconciliationRow]
    our_total: str
    their_total: str
    delta: str
    unmatched_our_rows: int
    """Requests we recorded that the provider has not priced. Either a polling backlog or
    spend the provider never billed us for."""
```

- [ ] **Step 4: Write the endpoint**

Create `litellm/proxy/management_endpoints/provider_reconciliation.py`:

```python
"""What we recorded against what the provider charged.

Only the rows the provider has actually priced count toward their total. Treating a
missing provider figure as zero would report a saving that does not exist, so those rows
are counted separately and shown rather than dropped.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final

import fastapi
from fastapi import APIRouter, Depends, HTTPException, status

from litellm.proxy._types import CommonProxyErrors, LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.types.proxy.management_endpoints.team_endpoints import (
    ReconciliationResponse,
    ReconciliationRow,
)

router: Final = APIRouter()

_SQL: Final = """
SELECT s.request_id,
       s.model,
       COALESCE(s.provider_credential, '') AS credential_name,
       s.spend::numeric      AS our_cost,
       f.billed_cost         AS their_cost,
       COALESCE(f.evidence, 'allocated') AS evidence
  FROM "LiteLLM_SpendLogs" s
  LEFT JOIN "LiteLLM_ProviderUsageFact" f
         ON f.provider_request_id = s.request_id
        AND f.provider = $1
 WHERE s.custom_llm_provider = $1
   AND s."startTime" >= NOW() - ($2 || ' days')::interval
 ORDER BY s."startTime" DESC
 LIMIT 1000
"""


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    return None


@router.get(
    "/provider/reconciliation",
    tags=["provider billing"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=ReconciliationResponse,
)
async def provider_reconciliation(
    provider: str = fastapi.Query(description="Which provider to reconcile, for example openrouter"),
    days: int = fastapi.Query(default=7, ge=1, le=31),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> ReconciliationResponse:
    """Every request in the window, priced by us and by the provider, with the difference."""
    from litellm.proxy.proxy_server import prisma_client

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Only a proxy admin may read cross-team provider reconciliation."},
        )
    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    raw: Final[Sequence[Mapping[str, object]]] = await prisma_client.db.query_raw(_SQL, provider, str(days))

    rows: Final = tuple(
        (
            str(row.get("request_id") or ""),
            row.get("model") if isinstance(row.get("model"), str) else None,
            str(row.get("credential_name") or ""),
            _decimal(row.get("our_cost")) or Decimal(0),
            _decimal(row.get("their_cost")),
            str(row.get("evidence") or "allocated"),
        )
        for row in raw
    )

    our_total: Final = sum((ours for _, _, _, ours, _, _ in rows), Decimal(0))
    their_total: Final = sum((theirs for *_, theirs, _ in rows if theirs is not None), Decimal(0))

    return ReconciliationResponse(
        provider=provider,
        rows=[
            ReconciliationRow(
                request_id=request_id,
                model=model,
                credential_name=credential_name,
                our_cost=str(ours),
                their_cost=None if theirs is None else str(theirs),
                delta=None if theirs is None else str(ours - theirs),
                evidence=evidence,
            )
            for request_id, model, credential_name, ours, theirs, evidence in rows
        ],
        our_total=str(our_total),
        their_total=str(their_total),
        delta=str(our_total - their_total),
        unmatched_our_rows=sum(1 for *_, theirs, _ in rows if theirs is None),
    )
```

- [ ] **Step 5: Register the router**

In `litellm/proxy/proxy_server.py`, find the block of `app.include_router(...)` calls near
the bottom of the module and add, following the surrounding style:

```python
app.include_router(provider_reconciliation_router)
```

with the import beside the other management endpoint router imports:

```python
from litellm.proxy.management_endpoints.provider_reconciliation import (
    router as provider_reconciliation_router,
)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -q`
Expected: `5 passed`

- [ ] **Step 7: Prove the admin check has teeth**

Comment out the `user_role != PROXY_ADMIN` block, re-run, confirm
`test_only_an_admin_may_read_it` FAILS, then restore it.

- [ ] **Step 8: Commit**

```bash
git add litellm/proxy/management_endpoints/provider_reconciliation.py litellm/types/proxy/management_endpoints/team_endpoints.py litellm/proxy/proxy_server.py tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py
git commit -m "feat(billing): report our figure against the provider's, per request"
```

---

### Task 8: Wire it into the running proxy and prove it

**Files:**
- Modify: `litellm/proxy/proxy_server.py` (register the scheduled job near the other `scheduler.add_job` calls, around line 9308)
- Test: `tests/test_litellm/provider_billing/test_scheduled_registration.py`

**Interfaces:**
- Consumes: everything above
- Produces: job id `provider_billing_ingestion_job` on a 300 second interval

- [ ] **Step 1: Write the failing test**

Create `tests/test_litellm/provider_billing/test_scheduled_registration.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_only_one_replica_polls_the_provider():
    """Every replica running this would multiply the customer's provider rate-limit
    consumption by the replica count, and OpenRouter's per-request endpoint is the tightest
    limit we touch."""
    from litellm.provider_billing.scheduled import ingest_provider_billing

    lock = MagicMock()
    lock.redis_cache = MagicMock()
    lock.acquire_lock = AsyncMock(return_value=False)
    lock.release_lock = AsyncMock()
    ran = MagicMock()

    await ingest_provider_billing(pod_lock_manager=lock, run=ran, now=datetime.now(timezone.utc))

    ran.assert_not_called()


@pytest.mark.asyncio
async def test_the_lock_is_released_even_when_the_run_fails():
    """A lock held by a crashed run would stop ingestion until the next restart, and the
    customer would see stale provider figures with no error to explain it."""
    from litellm.provider_billing.scheduled import ingest_provider_billing

    lock = MagicMock()
    lock.redis_cache = MagicMock()
    lock.acquire_lock = AsyncMock(return_value=True)
    lock.release_lock = AsyncMock()

    async def boom(**_: object):
        raise RuntimeError("boom")

    await ingest_provider_billing(pod_lock_manager=lock, run=boom, now=datetime.now(timezone.utc))

    lock.release_lock.assert_awaited()


@pytest.mark.asyncio
async def test_without_redis_a_single_process_still_ingests():
    """A self-hosted single-replica customer has no redis. Requiring a lock would mean
    they never ingest anything at all."""
    from litellm.provider_billing.scheduled import ingest_provider_billing

    lock = MagicMock()
    lock.redis_cache = None
    ran = AsyncMock()

    await ingest_provider_billing(pod_lock_manager=lock, run=ran, now=datetime.now(timezone.utc))

    ran.assert_awaited()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_scheduled_registration.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write the scheduled wrapper**

Create `litellm/provider_billing/scheduled.py`:

```python
"""One replica polls; the rest stand down.

Polling from every replica multiplies the customer's provider rate-limit consumption by
the replica count. A deployment without redis has nothing to coordinate through and is
assumed to be a single process, which is the common self-hosted case.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Final

from litellm._logging import verbose_proxy_logger

LOCK_ID: Final = "provider_billing_ingestion"


async def ingest_provider_billing(
    *,
    pod_lock_manager: object,
    run: Callable[..., Awaitable[object]],
    now: datetime,
) -> None:
    redis_cache: Final = getattr(pod_lock_manager, "redis_cache", None)
    if redis_cache is None:
        await run(now=now)
        return

    acquired: Final = await pod_lock_manager.acquire_lock(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        cronjob_id=LOCK_ID
    )
    if not acquired:
        return
    try:
        await run(now=now)
    except Exception as exc:  # noqa: BLE001  # a failed run must not keep the lock and stall every later tick
        verbose_proxy_logger.exception("provider billing ingestion failed: %s", exc)
    finally:
        await pod_lock_manager.release_lock(cronjob_id=LOCK_ID)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/test_scheduled_registration.py -q`
Expected: `3 passed`

- [ ] **Step 5: Register the job**

In `litellm/proxy/proxy_server.py`, immediately after the `### PROXY WORKER HEARTBEAT ###`
block that calls `scheduler.add_job(worker_heartbeat.beat, ...)` around line 9308, add:

```python
        ### PROVIDER BILLING INGESTION ###
        scheduler.add_job(
            build_provider_billing_job(prisma_client=prisma_client, proxy_logging_obj=proxy_logging_obj),
            "interval",
            seconds=300,
            id="provider_billing_ingestion_job",
            replace_existing=True,
            misfire_grace_time=APSCHEDULER_MISFIRE_GRACE_TIME,
        )
```

Add `build_provider_billing_job` to `litellm/provider_billing/scheduled.py`, which composes
the repository, the registered connectors, and a credential lookup that reads
`LiteLLM_CredentialsTable` rows whose `credential_info` carries `{"purpose": "billing_ingestion"}`:

```python
def build_provider_billing_job(
    *, prisma_client: object, proxy_logging_obj: object
) -> Callable[[], Awaitable[None]]:
    from datetime import datetime, timezone

    from litellm.provider_billing.connector import registered_connectors
    from litellm.provider_billing.runner import run_ingestion
    from litellm.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

    repository: Final = ProviderUsageFactRepository(prisma_client)

    async def credentials_for(provider: str) -> tuple[str, Mapping[str, str]] | None:
        rows = await prisma_client.db.litellm_credentialstable.find_many(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            where={"credential_info": {"path": ["purpose"], "equals": "billing_ingestion"}}
        )
        for row in rows:  # pyright: ignore[reportUnknownVariableType]
            info = getattr(row, "credential_info", None)
            if isinstance(info, Mapping) and info.get("provider") == provider:
                values = getattr(row, "credential_values", None)
                if isinstance(values, Mapping):
                    return (str(getattr(row, "credential_name", "")), {k: str(v) for k, v in values.items()})
        return None

    async def job() -> None:
        await ingest_provider_billing(
            pod_lock_manager=getattr(
                getattr(proxy_logging_obj, "db_spend_update_writer", None), "pod_lock_manager", None
            ),
            run=lambda now: run_ingestion(
                repository=repository,
                connectors=registered_connectors(),
                credentials_for=credentials_for,
                now=now,
            ),
            now=datetime.now(timezone.utc),
        )

    return job
```

Add the import beside the other proxy imports:

```python
from litellm.provider_billing.scheduled import build_provider_billing_job
```

- [ ] **Step 6: Register the OpenRouter connector at startup**

In the same block, before `scheduler.add_job`, add:

```python
        register_connector(
            OpenRouterBillingConnector(
                unpriced_request_ids=build_unpriced_openrouter_lookup(prisma_client),
                http_client_factory=lambda: get_async_httpx_client(
                    llm_provider=httpxSpecialProvider.LoggingCallback
                ),
            )
        )
```

Add `build_unpriced_openrouter_lookup` to `litellm/provider_billing/openrouter.py`:

```python
def build_unpriced_openrouter_lookup(prisma_client: object) -> Callable[[], Awaitable[Sequence[str]]]:
    """Generation ids this gateway recorded that no fact has priced yet, newest first.

    Newest first because OpenRouter drops history after 30 days: given a backlog, the rows
    about to expire are worth less than the ones a customer is looking at today, and the
    old ones will still be there next run while the recent ones will not.
    """

    async def unpriced() -> Sequence[str]:
        rows = await prisma_client.db.query_raw(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            """
            SELECT s.request_id
              FROM "LiteLLM_SpendLogs" s
              LEFT JOIN "LiteLLM_ProviderUsageFact" f
                     ON f.provider_request_id = s.request_id AND f.provider = 'openrouter'
             WHERE s.custom_llm_provider = 'openrouter'
               AND s.request_id LIKE 'gen-%'
               AND f.id IS NULL
               AND s."startTime" >= NOW() - INTERVAL '29 days'
             ORDER BY s."startTime" DESC
             LIMIT 500
            """
        )
        return tuple(str(row["request_id"]) for row in rows if row.get("request_id"))

    return unpriced
```

- [ ] **Step 7: Run every suite this touched**

Run:
```bash
.venv/Scripts/python.exe -m pytest tests/test_litellm/provider_billing/ tests/test_litellm/repositories/ tests/test_litellm/types/proxy/ tests/test_litellm/proxy/management_endpoints/test_provider_reconciliation.py -q -p no:randomly --timeout=300
```
Expected: all pass.

- [ ] **Step 8: Prove it against the live proxy**

The repo requires proof from a real running instance, not a test run.

```bash
# 1. Restart with the new code
bash ~/.claude/scripts/litellm-dev-up.sh

# 2. Register the OpenRouter key as an ingestion credential, copied from the
#    existing deployment so no plaintext key is handled
curl -s -X POST -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"credential_name":"openrouter-billing","model_id":"<the openrouter deployment model_id>",
       "credential_info":{"purpose":"billing_ingestion","provider":"openrouter"}}' \
  http://127.0.0.1:4001/credentials

# 3. Send a real request so there is something to reconcile
curl -s -X POST -H "Authorization: Bearer $A_TEAM_KEY" -H "Content-Type: application/json" \
  -d '{"model":"openrouter/openai/gpt-4o-mini","messages":[{"role":"user","content":"say ok"}],"max_tokens":5}' \
  http://127.0.0.1:4001/v1/chat/completions

# 4. Wait for one ingestion tick (300s), or restart to trigger the first run

# 5. Read the reconciliation
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  "http://127.0.0.1:4001/provider/reconciliation?provider=openrouter&days=7" | python -m json.tool
```

Expected: rows with both `our_cost` and `their_cost` populated, `evidence: "reconciled"`,
and a `delta` that is small but very likely non-zero. Record the actual output in the
commit message. A delta of exactly zero on every row means the join is matching a row
against itself; check that `their_cost` is genuinely coming from the fact table.

- [ ] **Step 9: Commit**

```bash
git add litellm/provider_billing/scheduled.py litellm/provider_billing/openrouter.py litellm/proxy/proxy_server.py tests/test_litellm/provider_billing/test_scheduled_registration.py
git commit -m "feat(billing): poll OpenRouter on a schedule from one replica"
```

---

## Self-review notes

**Spec coverage.** The spec's decisions map to tasks as follows: reconciliation-as-product
is Task 7; gateway number stays operational is enforced by Task 7 never writing to
`LiteLLM_SpendLogs`; evidence levels are Tasks 2, 5 and 7; OpenRouter first is Task 5; poll
and store is Tasks 1, 3 and 6; FOCUS column names are Task 1 (`billed_cost`,
`billing_currency`); credential reuse is Task 8. The spec's out-of-scope list is respected:
nothing here rewrites a spend row.

**Not covered by this plan, by design.** Anthropic, OpenAI and the cloud-billing family are
plans 2 and 3. There is no UI in this phase; the endpoint is the deliverable, and screens
come with plan 4 once there is more than one provider to show.

**Prior art checked.** `litellm/integrations/focus/`, `litellm/integrations/cloudzero/` and
`litellm/integrations/vantage/` already exist and all push data outward. Nothing in this
codebase currently pulls billing data in, so nothing here duplicates existing work. The
FOCUS schema in `litellm/integrations/focus/schema.py` is the naming authority for any
column added to the fact table later.

**Known risk.** The `credentials_for` lookup in Task 8 reads the encrypted credential store
and hands values to a connector. Confirm during Task 8 that Prisma returns decrypted values
for `credential_values`, and if it does not, use the same accessor the pass-through router
uses (`CredentialAccessor.get_credential_values`) rather than decrypting anything by hand.
