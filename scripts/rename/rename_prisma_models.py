"""Rename the 85 Prisma models, and keep every real table exactly where it is.

Phase 8 step 1 changes code names only. `model LiteLLM_TeamTable` becomes `model TeamTable` with
`@@map("LiteLLM_TeamTable")` beside it, so the table in a customer's database is untouched and no
migration runs. Step 2, in a later release and after a rehearsal against a copy, is what moves the tables.

    python scripts/rename/rename_prisma_models.py --audit
    python scripts/rename/rename_prisma_models.py --dry-run
    python scripts/rename/rename_prisma_models.py --apply

A name moves wherever Prisma or a reader treats it as a model: the declaration, the type of a relation
field, and a mention in a comment, which would otherwise name something that no longer exists.

Two things do not move. The string inside `@@map` is the real table, and it is written from the name the
model had rather than carried over, so the one model that already had a map comes out right too. And raw
SQL in the engine stays as it is: 306 queries name `"LiteLLM_SpendLogs"` because that is still what the
table is called, and renaming them here breaks every one on the first request. They belong with the
`ALTER TABLE` migration in step 2.

Field names stay as well. `litellm_budget_table` is a relation field, and a field name is a key in the
API's JSON that the dashboard reads, so it waits for the dashboard to be rebuilt alongside.

The three copies of the schema are byte-identical, which `check-schema-sync.yml` enforces, so all three
are rewritten from the same pass and compared against the root afterwards. `bad_schema.prisma` is a
fixture that is deliberately invalid and is left alone.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import sys
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]

SCHEMAS: Final[tuple[str, ...]] = (
    "schema.prisma",
    "token_iq/gateway/proxy/schema.prisma",
    "token-iq-migrations/token_iq_migrations/schema.prisma",
)

PREFIX: Final = "LiteLLM_"
OLD_DECLARATION: Final = re.compile(r"^model\s+(LiteLLM_\w+)\s*\{", re.MULTILINE)
ANY_DECLARATION: Final = re.compile(r"^model\s+(\w+)\s*\{", re.MULTILINE)
MAPPED: Final = re.compile(r'@@map\("[^"]*"\)')


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    dry_run: bool = False
    audit: bool = False


def models(text: str) -> tuple[str, ...]:
    """Every model the schema declares with the old prefix, in the order it declares them."""
    return tuple(OLD_DECLARATION.findall(text))


def blocks(text: str) -> tuple[tuple[int, int], ...]:
    """Where each model's block starts and ends.

    A block ends at the first `}` at column zero, which is how this file is written throughout and what
    `prisma format` produces.
    """
    return tuple(
        (match.start(), end + 2)
        for match in ANY_DECLARATION.finditer(text)
        for end in (text.find("\n}", match.end()),)
        if end != -1
    )


def with_map(block: str, table: str) -> str:
    """The block with `@@map` naming the real table, written rather than carried over.

    Added as the last line, after any `@@unique` or `@@index`, which is where `prisma format` puts it. A
    blank line goes before it only when the line above is a field rather than another block attribute.
    """
    if MAPPED.search(block):
        return MAPPED.sub(f'@@map("{table}")', block, count=1)
    body, _, close = block.rstrip().rpartition("\n")
    last: Final = next((line for line in reversed(body.split("\n")) if line.strip()), "")
    gap: Final = "" if last.strip().startswith("@@") else "\n"
    return f'{body}\n{gap}  @@map("{table}")\n{close}'


def rewrite(text: str) -> tuple[str, dict[str, int]]:
    """The schema with every model renamed and every table mapped back to where it is."""
    named: Final = models(text)
    if not named:
        return text, {}

    renamed = text  # rebind-ok: one substitution per model name
    for old in sorted(named, key=len, reverse=True):
        renamed = re.sub(rf"\b{re.escape(old)}\b", old.removeprefix(PREFIX), renamed)

    # The declarations are in the same order as before, so each block pairs with the name it had. Spliced
    # back to front so an earlier `@@map` cannot shift a later block's offsets.
    found: Final = blocks(renamed)
    assert len(found) == len(named), f"{len(found)} block(s) for {len(named)} model(s)"
    mapped = renamed  # rebind-ok: one splice per block
    for (start, end), table in reversed(tuple(zip(found, named, strict=True))):
        mapped = mapped[:start] + with_map(mapped[start:end], table) + mapped[end:]

    return mapped, {"models renamed": len(named), "tables mapped": len(MAPPED.findall(mapped))}


def run(*, write: bool) -> tuple[dict[str, dict[str, int]], tuple[str, ...]]:
    """Each schema rewritten, and any copy that did not come out the same as the root."""
    totals: dict[str, dict[str, int]] = {}  # rebind-ok: a tally per file
    written: dict[str, str] = {}  # rebind-ok: what each file became

    for name in SCHEMAS:
        path = REPO / name
        before = path.read_text(encoding="utf-8")
        after, counts = rewrite(before)
        written[name] = after
        if after != before:
            totals[name] = counts
            if write:
                _ = path.write_text(after, encoding="utf-8")

    root: Final = written[SCHEMAS[0]]
    return totals, tuple(name for name, text in written.items() if text != root)


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the schemas")
    _ = parser.add_argument("--dry-run", action="store_true", help="say what would change")
    _ = parser.add_argument("--audit", action="store_true", help="list the models and their tables")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if sum((options.apply, options.dry_run, options.audit)) != 1:
        print("pass exactly one of --apply, --dry-run and --audit", file=say)
        return 2

    if options.audit:
        named: Final = models((REPO / SCHEMAS[0]).read_text(encoding="utf-8"))
        for old in named:
            print(f"{old.removeprefix(PREFIX):<40} stays table {old}", file=say)
        print(f"\n{len(named)} model(s) to rename, 0 table(s) to move", file=say)
        return 0

    totals, differing = run(write=options.apply)
    for name, counts in totals.items():
        print(f"{name}: {counts['models renamed']} renamed, {counts['tables mapped']} mapped", file=say)
    if differing:
        print(f"\nthese came out different from the root schema: {differing}", file=say)
        return 1
    print("\nall three schemas came out identical", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
