"""Persistence for provider-reported usage facts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Final, get_args

from litellm.types.proxy.provider_billing import EvidenceLevel, ProviderUsageFact, SummaryRow, TokenTotals

_EVIDENCE_LEVELS: Final[frozenset[str]] = frozenset(get_args(EvidenceLevel))

_SUMMARY_SQL: Final = """
SELECT f.model,
       f.credential_name,
       f.evidence,
       SUM(f.billed_cost::numeric)::text AS billed_cost,
       COUNT(*)                    AS facts
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE f.provider = $1
   AND f.bucket_start >= NOW() - ($2 || ' days')::interval
 GROUP BY f.model, f.credential_name, f.evidence
 ORDER BY 4 DESC
"""

_TOKENS_SQL: Final = """
SELECT COALESCE(SUM(f.input_tokens), 0)::bigint        AS input,
       COALESCE(SUM(f.output_tokens), 0)::bigint       AS output,
       COALESCE(SUM(f.cached_input_tokens), 0)::bigint AS cached_input,
       COALESCE(SUM(f.cache_write_tokens), 0)::bigint  AS cache_write
  FROM "LiteLLM_ProviderUsageFact" f
 WHERE f.provider = $1
   AND f.bucket_start >= NOW() - ($2 || ' days')::interval
"""


def _read(row: object, key: str) -> object:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _count_of(row: object) -> object:
    counted: Final = _read(row, "_count")
    if isinstance(counted, Mapping):
        return counted.get("credential_name") or counted.get("_all")
    return counted


def _bigint(value: object) -> int | None:
    """A whole number, whatever numeric shape the driver decoded it as.

    prisma-client-py decodes SUM(bigint) as a float, the same class of type-changing
    decode that made billed_cost cross as a float before it was cast to text. Relying on
    the SQL cast alone and rejecting anything but a strict int is what turned a real token
    count into a silent zero.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _summary_row_or_none(row: object) -> SummaryRow | None:
    """A row we cannot read is dropped rather than guessed at.

    Defaulting an unreadable cost to zero would understate the customer's bill, which is
    worse than leaving the line out.
    """
    evidence: Final = _read(row, "evidence")
    if evidence not in _EVIDENCE_LEVELS:
        return None
    credential_name: Final = _read(row, "credential_name")
    if not isinstance(credential_name, str):
        return None
    billed_cost: Final = _decimal(_read(row, "billed_cost"))
    if billed_cost is None:
        return None
    facts: Final = _read(row, "facts")
    if not isinstance(facts, int):
        return None
    model: Final = _read(row, "model")
    return SummaryRow(
        model=model if isinstance(model, str) else None,
        credential_name=credential_name,
        evidence=evidence,
        billed_cost=billed_cost,
        facts=facts,
    )


def _row(fact: ProviderUsageFact) -> dict[str, object]:
    """The cost crosses as a string because the column is text and holds exact digits."""
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
        "raw": None if fact.raw is None else dict(fact.raw),
    }


class ProviderUsageFactRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _db(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db attr

    @property
    def _table(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._db.litellm_providerusagefact

    async def upsert_many(self, facts: Sequence[ProviderUsageFact]) -> int:
        """Write facts, overwriting any already stored under the same fact_key."""
        for fact in facts:
            row: Final[Mapping[str, object]] = _row(fact)
            await self._table.upsert(
                where={"fact_key": fact.fact_key},
                data={"create": dict(row), "update": dict(row)},
            )
        return len(facts)

    async def request_ids_already_fetched(self, provider: str, request_ids: Sequence[str]) -> frozenset[str]:
        """Which of these the provider has already priced, so a run can skip them."""
        if not request_ids:
            return frozenset()
        rows: Final = await self._table.find_many(
            where={"provider": provider, "provider_request_id": {"in": list(request_ids)}}
        )
        return frozenset(
            found for row in rows if isinstance(found := getattr(row, "provider_request_id", None), str)
        )

    async def counts_by_credential(self, provider: str) -> Mapping[str, int]:
        """How many facts each account has produced, for deciding whether it has ever worked."""
        rows: Final = await self._table.group_by(by=["credential_name"], where={"provider": provider}, count=True)
        return MappingProxyType(
            {
                name: count
                for row in rows
                if isinstance(name := _read(row, "credential_name"), str)
                and isinstance(count := _count_of(row), int)
            }
        )

    async def summary_rows(self, *, provider: str, days: int) -> tuple[SummaryRow, ...]:
        """Totals by model, account and evidence level over the window, summed in SQL.

        Bounded by the window and grouped in the database: this table grows on every
        scheduler tick, so pulling its rows into Python to sum them would make the cost of
        drawing this screen grow with the customer's entire billing history.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_SUMMARY_SQL, provider, str(days))
        return tuple(row for r in rows if (row := _summary_row_or_none(r)) is not None)

    async def token_totals(self, *, provider: str, days: int) -> TokenTotals:
        """Token counts by type over the window, summed in SQL.

        A column this cannot read defaults to zero rather than dropping the whole result,
        unlike summary_rows: a token count is not money, and failing the entire totals
        block over one mistyped column would also take away the three columns that did
        decode, on the same screen that still shows the correct cost from summary_rows.
        """
        rows: Final[Sequence[Mapping[str, object]]] = await self._db.query_raw(_TOKENS_SQL, provider, str(days))
        row: Final[Mapping[str, object]] = rows[0] if rows else {}
        return TokenTotals(
            input_tokens=_bigint(_read(row, "input")) or 0,
            output_tokens=_bigint(_read(row, "output")) or 0,
            cached_input_tokens=_bigint(_read(row, "cached_input")) or 0,
            cache_write_tokens=_bigint(_read(row, "cache_write")) or 0,
        )
