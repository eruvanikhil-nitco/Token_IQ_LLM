"""What a model cost on a given day.

The bundled price list says what a model costs now. Re-pricing a closed month at today's
prices produces a figure that still looks like a figure, so the error is invisible: the
ledger reconciles, the Savings Simulator answers, and the number is wrong.

The history is an append-only record of accepted changes, shipped with the code beside the
prices it describes. It is reference data, not an installation's own data, so it is read into
memory at import rather than into a table: a migration would add a schema to maintain, a
backfill to get right and a divergence between installations, and buy nothing, because every
installation of a given release has exactly the same history.

The live gateway prices at the current rate. Only the ledger, the Savings Simulator and any
re-pricing of a past period look backwards.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Final

HISTORY_PATH: Final = pathlib.Path(__file__).resolve().parents[2] / "data" / "pricing" / "price_history.jsonl"

REQUIRED: Final[tuple[str, ...]] = (
    "model",
    "provider",
    "field",
    "old",
    "new",
    "effective_from",
    "source",
    "approved_by",
)


@dataclasses.dataclass(frozen=True, slots=True)
class PriceChange:
    """One accepted change to one field of one model's price."""

    model: str
    provider: str
    field: str
    old: Decimal
    new: Decimal
    effective_from: date
    source: str
    """Where it came from: an upstream commit, or "manual"."""
    approved_by: str

    def as_line(self) -> str:
        return json.dumps(
            {
                "model": self.model,
                "provider": self.provider,
                "field": self.field,
                "old": str(self.old),
                "new": str(self.new),
                "effective_from": self.effective_from.isoformat(),
                "source": self.source,
                "approved_by": self.approved_by,
            },
            sort_keys=True,
        )


def _change_from(payload: Mapping[str, object], where: str) -> PriceChange:
    missing: Final = tuple(name for name in REQUIRED if name not in payload)
    if missing:
        raise ValueError(f"{where}: price change is missing {', '.join(missing)}")
    return PriceChange(
        model=str(payload["model"]),
        provider=str(payload["provider"]),
        field=str(payload["field"]),
        # Decimal from the string as written. A price that cannot survive a float round trip
        # is exactly the kind this has to carry.
        old=Decimal(str(payload["old"])),
        new=Decimal(str(payload["new"])),
        effective_from=date.fromisoformat(str(payload["effective_from"])),
        source=str(payload["source"]),
        approved_by=str(payload["approved_by"]),
    )


def parse_history(lines: Iterable[str]) -> tuple[PriceChange, ...]:
    """Every change in the given lines, blank lines ignored, a bad line refused.

    Skipping a malformed line would turn a price change into one that quietly never
    happened, which is the failure this whole module exists to prevent.
    """
    parsed: Final[list[PriceChange]] = []  # mutable-ok: accumulated over one pass
    for number, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(f"price history line {number} is not JSON: {error}") from error
        if not isinstance(payload, Mapping):
            raise ValueError(f"price history line {number} is not an object")
        parsed.append(_change_from(payload, f"price history line {number}"))
    return tuple(parsed)


@dataclasses.dataclass(frozen=True, slots=True)
class PriceHistory:
    changes: tuple[PriceChange, ...]

    @classmethod
    def from_lines(cls, lines: Iterable[str]) -> PriceHistory:
        return cls(changes=parse_history(lines))

    def price_on(self, model: str, field: str, when: date) -> Decimal | None:
        """The price in effect on `when`, or None when this field has no recorded history.

        None means "ask the current price list", never "free". A caller that treats an
        absent history as zero turns real spend into free usage.
        """
        relevant: Final = sorted(
            (c for c in self.changes if c.model == model and c.field == field),
            key=lambda c: c.effective_from,
        )
        if not relevant:
            return None

        applied: Final = [c for c in relevant if c.effective_from <= when]
        # Before the first recorded change, the price was that change's "old" value.
        return applied[-1].new if applied else relevant[0].old


def load_history(path: pathlib.Path | None = None) -> PriceHistory:
    target: Final = path if path is not None else HISTORY_PATH
    if not target.exists():
        return PriceHistory(changes=())
    return PriceHistory.from_lines(target.read_text(encoding="utf-8").splitlines())


def append_changes(changes: Sequence[PriceChange], path: pathlib.Path | None = None) -> None:
    """Append accepted changes. Append-only: a recorded price is never edited or removed,
    because a month already reported was priced with it."""
    target: Final = path if path is not None else HISTORY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        for change in changes:
            handle.write(change.as_line() + "\n")


def price_as_of(
    model: str,
    field: str,
    when: date,
    history: PriceHistory | None = None,
) -> Decimal | None:
    """What `model`'s `field` cost on `when`.

    History first, because it knows about days the current list has forgotten. The current
    list second, for fields that have never changed. None when neither knows, which the
    caller must not read as zero.
    """
    recorded: Final = (history if history is not None else load_history()).price_on(model, field, when)
    if recorded is not None:
        return recorded

    from litellm.litellm_core_utils.get_model_cost_map import load_bundled_prices

    entry: Final = load_bundled_prices().get(model)
    if not isinstance(entry, Mapping):
        return None
    current: Final = entry.get(field)
    return None if current is None else Decimal(str(current))
