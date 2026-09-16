"""Persistence for provider-reported usage facts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from litellm.types.proxy.provider_billing import ProviderUsageFact


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
    def _table(self) -> Any:  # any-ok: PrismaClient is an untyped runtime wrapper
        return self._prisma_client.db.litellm_providerusagefact  # pyright: ignore[reportAttributeAccessIssue]

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
