"""Shape provider usage aggregates into the summary a customer reads.

Kept pure and separate from the endpoint so the arithmetic can be read and tested on its
own, the same reason `connection_state.py` exists. `by_evidence` is the honest part: a
reader needs to know which figures the provider itself asserted (`reconciled`, `priced`)
and which exist only because our own gateway saw the traffic (`allocated`). Collapsing
those into one number would overstate how much of the total is confirmed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from litellm.types.proxy.provider_billing import EvidenceLevel, SummaryRow, TokenTotals

_EVIDENCE_LEVELS: Final[tuple[EvidenceLevel, ...]] = ("reconciled", "priced", "allocated")


@dataclass(frozen=True, slots=True)
class ModelSpend:
    model: str | None
    billed_cost: Decimal
    facts: int


@dataclass(frozen=True, slots=True)
class AccountSpend:
    credential_name: str
    billed_cost: Decimal
    facts: int


@dataclass(frozen=True, slots=True)
class UsageSummary:
    total_cost: Decimal
    by_model: tuple[ModelSpend, ...]
    by_account: tuple[AccountSpend, ...]
    by_evidence: Mapping[EvidenceLevel, Decimal]
    tokens: TokenTotals
    facts: int


def build_usage_summary(rows: Sequence[SummaryRow], tokens: TokenTotals) -> UsageSummary:
    """Fold the per-model-per-account aggregate rows from the repository into one summary.

    A row with `model is None` is a real charge, such as web search or code execution
    billed with no model attached, and is kept as its own labelled entry rather than
    dropped: dropping it would make the breakdown add up to less than the bill.
    """
    models: Final[tuple[str | None, ...]] = tuple({row.model for row in rows})
    by_model: Final = tuple(
        sorted(
            (
                ModelSpend(
                    model=model,
                    billed_cost=sum((row.billed_cost for row in rows if row.model == model), start=Decimal(0)),
                    facts=sum(row.facts for row in rows if row.model == model),
                )
                for model in models
            ),
            key=lambda spend: (-spend.billed_cost, spend.model is None, spend.model or ""),
        )
    )

    accounts: Final[tuple[str, ...]] = tuple({row.credential_name for row in rows})
    by_account: Final = tuple(
        sorted(
            (
                AccountSpend(
                    credential_name=account,
                    billed_cost=sum(
                        (row.billed_cost for row in rows if row.credential_name == account), start=Decimal(0)
                    ),
                    facts=sum(row.facts for row in rows if row.credential_name == account),
                )
                for account in accounts
            ),
            key=lambda spend: (-spend.billed_cost, spend.credential_name),
        )
    )

    by_evidence: Final[Mapping[EvidenceLevel, Decimal]] = MappingProxyType(
        {
            level: sum((row.billed_cost for row in rows if row.evidence == level), start=Decimal(0))
            for level in _EVIDENCE_LEVELS
        }
    )

    return UsageSummary(
        total_cost=sum((row.billed_cost for row in rows), start=Decimal(0)),
        by_model=by_model,
        by_account=by_account,
        by_evidence=by_evidence,
        tokens=tokens,
        facts=sum(row.facts for row in rows),
    )
