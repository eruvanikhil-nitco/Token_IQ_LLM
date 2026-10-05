"""Propose upstream's price changes as a reviewed pull request.

This is the only thing in the repository that fetches from upstream, and it runs in CI, not
in an installation. A running proxy reads `data/pricing/model_prices.json` and nothing else.

The split exists because the two kinds of change carry different risk. A model that did not
exist yesterday cannot make an existing bill wrong, so an addition merges itself once the
tests pass. A price that moved changes what the product says somebody already spent, so a
person reads it. A model upstream dropped is never deleted here, because the months it was
in use still have to price.

    python -m scripts.update_model_prices                 # the daily run
    python -m scripts.update_model_prices --model gpt-4o  # one model, same review
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[1]
PRICES: Final = REPO / "data" / "pricing" / "model_prices.json"
IN_USE: Final = REPO / "data" / "pricing" / "models_in_use.txt"

UPSTREAM_URL: Final = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)

# Only money needs a reviewer. A changed mode, a new alias or a context window moving does
# not change what anybody was charged.
PRICE_FIELD_MARKERS: Final[tuple[str, ...]] = ("cost_per", "_cost")

FLAG_LARGE: Final = "large"
FLAG_TO_ZERO: Final = "to_zero"
FLAG_IN_USE: Final = "in_use"

LARGE_CHANGE_RATIO: Final = Decimal("0.5")

# Upstream shipping a tiny file is a broken fetch, not a price change. Merging it would
# unprice most of the product in one commit.
MIN_PLAUSIBLE_RATIO: Final = Decimal("0.5")

RESERVED_KEYS: Final[frozenset[str]] = frozenset({"sample_spec", "fallback_generalizations"})


@dataclasses.dataclass(frozen=True, slots=True)
class Addition:
    model: str


@dataclasses.dataclass(frozen=True, slots=True)
class Change:
    model: str
    provider: str
    field: str
    old: Decimal
    new: Decimal
    flags: frozenset[str]


@dataclasses.dataclass(frozen=True, slots=True)
class Removal:
    model: str
    action: str = "retire"
    """Never "delete". A model retired upstream still prices the months it was in use."""


@dataclasses.dataclass(frozen=True, slots=True)
class Diff:
    additions: tuple[Addition, ...]
    changes: tuple[Change, ...]
    removals: tuple[Removal, ...]

    @property
    def can_auto_merge(self) -> bool:
        """Additions only. Anything that moves or removes a price is read by a person."""
        return not self.changes and not self.removals


def _is_price_field(name: str) -> bool:
    return any(marker in name for marker in PRICE_FIELD_MARKERS)


def _as_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return None


def _models(payload: Mapping[str, object]) -> Mapping[str, Mapping[str, object]]:
    return {
        name: entry
        for name, entry in payload.items()
        if name not in RESERVED_KEYS and isinstance(entry, Mapping)
    }


def _flags_for(old: Decimal, new: Decimal, model: str, in_use: frozenset[str]) -> frozenset[str]:
    flags: Final[set[str]] = set()  # mutable-ok: assembled for one comparison
    if new == 0:
        flags.add(FLAG_TO_ZERO)
    elif old != 0 and abs(new - old) / abs(old) > LARGE_CHANGE_RATIO:
        flags.add(FLAG_LARGE)
    if model in in_use:
        flags.add(FLAG_IN_USE)
    return frozenset(flags)


def classify(
    current: Mapping[str, object],
    upstream: Mapping[str, object],
    in_use: frozenset[str] = frozenset(),
) -> Diff:
    """What changed between the bundled list and upstream's."""
    if not isinstance(upstream, Mapping) or not isinstance(current, Mapping):
        raise ValueError("both price maps must be objects")

    ours: Final = _models(current)
    theirs: Final = _models(upstream)

    if ours and len(theirs) < len(ours) * MIN_PLAUSIBLE_RATIO:
        raise ValueError(
            f"upstream has {len(theirs)} models against our {len(ours)}; refusing a fetch that lost most of the file"
        )

    additions: Final = tuple(Addition(model=name) for name in sorted(theirs.keys() - ours.keys()))
    removals: Final = tuple(Removal(model=name) for name in sorted(ours.keys() - theirs.keys()))

    changes: Final[list[Change]] = []  # mutable-ok: accumulated over one comparison
    for name in sorted(ours.keys() & theirs.keys()):
        mine, upstream_entry = ours[name], theirs[name]
        for field in sorted(set(mine) | set(upstream_entry)):
            if not _is_price_field(field):
                continue
            old, new = _as_decimal(mine.get(field)), _as_decimal(upstream_entry.get(field))
            if new is None or old == new:
                continue
            before: Final = old if old is not None else Decimal(0)
            changes.append(
                Change(
                    model=name,
                    provider=str(upstream_entry.get("litellm_provider", "")),
                    field=field,
                    old=before,
                    new=new,
                    flags=_flags_for(before, new, name, in_use),
                )
            )

    return Diff(additions=additions, changes=tuple(changes), removals=removals)


