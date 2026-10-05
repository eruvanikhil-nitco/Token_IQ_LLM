"""Repair the tests the price consolidation left behind.

The price list used to exist twice: `model_prices_and_context_window.json` at the repository root
and `litellm/model_prices_and_context_window_backup.json` beside the package. Both were replaced
by one file, `data/pricing/model_prices.json`, and
`tests/test_litellm/litellm_core_utils/test_get_model_cost_map.py::test_the_bundled_file_is_the_only_copy`
is the test that keeps it that way. The tests that read the old paths were not updated, so 88 test
files refer to files that do not exist. Five of them fail at collection, which truncates whatever
pytest was collecting after them.

Three kinds of repair, and only the first two are mechanical:

- a path built to either old file becomes a path to the one that exists
- a test function that exists solely to assert the two copies agree is removed. Not a judgement
  about its value: with one copy there is nothing for it to compare, and the decision that there
  is one copy is already taken and already tested
- a test that loops over both copies to check a flag in each needs its loop to cover one file.
  Those are listed and left alone, because collapsing a loop is a change to what the test asserts

Run with `--dry-run` first. It prints what it would do and touches nothing.

## What a first attempt got wrong, measured

**The right replacement depends on what each path's base is, and this script does not know it.**
Applying it and running the tests moved 27 failures to 21 and 14 errors to 2, then two further
attempts to widen its rule made things worse, peaking at 108 failures, and the whole thing was
reverted. Three distinct reasons, all of them the base:

- `"model_prices_and_context_window_backup.json"`, 38 occurrences, resolves against the *package*
  directory via `os.path.dirname(litellm.__file__)`. Replacing just the filename yields
  `litellm/data/pricing/model_prices.json`, which does not exist
- `"../../model_prices_and_context_window.json"`, 15 occurrences, resolves against the *repository
  root* from a test two directories down. A rule that rewrites the whole quoted string loses the
  `../../` and points at the wrong place
- the filename also appears as a function's default argument value and inside tuples of
  filenames, which a rule keyed on `open`/`Path`/`join` appearing on the same line cannot see

The seven distinct forms and their counts, measured after reverting:

    75  "model_prices_and_context_window.json"
    38  "model_prices_and_context_window_backup.json"
    15  "../../model_prices_and_context_window.json"
     7  "litellm/model_prices_and_context_window_backup.json"
     1  "../../litellm/model_prices_and_context_window_backup.json"
     1  "../../../../model_prices_and_context_window.json"
     1  "../../../../../model_prices_and_context_window.json"

The repair that will work is not a string substitution. It is replacing each read with the
loader's own `PRICES_PATH`, which is base-independent and correct by construction, and which the
four files handled by hand already use. That needs an import added per file and the expression
rewritten, not a filename swapped, so it wants its own pass rather than being wedged between
phases. The `VACUOUS` list below still holds and is the part that was right.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import subprocess
import sys
from collections.abc import Sequence
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[1]

CANONICAL: Final = "data/pricing/model_prices.json"

# Both old spellings, longest first so the backup is matched before the root file's name, which is
# a prefix of it.
OLD_PATHS: Final[tuple[str, ...]] = (
    "litellm/model_prices_and_context_window_backup.json",
    "model_prices_and_context_window_backup.json",
    "model_prices_and_context_window.json",
)

# A line that builds a path, as opposed to one that names the file in prose. An upstream URL is
# not a path into this repository and must keep pointing at upstream's copy.
BUILDS_A_PATH: Final = re.compile(
    r"\b(open|Path|read_text|read_bytes|json\.load|load_model_cost|_load_model_cost"
    r"|os\.path\.join|os\.path\.dirname|parents|parent)\b"
)
UPSTREAM: Final = re.compile(r"https?://")

# Functions whose whole purpose was comparing the two copies. Listed rather than matched on the
# name, so that adding one to this list is a decision somebody made rather than a pattern that
# quietly swept up a test that still asserts something.
VACUOUS: Final[tuple[tuple[str, str], ...]] = (
    ("tests/local_testing/test_get_model_file.py", "test_get_backup_model_cost_map"),
    ("tests/test_litellm/llms/openai_like/test_scx_ai_provider.py", "test_scx_ai_models_synced_to_backup"),
    ("tests/test_litellm/test_anthropic_sonnet_1hr_cache_pricing.py", "test_backup_matches_main_for_claude_3_1hr_cache_write"),
    ("tests/test_litellm/test_azure_ai_grok_4_3_model_metadata.py", "test_azure_ai_grok_4_3_backup_matches_main"),
    ("tests/test_litellm/test_gpt_5_5_model_metadata.py", "test_azure_ai_gpt_5_5_backup_matches_main"),
    ("tests/test_litellm/test_gpt_realtime_mode.py", "test_backup_matches_main_for_realtime_models"),
    ("tests/test_litellm/test_muse_spark_1_1_model_metadata.py", "test_muse_spark_1_1_backup_matches_main"),
    ("tests/test_litellm/test_muse_spark_1_2_model_metadata.py", "test_muse_spark_1_2_backup_matches_main"),
    ("tests/test_litellm/test_muse_spark_1_3_model_metadata.py", "test_muse_spark_1_3_backup_matches_main"),
    ("tests/test_litellm/test_replicate_model_key_format.py", "test_replicate_backup_matches_main"),
    ("tests/test_litellm/test_together_ai_model_metadata.py", "test_together_backup_cost_map_in_sync"),
    ("tests/test_litellm/test_utils.py", "test_deepseek_v4_models_in_backup_cost_map"),
)

# Left alone on purpose: each loops over both copies to assert a flag in every entry, so turning
# it into one file changes what it covers rather than where it reads from.
BY_HAND: Final[tuple[str, ...]] = (
    "tests/test_litellm/llms/anthropic/experimental_pass_through/messages/"
    "test_anthropic_experimental_pass_through_messages_handler.py",
    "tests/test_litellm/llms/azure_ai/claude/test_azure_anthropic_messages_transformation.py",
    "tests/test_litellm/llms/bedrock/messages/invoke_transformations/"
    "test_anthropic_claude3_transformation.py",
    "tests/test_litellm/llms/tencent/chat/test_tencent_chat_transformation.py",
    "tests/test_litellm/llms/vertex_ai/vertex_ai_partner_models/anthropic/"
    "test_vertex_ai_partner_models_anthropic_messages_config.py",
)

# The test that enforces there being one copy. It names the old paths in order to assert they are
# absent, so repointing it would make it assert nothing.
ENFORCES_ONE_COPY: Final = "tests/test_litellm/litellm_core_utils/test_get_model_cost_map.py"


def repoint(line: str) -> str:
    """A path to either old file becomes a path to the one that exists."""
    if not BUILDS_A_PATH.search(line) or UPSTREAM.search(line):
        return line
    for old in OLD_PATHS:
        if old in line:
            return line.replace(old, CANONICAL)
    return line


def _function_lines(text: str, name: str) -> tuple[int, int] | None:
    """The 1-indexed line span of a test function, decorators included.

    Walks the whole tree rather than the top level: several of these are methods on a class, and
    looking only at module scope reported them as missing.
    """
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            first = min((d.lineno for d in node.decorator_list), default=node.lineno)
            return first, node.end_lineno or node.lineno
    return None


def _without(text: str, name: str) -> str | None:
    """The file with that function gone, or None if it is not there or could not go cleanly."""
    span: Final = _function_lines(text, name)
    if span is None:
        return None
    first, last = span
    lines: Final = text.splitlines(keepends=True)
    # Take the blank lines before it too, so the file does not end up with four in a row.
    start = first - 1
    while start > 0 and not lines[start - 1].strip():
        start -= 1
    shorter: Final = "".join(lines[:start] + lines[last:])
    try:
        # Removing the only method of a class leaves an empty body, which does not parse. Better
        # to refuse and say so than to write a file that no longer imports.
        _ = ast.parse(shorter)
    except SyntaxError:
        return None
    return shorter


def _targets() -> tuple[str, ...]:
    found: Final = subprocess.run(
        ("git", "grep", "-l", "model_prices_and_context_window", "--", "tests"),
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    ).stdout.split()
    return tuple(f for f in found if f != ENFORCES_ONE_COPY and f not in BY_HAND)


def main(argv: Sequence[str] | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print what would change")
    args: Final = parser.parse_args(argv)

    removed, repointed, absent = 0, 0, []
    for path, name in VACUOUS:
        file = REPO / path
        if not file.is_file():
            absent.append(f"{path} (file)")
            continue
        with file.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
        shorter = _without(text, name)
        if shorter is None:
            absent.append(f"{path}::{name}")
            continue
        removed += 1
        sys.stdout.write(f"remove {path}::{name}\n")
        if not args.dry_run:
            with file.open("w", encoding="utf-8", newline="") as handle:
                _ = handle.write(shorter)

    for path in _targets():
        file = REPO / path
        with file.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
        updated = "".join(repoint(line) for line in text.splitlines(keepends=True))
        if updated == text:
            continue
        repointed += 1
        sys.stdout.write(f"repoint {path}\n")
        if not args.dry_run:
            with file.open("w", encoding="utf-8", newline="") as handle:
                _ = handle.write(updated)

    sys.stdout.write(
        f"\n{removed} function(s) removed, {repointed} file(s) repointed"
        f"{' (dry run, nothing written)' if args.dry_run else ''}\n"
    )
    if absent:
        sys.stderr.write(f"\n{len(absent)} listed target(s) not found:\n")
        for item in absent:
            sys.stderr.write(f"  {item}\n")
        return 1
    sys.stdout.write(f"{len(BY_HAND)} file(s) left for a person, listed in BY_HAND\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
