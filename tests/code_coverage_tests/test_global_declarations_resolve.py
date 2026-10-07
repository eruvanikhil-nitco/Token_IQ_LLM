"""A name declared `global` is assigned somewhere in the module that declares it.

`global X` followed by `X = ...` is how the proxy publishes startup state for other modules to import.
Nothing checks that the two names agree, and no linter can: the assignment is a store to a global, so it
is never an unused local, and the module attribute the readers import exists either way because some
other line defined it.

The rename programme broke exactly that pair. `load_config` still declared `global litellm_master_key_hash`
while the assignment under it, the module-level definition and the reader in `internal_user_endpoints` had
all become `gateway_master_key_hash`. The assignment went to a function local, the module attribute stayed
`None` for the life of the process, and `general_settings.disable_master_key_return` stopped hiding the
master key from the keys a user-info call returns. Every test passed and the proxy started normally.

An `ast.Global` node holds plain strings rather than `ast.Name` nodes, which is why an identifier pass
walks straight past it. This looks at the strings.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
from collections.abc import Iterator
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
SCOPE: Final[tuple[str, ...]] = ("token_iq/*.py",)


class Dangling(BaseModel, frozen=True):
    """One name a function declares global that nothing in its module ever assigns."""

    file: str
    line: int
    name: str


def _assigned(tree: ast.AST) -> frozenset[str]:
    """Every name the module stores to anywhere, at module level or inside a function."""
    return frozenset(
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    ) | frozenset(
        alias.asname or alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    )


def _declared(tree: ast.AST) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            yield from ((node.lineno, name) for name in node.names)


def dangling_in(source: str, name: str = "<string>") -> tuple[Dangling, ...]:
    tree: Final = ast.parse(source)
    stored: Final = _assigned(tree)
    return tuple(
        Dangling(file=name, line=line, name=declared)
        for line, declared in _declared(tree)
        if declared not in stored
    )


def _tracked() -> tuple[str, ...]:
    return tuple(
        line
        for line in subprocess.run(
            ("git", "ls-files", *SCOPE), cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        if line
    )


def _every_dangling() -> tuple[Dangling, ...]:
    found: list[Dangling] = []  # rebind-ok: the accumulator of a scan over files
    for name in _tracked():
        try:
            found.extend(dangling_in((REPO / name).read_text(encoding="utf-8"), name))
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
    return tuple(found)


def test_no_global_declaration_names_something_the_module_never_assigns() -> None:
    offenders: Final = _every_dangling()
    assert not offenders, "these `global` declarations name something nothing assigns: " + ", ".join(
        f"{one.file}:{one.line} {one.name}" for one in offenders
    )


def test_the_check_catches_the_bug_it_was_written_for() -> None:
    """The real shape: the declaration keeps the old spelling while everything under it was renamed."""
    caught: Final = dangling_in(
        "\n".join(
            (
                "gateway_master_key_hash = None",
                "def load_config():",
                "    global litellm_master_key_hash",
                "    gateway_master_key_hash = hash_token(key)",
            )
        )
    )

    assert [one.name for one in caught] == ["litellm_master_key_hash"]


def test_a_declaration_whose_name_is_assigned_is_accepted() -> None:
    assert dangling_in("x = None\ndef f():\n    global x\n    x = 1\n") == ()


def test_a_name_assigned_only_inside_another_function_is_accepted() -> None:
    """Publishing from one function and clearing from another is normal, and neither sees the other's body."""
    assert dangling_in("def f():\n    global x\n    print(x)\ndef g():\n    global x\n    x = 1\n") == ()


def test_an_imported_name_counts_as_assigned() -> None:
    """`global litellm` over `import litellm` is a rebind of the import, not a dangling name."""
    assert dangling_in("import json\ndef f():\n    global json\n    print(json)\n") == ()


def test_the_scan_really_reaches_the_package() -> None:
    """Guards the invariant above, which passes trivially if git lists nothing."""
    assert len(_tracked()) > 1000