def history_lines(diff: Diff, effective_from: str, source: str, approved_by: str) -> tuple[str, ...]:
    """One line per price that moved. Additions have no old price, so they record nothing."""
    from datetime import date

    from token_iq.pricing.history import PriceChange

    return tuple(
        PriceChange(
            model=change.model,
            provider=change.provider,
            field=change.field,
            old=change.old,
            new=change.new,
            effective_from=date.fromisoformat(effective_from),
            source=source,
            approved_by=approved_by,
        ).as_line()
        for change in diff.changes
    )


def load_in_use(path: pathlib.Path | None = None) -> frozenset[str]:
    target: Final = path if path is not None else IN_USE
    if not target.exists():
        return frozenset()
    return frozenset(
        line.strip() for line in target.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def fetch_upstream(url: str = UPSTREAM_URL) -> Mapping[str, object]:
    """The one network call in this repository, and it never runs in an installation."""
    import httpx

    response: Final = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def render_report(diff: Diff) -> str:
    lines: Final = [
        f"{len(diff.additions)} additions, {len(diff.changes)} changes, {len(diff.removals)} removals",
        f"auto-merge: {'yes' if diff.can_auto_merge else 'no, a person reads this'}",
    ]
    for change in diff.changes:
        marks = f"  [{', '.join(sorted(change.flags))}]" if change.flags else ""
        lines.append(f"  {change.model} {change.field}: {change.old} -> {change.new}{marks}")
    for removal in diff.removals:
        lines.append(f"  {removal.model}: {removal.action}, never deleted")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None, help="only consider this model")
    parser.add_argument("--url", default=UPSTREAM_URL)
    parser.add_argument("--write", action="store_true", help="apply additions and append history")
    parser.add_argument("--effective-from", default=None)
    parser.add_argument("--approved-by", default="price-update-job")
    args: Final = parser.parse_args(argv)

    current: Final = json.loads(PRICES.read_text(encoding="utf-8"))
    upstream: Final = fetch_upstream(args.url)
    narrowed: Final = (
        {k: v for k, v in upstream.items() if k == args.model or k in RESERVED_KEYS}
        if args.model
        else upstream
    )
    reference: Final = (
        {k: v for k, v in current.items() if k == args.model or k in RESERVED_KEYS}
        if args.model
        else current
    )

    diff: Final = classify(current=reference, upstream=narrowed, in_use=load_in_use())
    print(render_report(diff))

    if not args.write:
        return 0

    from datetime import datetime, timezone

    from token_iq.pricing.history import append_changes, parse_history

    effective: Final = args.effective_from or datetime.now(timezone.utc).date().isoformat()
    lines: Final = history_lines(diff, effective_from=effective, source=args.url, approved_by=args.approved_by)
    if lines:
        append_changes(parse_history(lines))

    merged: Final = {**current, **{a.model: upstream[a.model] for a in diff.additions}}
    PRICES.write_text(json.dumps(merged, indent=4, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(diff.additions)} additions and {len(lines)} history lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
