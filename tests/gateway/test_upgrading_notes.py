"""Tests for the rename map's phase 7 answers and the changelog generated from them.

What a customer reads before upgrading is the worst place for a list that has drifted, and drift here is
silent in both directions. A name in the notes that the engine does not read sends someone to change
configuration for no effect. A name the engine renamed but the notes leave out means their proxy starts
warning about something they were never told to change.

So the map is checked against the code, and the changelog against the map.
"""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

from token_iq.gateway import compat

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    path = _REPO_ROOT / "scripts" / "rename" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fill_rename_map = _load("fill_rename_map")
write_upgrading_notes = _load("write_upgrading_notes")

MAP = _REPO_ROOT / "docs" / "plans" / "rename-map.csv"
CHANGELOG = _REPO_ROOT / "CHANGELOG.md"


def rows() -> list[dict[str, str]]:
    with MAP.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def renamed(kind: str) -> list[tuple[str, str]]:
    return [(row["old"], row["new"]) for row in rows() if row["kind"] == kind and row["new"]]


# --- the changelog against the map ----------------------------------------------------------------


def test_the_changelog_on_disk_matches_the_map() -> None:
    """The guard against someone editing one and not the other. Regenerate with
    `python scripts/rename/write_upgrading_notes.py --apply`."""
    assert write_upgrading_notes.main(["--check"]) == 0


def test_every_renamed_name_is_in_the_notes() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    missing = [
        f"{kind}: {old}"
        for kind in ("env var", "config key", "request header")
        for old, new in renamed(kind)
        if f"| `{old}` | `{new}` |" not in text
    ]

    assert missing == []


def test_a_name_that_was_not_renamed_is_not_in_the_notes() -> None:
    """`LITELLM_LICENSE` is read by a package that is not in this repository, so telling a customer to
    rename it would send them to turn a working knob off.

    `LITELLM_MIGRATION_DIR` used to belong here for the same reason. Phase 8 renamed the migrations package
    and taught it to read both names itself, so it is in the notes now.
    """
    text = CHANGELOG.read_text(encoding="utf-8")

    assert "| `LITELLM_LICENSE` |" not in text
    assert "| `LITELLM_MIGRATION_DIR` | `TOKEN_IQ_MIGRATION_DIR` |" in text


def test_the_bare_prefix_is_not_listed_as_a_variable() -> None:
    """It is a literal in the engine and a row in the inventory, and neither makes it a variable. Listed,
    the notes open by telling a customer to rename nothing into nothing."""
    assert "| `LITELLM_` | `TOKEN_IQ_` |" not in CHANGELOG.read_text(encoding="utf-8")


def test_the_notes_say_how_many_of_each_there_are() -> None:
    """A count that disagrees with the table is the first thing a reader notices."""
    text = CHANGELOG.read_text(encoding="utf-8")

    assert f"Environment variables, {len(renamed('env var'))} of them" in text
    assert f"Config keys, {len(renamed('config key'))} of them" in text
    assert f"Request and response headers, {len(renamed('request header'))} of them" in text


# --- the map against the code ---------------------------------------------------------------------


def test_the_config_keys_in_the_map_are_the_ones_the_engine_accepts() -> None:
    """The map is where the notes come from, and `compat.CONFIG_KEYS` is what the proxy actually reads."""
    assert dict(renamed("config key")) == {old: new for new, old in compat.CONFIG_KEYS.items()}


@pytest.mark.parametrize(("old", "new"), renamed("request header"))
def test_each_header_pair_agrees_with_the_compatibility_helper(old: str, new: str) -> None:
    """`compat.old_header_for` is what a request is actually matched against, so a pair the map states
    and the helper disagrees with is a line in the notes that does not describe the proxy."""
    assert compat.old_header_for(new.removesuffix("*")) == old.removesuffix("*")


def test_every_renamed_variable_is_one_the_engine_reads() -> None:
    asked = fill_rename_map.env_names(fill_rename_map.literals())
    listed = [new for _old, new in renamed("env var")]

    assert [name for name in listed if name not in asked] == []


def test_every_header_in_the_map_is_one_the_engine_names() -> None:
    named = set(fill_rename_map.header_names(fill_rename_map.literals()))
    listed = [new for _old, new in renamed("request header")]

    assert [name for name in listed if name not in named] == []


def test_the_two_headers_the_engine_completes_are_written_as_patterns() -> None:
    """They end in a hyphen in the source because a model group follows. Written that way in the notes a
    reader would take the hyphen for part of the name."""
    patterns = [new for _old, new in renamed("request header") if new.endswith("*")]

    assert sorted(patterns) == [
        "x-token-iq-key-remaining-requests-*",
        "x-token-iq-key-remaining-tokens-*",
    ]


def test_filling_the_map_twice_gives_the_same_map() -> None:
    """A second run has to be a no-op, or the map and the notes churn on every build."""
    once = fill_rename_map.filled(rows(), fill_rename_map.literals())
    twice = fill_rename_map.filled(list(once), fill_rename_map.literals())

    assert once == twice


def test_a_variable_the_engine_stops_reading_is_cleared_rather_than_left() -> None:
    """Otherwise a name only ever gets added to the notes and never leaves them."""
    stale = [{"kind": "env var", "old": "LITELLM_GONE", "new": "TOKEN_IQ_GONE", "files": "1", "note": ""}]

    filled = fill_rename_map.filled(stale, fill_rename_map.literals())

    assert filled[0]["new"] == ""
