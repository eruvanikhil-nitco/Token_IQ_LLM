"""Remove dashboard links that point at another product's documentation.

Token IQ has no documentation site. These links went to LiteLLM's, for features Token IQ is
deliberately diverging from and will rename in phases 7 to 9, so following one would take a
customer somewhere that describes a different product. A link to someone else's docs is
worse than no link, and gets worse as the rename proceeds.

Whole elements go, not just their URLs. An anchor whose text reads "Learn more" means
nothing without its destination, and an `<a>` with no `href` is worse than no anchor at all.

    python -m scripts.remove_ui_doc_links --check
    python -m scripts.remove_ui_doc_links --write
"""

from __future__ import annotations

import argparse
import pathlib
import re
from collections.abc import Sequence
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[1]
UI: Final = REPO / "ui" / "litellm-dashboard" / "src"

DOCS_HOST: Final = r"https://docs\.litellm\.ai[^\"']*"

# A JSX element wrapping a documentation link, with the `{" "}` spacer that usually precedes
# it. Non-greedy so it stops at the first closing tag, and the tag name is captured so the
# opener and closer must agree.
ELEMENT: Final = re.compile(
    r'(?:\{"\s*"\}\s*)?'
    # Only a literal documentation URL. An earlier version also allowed href={anything},
    # which matched every expression href and gutted the generic HelpLink component itself.
    rf'<(a|HelpLink)\s+[^>]*href="{DOCS_HOST}"[^>]*>'
    r".*?"
    r"</\1>",
    re.DOTALL,
)

# An anchor passed as a prop value is the whole prop's reason to exist, so the prop goes
# with it. Removing only the element leaves `render={}`, which is not valid JSX.
PROP_VALUED: Final = re.compile(
    # The prop may sit on its own line or inline after another one. Requiring a leading
    # newline missed the inline form and left `render={}` in two test files, which the
    # build never caught because it does not compile tests.
    rf'[ \t]*\n?[ \t]*\w+=\{{<(?:a|HelpLink)\s+[^>]*href="{DOCS_HOST}"[^>]*/>\}}'
)

# The same thing written across several lines, where the anchor has children. Removing only
# the element leaves `render={` and a bare `}`, which is the same invalid JSX.
PROP_VALUED_BLOCK: Final = re.compile(
    rf'\n[ \t]*\w+=\{{\s*<(a|HelpLink)\s+[^>]*href="{DOCS_HOST}"[^>]*>.*?</\1>\s*\}}',
    re.DOTALL,
)

# A self-closing one, which carries its text in a prop rather than children.
SELF_CLOSING: Final = re.compile(rf'(?:\{{"\s*"\}}\s*)?<(?:a|HelpLink)\s+[^>]*href="{DOCS_HOST}"[^>]*/>')

# Leftovers the removal can create: a spacer with nothing after it before a closing tag, and
# a line of pure whitespace where an element used to be.
DANGLING_SPACER: Final = re.compile(r'\{"\s*"\}(\s*)(?=</)')


def remove_links(text: str) -> str:
    if "docs.litellm.ai" not in text:
        return text
    stripped: Final = PROP_VALUED_BLOCK.sub("", PROP_VALUED.sub("", text))
    without: Final = ELEMENT.sub("", SELF_CLOSING.sub("", stripped))
    tidied: Final = DANGLING_SPACER.sub(r"\1", without)
    # Collapse a line left holding only whitespace between two tags, without touching
    # indentation anywhere else.
    return re.sub(r"\n[ \t]+\n(?=[ \t]*</)", "\n", tidied)


def targets() -> tuple[pathlib.Path, ...]:
    return tuple(
        p
        for p in UI.rglob("*")
        if p.suffix in {".tsx", ".ts"} and p.is_file() and "docs.litellm.ai" in p.read_text(encoding="utf-8", errors="ignore")
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args: Final = parser.parse_args(argv)

    found: Final = targets()
    if not args.write:
        print(f"{len(found)} files carry a documentation link")
        return 0

    changed: Final[list[str]] = []  # mutable-ok: accumulated over one pass
    remaining: Final[list[str]] = []  # mutable-ok: accumulated over one pass
    for path in found:
        original = path.read_text(encoding="utf-8")
        rewritten = remove_links(original)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")
            changed.append(path.relative_to(REPO).as_posix())
        if "docs.litellm.ai" in rewritten:
            remaining.append(path.relative_to(REPO).as_posix())

    print(f"rewrote {len(changed)} of {len(found)} files")
    if remaining:
        print(f"{len(remaining)} still hold a reference, for hand review:")
        for name in remaining:
            print("  ", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
