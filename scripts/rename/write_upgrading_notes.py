"""Generate the Upgrading section of CHANGELOG.md from the rename map.

Phase 7 asks for a changelog that lists every renamed variable, key and header, generated from the map
rather than typed out. Typed out it would go stale the first time a name moved and nobody would know,
and the thing a customer reads before upgrading is the worst place for a list that has drifted.

    python scripts/rename/write_upgrading_notes.py --check
    python scripts/rename/write_upgrading_notes.py --apply

The section sits between two markers so it can be regenerated in place. `--check` says whether the file
on disk matches the map, which is what a test asserts.
"""

from __future__ import annotations

import argparse
import csv
import io
import pathlib
import sys
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
MAP: Final = REPO / "docs" / "plans" / "rename-map.csv"
CHANGELOG: Final = REPO / "CHANGELOG.md"

BEGIN: Final = "<!-- begin generated: scripts/rename/write_upgrading_notes.py -->"
END: Final = "<!-- end generated -->"


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    check: bool = False


def renamed(kind: str) -> tuple[tuple[str, str], ...]:
    with MAP.open(newline="", encoding="utf-8") as handle:
        return tuple((row["old"], row["new"]) for row in csv.DictReader(handle) if row["kind"] == kind and row["new"])


def table(pairs: Sequence[tuple[str, str]], old_heading: str, new_heading: str) -> str:
    rows: Final = "\n".join(f"| `{old}` | `{new}` |" for old, new in sorted(pairs))
    return f"| {old_heading} | {new_heading} |\n| --- | --- |\n{rows}"


def section() -> str:
    variables: Final = renamed("env var")
    keys: Final = renamed("config key")
    headers: Final = renamed("request header")
    return f"""{BEGIN}

### Upgrading to this release

Nothing to do. Every name below was renamed, and this release reads both spellings, so a running
installation keeps working with the configuration it already has. The release after next stops accepting
the old ones, so treat this as the window to migrate.

The proxy logs a deprecation warning the first time it reads each old name, once per name rather than
once per read, which is also the shortest list of what a particular installation still has to change.

Two things do not move. `model: litellm_proxy/gpt-4o` still names the provider that way, because that is
a value a customer writes rather than a setting. And the names kept for legal and historical reasons stay
put: `LICENSE`, `NOTICE`, this file, and the decision records and plans under `docs/`.

#### Environment variables, {len(variables)} of them

The rule is the prefix and nothing else: `LITELLM_` becomes `TOKEN_IQ_`. The new name wins when both are
set, so an operator who has migrated is not overridden by a variable they forgot to delete.

{table(variables, "Before", "Now")}

Variables the engine does not read are not renamed, including `LITELLM_LICENSE`, which the enterprise
package reads, and `LITELLM_MIGRATION_DIR`, which the migrations package reads.

#### Config keys, {len(keys)} of them

Both spellings are accepted anywhere in `config.yaml`, including inside each entry of `model_list`, and
in a config stored in the database or fetched from S3 or GCS.

{table(keys, "Before", "Now")}

#### Request and response headers, {len(headers)} of them

A request is understood under either spelling. A response carries only the new one, which is what makes
the old one droppable later, so anything reading a response header has to be updated in this window
rather than the next.

{table(headers, "Before", "Now")}

{END}"""


def rewritten(text: str) -> str:
    """The changelog with the generated section replaced, or added under its own heading."""
    if BEGIN in text and END in text:
        before, _, rest = text.partition(BEGIN)
        _, _, after = rest.partition(END)
        return f"{before}{section()}{after}"
    return f"{text.rstrip()}\n\n{section()}\n"


def skeleton() -> str:
    return """# Changelog

This file records what changes between releases, and names the settings an upgrade has to know about.
It keeps the name Token IQ was forked from, which is one of the four places that do; see
`docs/decisions/0023-remove-litellm-names.md`.

## Unreleased

The transition release of the rename. Everything a customer configures now has a Token IQ name, and
every old name still works for one more release.
"""


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the section")
    _ = parser.add_argument("--check", action="store_true", help="say whether the file matches the map")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if options.apply == options.check:
        print("pass exactly one of --apply and --check", file=say)
        return 2

    on_disk: Final = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else skeleton()
    wanted: Final = rewritten(on_disk)

    if options.check:
        if wanted == on_disk:
            print("CHANGELOG.md matches the rename map", file=say)
            return 0
        print("CHANGELOG.md is out of step with the rename map; run with --apply", file=say)
        return 1

    _ = CHANGELOG.write_text(wanted, encoding="utf-8")
    print(f"wrote the Upgrading section to {CHANGELOG.relative_to(REPO).as_posix()}", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
