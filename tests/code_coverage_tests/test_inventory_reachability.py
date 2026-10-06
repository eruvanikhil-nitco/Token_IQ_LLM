"""Phase 0 reachability: evidence for keeping code, never permission to delete it."""

from __future__ import annotations

import pathlib
from typing import Final

from scripts.inventory.reachability import analyse, imports_of, module_name_for


def _tree(root: pathlib.Path, modules: dict[str, str]) -> pathlib.Path:
    for dotted, body in modules.items():
        path: Final = root / (dotted.replace(".", "/") + ".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        for parent in path.parents:
            if parent == root:
                break
            (parent / "__init__.py").touch()
    return root


class TestModuleNames:
    def test_maps_a_file_to_its_dotted_name(self, tmp_path: pathlib.Path) -> None:
        assert module_name_for(tmp_path / "pkg" / "sub" / "mod.py", tmp_path) == "pkg.sub.mod"

    def test_an_init_names_its_package_not_itself(self, tmp_path: pathlib.Path) -> None:
        assert module_name_for(tmp_path / "pkg" / "__init__.py", tmp_path) == "pkg"


class TestImportsOf:
    def test_reads_plain_and_from_imports(self) -> None:
        found: Final = imports_of("import pkg.a\nfrom pkg.b import thing\n", module="pkg.entry")
        assert "pkg.a" in found.runtime
        assert "pkg.b" in found.runtime

    def test_offers_the_imported_name_as_a_submodule_candidate(self) -> None:
        """`from pkg import x` cannot be told apart from importing the submodule `pkg.x`.

        Both are recorded and the resolver keeps whichever is a real module. Guessing wrong
        toward fewer edges is what makes live code look dead.
        """
        found: Final = imports_of("from pkg.b import thing\n", module="pkg.entry")
        assert "pkg.b.thing" in found.runtime

    def test_resolves_a_relative_import_against_the_importing_package(self) -> None:
        found: Final = imports_of("from . import sibling\nfrom .deeper import x\n", module="pkg.sub.entry")
        assert "pkg.sub.sibling" in found.runtime
        assert "pkg.sub.deeper" in found.runtime

    def test_separates_a_type_checking_import(self) -> None:
        """A module used only in annotations is used differently, and phase 5 may treat it so."""
        source: Final = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg.types import T\n"
        found: Final = imports_of(source, module="pkg.entry")
        assert "pkg.types" not in found.runtime
        assert "pkg.types" in found.type_only

    def test_follows_a_dynamic_import_written_as_a_literal(self) -> None:
        found: Final = imports_of('importlib.import_module("pkg.plugin")\n', module="pkg.entry")
        assert found.runtime == ("pkg.plugin",)

    def test_reports_a_dynamic_import_it_cannot_resolve_instead_of_ignoring_it(self) -> None:
        """The honest case. Silence here is what makes live code look dead."""
        found: Final = imports_of('importlib.import_module(f"pkg.{name}")\n', module="pkg.entry")
        assert found.runtime == ()
        assert len(found.unresolved) == 1
        assert found.unresolved[0].module == "pkg.entry"

    def test_reports_an_unresolved_dunder_import_too(self) -> None:
        found: Final = imports_of("__import__(chosen)\n", module="pkg.entry")
        assert len(found.unresolved) == 1

    def test_survives_a_file_it_cannot_parse(self) -> None:
        """One syntax error must not abort the whole graph."""
        found: Final = imports_of("def broken(\n", module="pkg.entry")
        assert found.runtime == ()
        assert found.unparsed


class TestAnalyse:
    def test_a_module_imported_from_an_entry_point_is_used(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"pkg.entry": "import pkg.used", "pkg.used": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.used"].verdict == "used"

    def test_unreachability_propagates_rather_than_stopping_at_the_first_hop(
        self, tmp_path: pathlib.Path
    ) -> None:
        """If this breaks, almost everything looks used and the inventory proposes nothing."""
        _tree(tmp_path, {"pkg.entry": "", "pkg.orphan": "import pkg.only_orphan_uses_me", "pkg.only_orphan_uses_me": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.orphan"].verdict == "unproven"
        assert graph.verdicts["pkg.only_orphan_uses_me"].verdict == "unproven"

    def test_reaches_through_a_chain(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"pkg.entry": "import pkg.a", "pkg.a": "import pkg.b", "pkg.b": "import pkg.c", "pkg.c": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert all(graph.verdicts[m].verdict == "used" for m in ("pkg.a", "pkg.b", "pkg.c"))

    def test_a_module_nothing_reaches_is_unproven_and_never_delete(self, tmp_path: pathlib.Path) -> None:
        """The analyser has no delete verdict at all. A person decides that."""
        _tree(tmp_path, {"pkg.entry": "", "pkg.lonely": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.lonely"].verdict == "unproven"
        assert all(v.verdict != "delete" for v in graph.verdicts.values())

    def test_a_module_reached_only_for_types_is_marked_as_such(self, tmp_path: pathlib.Path) -> None:
        source: Final = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg.shapes import S\n"
        _tree(tmp_path, {"pkg.entry": source, "pkg.shapes": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.shapes"].verdict == "used-type-only"

    def test_a_runtime_use_outranks_a_type_only_one(self, tmp_path: pathlib.Path) -> None:
        source: Final = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg.shapes import S\n"
        _tree(tmp_path, {"pkg.entry": source, "pkg.other": "import pkg.shapes", "pkg.shapes": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry", "pkg.other"))
        assert graph.verdicts["pkg.shapes"].verdict == "used"

    def test_records_which_entry_point_reached_a_module(self, tmp_path: pathlib.Path) -> None:
        """An inventory row has to say why it is kept, not just that it is."""
        _tree(tmp_path, {"pkg.entry": "import pkg.used", "pkg.used": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.used"].reached_from == ("pkg.entry",)

    def test_collects_every_unresolved_dynamic_import_for_a_human_to_read(
        self, tmp_path: pathlib.Path
    ) -> None:
        _tree(tmp_path, {"pkg.entry": 'importlib.import_module(f"pkg.{n}")\n'})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert len(graph.unresolved) == 1

    def test_an_entry_point_is_used_even_with_nothing_importing_it(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"pkg.entry": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.entry"].verdict == "used"

    def test_a_cycle_does_not_hang(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"pkg.entry": "import pkg.a", "pkg.a": "import pkg.b", "pkg.b": "import pkg.a"})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.b"].verdict == "used"


class TestRegistryLiterals:
    """A module that resolves imports at runtime turns its own string literals into edges.

    `token_iq/gateway/_lazy_imports_registry.py` holds 269 dotted module paths that are handed to
    `importlib.import_module` elsewhere. Reading only the call site misses every one of them,
    and the provider transformations phase 5 decides on are mostly in that list.

    The rule is deliberately narrow: only a file that performs a dynamic import it could not
    resolve contributes its literals. Treating every dotted string in the tree as an import
    would invent edges and mark dead code alive.
    """

    def test_a_dotted_literal_in_a_dynamic_importer_becomes_an_edge(self, tmp_path: pathlib.Path) -> None:
        _tree(
            tmp_path,
            {
                "pkg.entry": 'TABLE = {"a": "pkg.plugin"}\nimportlib.import_module(TABLE[k])\n',
                "pkg.plugin": "",
            },
        )
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.plugin"].verdict == "used"

    def test_a_relative_literal_resolves_against_the_holding_package(self, tmp_path: pathlib.Path) -> None:
        _tree(
            tmp_path,
            {
                "pkg.registry": 'TABLE = {"a": ".plugin"}\nimportlib.import_module(TABLE[k])\n',
                "pkg.plugin": "",
            },
        )
        graph: Final = analyse(tmp_path, entry_points=("pkg.registry",))
        assert graph.verdicts["pkg.plugin"].verdict == "used"

    def test_a_file_with_no_dynamic_import_contributes_no_literal_edges(self, tmp_path: pathlib.Path) -> None:
        """Otherwise a docstring or a log message would keep dead code alive."""
        _tree(tmp_path, {"pkg.entry": 'MESSAGE = "see pkg.plugin for details"\n', "pkg.plugin": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.verdicts["pkg.plugin"].verdict == "unproven"

    def test_a_literal_naming_nothing_real_is_not_an_edge(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"pkg.entry": 'T = {"a": "not.a.module"}\nimportlib.import_module(T[k])\n'})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry",))
        assert graph.unresolved  # still reported: the call itself was never resolved


class TestNamedLiteralSources:
    """Some registries hold the paths while a different module performs the import.

    `token_iq/gateway/_lazy_imports_registry.py` is the real case: 269 dotted paths live there, and
    `_lazy_imports.py` is what calls `import_module`. Neither file alone looks like a dynamic
    importer holding literals, so the registry is named explicitly rather than guessed at.
    """

    def test_a_named_source_contributes_its_literals_without_importing_anything(
        self, tmp_path: pathlib.Path
    ) -> None:
        _tree(tmp_path, {"pkg.registry": 'TABLE = {"a": "pkg.plugin"}\n', "pkg.plugin": "", "pkg.entry": ""})
        graph: Final = analyse(
            tmp_path, entry_points=("pkg.entry", "pkg.registry"), literal_sources=("pkg.registry",)
        )
        assert graph.verdicts["pkg.plugin"].verdict == "used"

    def test_an_unnamed_source_still_contributes_nothing(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"pkg.registry": 'TABLE = {"a": "pkg.plugin"}\n', "pkg.plugin": "", "pkg.entry": ""})
        graph: Final = analyse(tmp_path, entry_points=("pkg.entry", "pkg.registry"))
        assert graph.verdicts["pkg.plugin"].verdict == "unproven"
