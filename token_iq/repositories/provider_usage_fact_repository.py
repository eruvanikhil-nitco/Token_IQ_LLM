"""Persistence for provider-reported usage facts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Final, get_args

from litellm.types.proxy.provider_billing import (
    EvidenceLevel,
    ProviderUsageFact,
    RecentFactsPage,
    SummaryRow,
    TokenTotals,
    UsageGrain,
)

_EVIDENCE_LEVELS: Final[frozenset[str]] = frozenset(get_args(EvidenceLevel))
_GRAINS: Final[frozenset[str]] = frozenset(get_args(UsageGrain))

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
 ORDER BY SUM(f.billed_cost::numeric) DESC
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


def _recent_facts_where(
    provider: str, before: datetime | None, before_fact_key: str | None
) -> Mapping[str, object]:
    """The `where` clause for `recent_facts`.

    bucket_start alone is not unique (see `recent_facts`), so once a caller carries a
    fact_key forward the filter has to become an OR across two conditions rather than a
    single comparison. Every dict literal below is `mutable-ok`: prisma-client-py serialises
    this filter with `json.dumps` and has no encoder for `mappingproxy` (verified live:
    `TypeError: Type <class 'mappingproxy'> not serializable`), and Prisma's own filter
    syntax for a condition is a plain dict, so no immutable container can stand in for one.
    The `OR` value itself is a tuple, not a list: prisma accepts it (`json.dumps` serialises
    a tuple as a JSON array, verified live) and it needs no suppression.
    """
    if before is None:
        return {"provider": provider}  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
    lt_before: Final = {"lt": before}  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
    if before_fact_key is None:
        return {  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
            "provider": provider,
            "bucket_start": lt_before,
        }
    return {  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
        "provider": provider,
        "OR": (
            {"bucket_start": lt_before},  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
            {  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
                "bucket_start": before,
                "fact_key": {"lt": before_fact_key},  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
            },
        ),
    }


def _fact_or_none(row: object) -> ProviderUsageFact | None:
    """A row we cannot read is dropped rather than guessed at.

    Raw Data exists to show exactly what the provider said, so a corrupted or partial row
    must disappear from the page rather than render with fabricated fields.
    """
    fact_key: Final = _read(row, "fact_key")
    provider: Final = _read(row, "provider")
    credential_name: Final = _read(row, "credential_name")
    if not isinstance(fact_key, str) or not isinstance(provider, str) or not isinstance(credential_name, str):
        return None
    grain: Final = _read(row, "grain")
    if grain not in _GRAINS:
        return None
    bucket_start: Final = _read(row, "bucket_start")
    if not isinstance(bucket_start, datetime):
        return None
    evidence: Final = _read(row, "evidence")
    if evidence not in _EVIDENCE_LEVELS:
        return None
    billed_cost: Final = _decimal(_read(row, "billed_cost"))
    if billed_cost is None:
        return None
    billing_currency: Final = _read(row, "billing_currency")
    if not isinstance(billing_currency, str):
        return None
    fetched_at: Final = _read(row, "fetched_at")
    if not isinstance(fetched_at, datetime):
        return None
    raw: Final = _read(row, "raw")
    if raw is not None and not isinstance(raw, Mapping):
        return None
    model: Final = _read(row, "model")
    provider_request_id: Final = _read(row, "provider_request_id")
    provider_api_key_id: Final = _read(row, "provider_api_key_id")
    return ProviderUsageFact(
        fact_key=fact_key,
        provider=provider,
        credential_name=credential_name,
        grain=grain,
        bucket_start=bucket_start,
        evidence=evidence,
        billed_cost=billed_cost,
        billing_currency=billing_currency,
        provider_request_id=provider_request_id if isinstance(provider_request_id, str) else None,
        provider_api_key_id=provider_api_key_id if isinstance(provider_api_key_id, str) else None,
        model=model if isinstance(model, str) else None,
        input_tokens=_bigint(_read(row, "input_tokens")),
        output_tokens=_bigint(_read(row, "output_tokens")),
        cached_input_tokens=_bigint(_read(row, "cached_input_tokens")),
        cache_write_tokens=_bigint(_read(row, "cache_write_tokens")),
        raw=MappingProxyType(dict(raw)) if raw is not None else None,
        fetched_at=fetched_at,
    )


def _cursor_from_row(row: object) -> tuple[datetime, str] | None:
    """The (bucket_start, fact_key) pair a page's cursor resumes from, read straight off
    the raw row rather than off a parsed `ProviderUsageFact`.

    bucket_start and fact_key are this table's two NOT NULL columns, so a row some other
    field disqualifies from `_fact_or_none` almost always still yields a safe place to
    resume. Reading them independently means one corrupt evidence value or a bad cost
    string can never take the cursor down with it.
    """
    bucket_start: Final = _read(row, "bucket_start")
    fact_key: Final = _read(row, "fact_key")
    if isinstance(bucket_start, datetime) and isinstance(fact_key, str):
        return bucket_start, fact_key
    return None


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

    async def recent_facts(
        self, *, provider: str, limit: int, before: datetime | None, before_fact_key: str | None = None
    ) -> RecentFactsPage:
        """The newest facts for one provider, keyset-paged on bucket_start with fact_key as a tiebreaker.

        bucket_start alone is not unique: every fact one connector run fetches shares that
        run's watermark, and every day-grain fact shares its calendar day. A page boundary
        that falls inside such a group and then filters strictly on ``bucket_start`` alone
        would exclude every row at that exact value forever, including ones the earlier page
        never returned. Ordering and filtering on ``(bucket_start, fact_key)`` together, with
        fact_key unique, gives every row a place in one total order, so a caller that carries
        the fact_key half of a cursor forward never loses or repeats a row across pages.

        Whether the page was full is decided from how many rows the database returned, not
        from how many survived `_fact_or_none`: a row can fail that check and still count
        toward a full page, and the cursor has to reflect the database's position, not the
        parser's.
        """
        where: Final = _recent_facts_where(provider, before, before_fact_key)
        order: Final = (
            {"bucket_start": "desc"},  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
            {"fact_key": "desc"},  # mutable-ok: prisma json.dumps() has no mappingproxy encoder
        )
        rows: Final = await self._table.find_many(where=where, order=order, take=limit)
        facts: Final = tuple(fact for row in rows if (fact := _fact_or_none(row)) is not None)
        next_cursor: Final = _cursor_from_row(rows[-1]) if len(rows) == limit and rows else None
        return RecentFactsPage(facts=facts, next_cursor=next_cursor)
