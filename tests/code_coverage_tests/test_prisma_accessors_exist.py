"""No Prisma accessor is named after a package instead of a model.

`prisma_client.db.<accessor>` reaches a table, and the accessor is the model's name lowercased, nothing
else. The rename programme put a prefix on six of them, turning `db.litellm_providersyncrun` into
`db.gateway_providersyncrun` when the model had become plain `ProviderSyncRun`. Six accessors across five
modules then named nothing, and `/provider/connections` and `/tool/connections` answered 500 with
`AttributeError: 'Prisma' object has no attribute 'gateway_providersyncrun'`. Two pages of the dashboard
were empty.

Nothing caught it. The generated client is untyped, so basedpyright sees `Any`. The tests set the same
wrong name on a `MagicMock`, which creates any attribute asked of it, so every one of them passed against
a mock and none could ever fail. That is the shape this guards: a name only a rename pass would produce.

The rule is the prefix rather than the whole set, because `db` also carries real client methods
(`query_raw`, `tx`, `batch_`) and this fork's own wrapper attributes (`writer`, `reader`), and no list of
those could be derived without the generated client, which is not built in every environment.
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
from collections.abc import Iterator
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
SCHEMA: Final = REPO / "schema.prisma"
SCOPE: Final[tuple[str, ...]] = ("token_iq/*.py", "tests/*.py")

PACKAGE_PREFIXES: Final[tuple[str, ...]] = ("gateway_", "litellm_", "token_iq_", "tokeniq_")
"""What a rename pass bolts on. A model's accessor never carries one, so any of these names nothing."""

DB_HOLDERS: Final[frozenset[str]] = frozenset({"db", "_db"})


class Accessor(BaseModel, frozen=True):
    """One `db.<name>` reached in the source, and where."""

    file: str
    line: int
    name: str


def models() -> frozenset[str]:
    """Every accessor the schema defines, which is each model's name lowercased."""
    return frozenset(m.lower() for m in re.findall(r"^model\s+(\w+)", SCHEMA.read_text(encoding="utf-8"), re.M))


def _reached_off_db(node: ast.Attribute) -> bool:
    base: Final = node.value
    if isinstance(base, ast.Attribute):
        return base.attr in DB_HOLDERS
    return isinstance(base, ast.Name) and base.id in DB_HOLDERS


def accessors_in(source: str, name: str = "<string>") -> Iterator[Accessor]:
    try:
        tree: Final = ast.parse(source)
    except SyntaxError:
        return
    yield from (
        Accessor(file=name, line=node.lineno, name=node.attr)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and _reached_off_db(node)
    )


def _tracked() -> tuple[str, ...]:
    return tuple(
        line
        for line in subprocess.run(
            ("git", "ls-files", *SCOPE), cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        if line and line != "tests/code_coverage_tests/test_prisma_accessors_exist.py"
    )


def _every_accessor() -> tuple[Accessor, ...]:
    found: list[Accessor] = []  # rebind-ok: the accumulator of a scan over files
    for name in _tracked():
        try:
            found.extend(accessors_in((REPO / name).read_text(encoding="utf-8"), name))
        except (OSError, UnicodeDecodeError):
            continue
    return tuple(found)


def test_no_accessor_carries_a_package_prefix() -> None:
    offenders: Final = tuple(one for one in _every_accessor() if one.name.startswith(PACKAGE_PREFIXES))
    assert not offenders, "these name no table: " + ", ".join(f"{o.file}:{o.line} db.{o.name}" for o in offenders)


def test_an_accessor_that_is_a_prefixed_model_is_caught() -> None:
    """The exact bug: the model is `ProviderSyncRun`, so `providersyncrun` is the only name that reaches it."""
    caught = tuple(accessors_in("x = prisma.db.gateway_providersyncrun.find_many()"))

    assert [one.name for one in caught] == ["gateway_providersyncrun"]
    assert caught[0].name.startswith(PACKAGE_PREFIXES)
    assert "providersyncrun" in models()


def test_the_real_accessor_passes() -> None:
    caught = tuple(accessors_in("x = prisma.db.providersyncrun.find_many()"))

    assert [one.name for one in caught] == ["providersyncrun"]
    assert not caught[0].name.startswith(PACKAGE_PREFIXES)


def test_a_client_method_is_not_mistaken_for_an_accessor_name() -> None:
    """`query_raw`, `tx` and `batch_` are the client's own, and this fork adds `writer` and `reader`.
    None is a model and none may be reported."""
    for call in ("prisma.db.query_raw(sql)", "client.db.tx()", "self._db.batch_()", "prisma.db.writer"):
        found = tuple(accessors_in(call))
        assert found, call
        assert not found[0].name.startswith(PACKAGE_PREFIXES), call


def test_an_attribute_that_is_not_off_db_is_ignored() -> None:
    """`settings.gateway_providersyncrun` is not a table access, and reporting it would make the gate noise."""
    assert tuple(accessors_in("x = settings.gateway_providersyncrun")) == ()


def test_the_schema_really_parses() -> None:
    """Guards the model set, which an empty read would make vacuous."""
    found = models()

    assert len(found) > 80
    assert "providerusagefact" in found


def test_the_scan_really_reaches_the_source() -> None:
    assert len(_tracked()) > 1000
    assert any(one.name in models() for one in _every_accessor()), "no accessor resolved to a model at all"
