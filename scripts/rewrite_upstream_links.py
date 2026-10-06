"""Make every message stand on its own instead of pointing at upstream's documentation.

Two kinds of reference, handled differently. A message a user reads has to still help after
the link is gone, so the common ones are rewritten by hand through `MAPPED` below. A comment
citing an upstream issue is archaeology: the link goes and whatever the comment said stays.

The hazard is in the stripping, not the mapping. A pattern with `\\s*` around the URL eats
the newline after it and silently merges the following line into the one before, so a
docstring loses its paragraph breaks and a bullet list becomes one line. Nothing fails,
because the file still parses. Every pattern here is therefore anchored to horizontal space
only, never `\\s`.

    python -m scripts.rewrite_upstream_links --check     # what would change
    python -m scripts.rewrite_upstream_links --write
"""

from __future__ import annotations

import argparse
import pathlib
import re
from collections.abc import Sequence
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[1]

UPSTREAM_HOST: Final = r"(?:docs\.litellm\.ai|github\.com/BerriAI|www\.litellm\.ai|models\.litellm\.ai)"
URL: Final = rf"https?://{UPSTREAM_HOST}[^\s\"'`)\],]*"

# Written by hand: each of these is a message somebody reads when something has gone wrong,
# and it has to be useful once the link is gone.
MAPPED: Final[tuple[tuple[str, str], ...]] = (
    (
        rf"Add it here -[ \t]*{URL}",
        "Add it in data/pricing/model_prices.json, or ask your administrator",
    ),
    (rf"Register model, via custom pricing[ \t]*-?[ \t]*{URL}", "Register the model with custom pricing"),
    (rf"See modes here:[ \t]*{URL}", ""),
    (rf"Learn more[ \t]*-[ \t]*{URL}", ""),
    (rf"Get your key[ \t]*-[ \t]*{URL}", ""),
    (rf"Read more[ \t]*-[ \t]*{URL}", ""),
)

# Generic shapes, applied after the mapped ones. Horizontal space only, so a newline is
# never consumed.
GENERIC: Final[tuple[tuple[str, str], ...]] = (
    (rf"[ \t]*\([ \t]*{URL}[ \t]*\)", ""),
    (rf"[ \t]*-[ \t]*{URL}", ""),
    (rf"[ \t]*See[ \t]+{URL}", ""),
    (rf"[ \t]*see[ \t]+{URL}", ""),
    (rf"[ \t]*:[ \t]*{URL}", ""),
    (rf"[ \t]*{URL}", ""),
)

# Upstream's support banner, nine files, six lines plus a signature. Stripping only its URL
# would leave a hollowed-out box; it is somebody else's support channel and goes whole.
BANNER: Final = re.compile(
    r"# \+-+\+\n"
    r"(?:# \|.*\|\n)+"
    r"# \+-+\+\n"
    r"(?:#\n)?"
    r"(?:#[ \t]+Thank you users.*\n)?",
    re.MULTILINE,
)

TIDY: Final[tuple[tuple[str, str], ...]] = (
    # A sentence left with a dangling space before its full stop, or a doubled space.
    (r"[ \t]+\.", "."),
    (r"[ \t]{2,}", " "),
    # A quote left with trailing horizontal space before it closes.
    (r"[ \t]+\"", '"'),
    (r"[ \t]+'", "'"),
)


def rewrite_text(text: str) -> str:
    """Apply the rewrite line by line, leaving every newline and every untouched line alone."""
    if not re.search(UPSTREAM_HOST, text):
        return text
    without_banner: Final = BANNER.sub("", text) if "Give Feedback / Get Help" in text else text
    return "\n".join(_rewrite_line(line) for line in without_banner.split("\n"))


def _rewrite_line(line: str) -> str:
    """Strip the links from one line, and tidy only if that line actually changed.

    Tidying a line the removal never touched is how aligned comments and ASCII-art boxes
    lose their padding. An earlier version did exactly that and rewrote 16,140 lines across
    135 files for 334 URLs, every one of which still parsed, so nothing failed.
    """
    if not re.search(UPSTREAM_HOST, line):
        return line

    stripped: str = line  # rebind-ok: a pipeline of substitutions over one line
    for pattern, replacement in (*MAPPED, *GENERIC):
        stripped = re.sub(pattern, replacement, stripped)
    return _tidy_line(stripped)


def _tidy_line(line: str) -> str:
    """Clean up what the removal left behind, without touching leading indentation."""
    indent: Final = line[: len(line) - len(line.lstrip(" \t"))]
    body: str = line[len(indent) :]  # rebind-ok: a pipeline of substitutions over one line
    for pattern, replacement in TIDY:
        body = re.sub(pattern, replacement, body)
    # A comment reduced to nothing but its marker carried only the link.
    if body.rstrip() in {"#", "#:"}:
        return ""
    return indent + body.rstrip() if body.strip() else indent + body


def rewrite_file(path: pathlib.Path) -> bool:
    original: Final = path.read_text(encoding="utf-8")
    rewritten: Final = rewrite_text(original)
    if rewritten == original:
        return False
    path.write_text(rewritten, encoding="utf-8")
    return True


def targets() -> tuple[pathlib.Path, ...]:
    return tuple(
        p
        for p in (REPO / "litellm").rglob("*.py")
        # Only the built UI bundle is excluded. Excluding every `_experimental` path also
        # skipped token_iq/gateway/proxy/_experimental/mcp_server, which is ordinary source.
        if "out" not in p.parts
        and re.search(UPSTREAM_HOST, p.read_text(encoding="utf-8", errors="ignore"))
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args: Final = parser.parse_args(argv)

    found: Final = targets()
    if not args.write:
        print(f"{len(found)} files reference upstream")
        for path in found[:20]:
            print("  ", path.relative_to(REPO).as_posix())
        return 0

    changed: Final = tuple(p for p in found if rewrite_file(p))
    print(f"rewrote {len(changed)} of {len(found)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
