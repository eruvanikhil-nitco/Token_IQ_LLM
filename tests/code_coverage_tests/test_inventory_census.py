"""Phase 0 census: the per-category progress measure for the rename phases."""

from __future__ import annotations

import pathlib
from typing import Final

from scripts.inventory.census import CATEGORIES, count_tree, is_allowlisted, is_excluded


def _tree(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for name, body in files.items():
        path: Final = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


class TestExclusions:
    def test_skips_vendored_dependencies(self) -> None:
        """Counting node_modules is how the source document reached 521,641."""
        assert is_excluded(pathlib.PurePosixPath("ui/litellm-dashboard/node_modules/x/a.js"))

    def test_skips_the_committed_ui_bundle(self) -> None:
        """1,016 tracked files of build output are not source."""
        assert is_excluded(pathlib.PurePosixPath("litellm/proxy/_experimental/out/_next/static/chunks/a.js"))

    def test_does_not_skip_real_source(self) -> None:
        assert not is_excluded(pathlib.PurePosixPath("token_iq/gateway/proxy/proxy_server.py"))
        assert not is_excluded(pathlib.PurePosixPath("ui/litellm-dashboard/src/components/leftnav.tsx"))


class TestCategories:
    def test_counts_total_occurrences_in_any_case(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"a.py": "litellm LiteLLM LITELLM LiTeLlM"})
        assert count_tree(tmp_path).categories["occurrences"] == 4

    def test_counts_environment_variables_separately(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"a.py": 'os.getenv("LITELLM_MASTER_KEY")\nos.environ["LITELLM_MODE"]\nLITELLM_LOG = 1'})
        assert count_tree(tmp_path).categories["env_vars"] == 3

    def test_counts_request_headers_separately(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"a.py": '"x-litellm-call-id"\n"x-litellm-model-id"'})
        assert count_tree(tmp_path).categories["headers"] == 2

    def test_counts_prisma_models_separately(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"schema.prisma": "model LiteLLM_TeamTable {\n}\nmodel LiteLLM_UserTable {\n}"})
        assert count_tree(tmp_path).categories["prisma_models"] == 2

    def test_counts_metrics_separately_from_other_snake_case_names(self, tmp_path: pathlib.Path) -> None:
        """A metric is declared, not merely mentioned, so a bare identifier must not count."""
        _tree(tmp_path, {"a.py": 'Counter("token_iq_spend_metric")\nGauge("litellm_requests")\nlitellm_logging.foo()'})
        assert count_tree(tmp_path).categories["metrics"] == 2

    def test_separates_python_from_ui_source(self, tmp_path: pathlib.Path) -> None:
        """Phases 6 and 9 attack different trees, so one total would hide which is moving."""
        _tree(tmp_path, {"a.py": "litellm", "b.tsx": "litellm litellm"})
        counted: Final = count_tree(tmp_path)
        assert counted.categories["python"] == 1
        assert counted.categories["ui"] == 2

    def test_every_declared_category_is_reported(self, tmp_path: pathlib.Path) -> None:
        """A category that silently vanishes would look like progress to zero."""
        _tree(tmp_path, {"a.py": "nothing here"})
        assert frozenset(count_tree(tmp_path).categories) == frozenset(CATEGORIES)


class TestFileCount:
    def test_counts_files_holding_the_name_not_files_scanned(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"a.py": "litellm", "b.py": "clean", "c.py": "Gateway"})
        assert count_tree(tmp_path).files == 2

    def test_an_excluded_file_adds_nothing(self, tmp_path: pathlib.Path) -> None:
        _tree(tmp_path, {"a.py": "litellm", "node_modules/b.js": "litellm litellm litellm"})
        counted: Final = count_tree(tmp_path)
        assert counted.files == 1
        assert counted.categories["occurrences"] == 1


class TestAllowlist:
    """Phase 10 lets the name survive in history and legal text, so the measure must too.

    A progress metric that can never reach zero stops being read.
    """

    def test_history_and_legal_text_are_allowlisted(self) -> None:
        for path in (
            "docs/decisions/0021-client-facing-rebrand.md",
            "docs/plans/2026-10-04-independent-codebase.md",
            "LICENSE",
            "NOTICE",
            "CHANGELOG.md",
        ):
            assert is_allowlisted(pathlib.PurePosixPath(path)), path

    def test_product_code_and_docs_are_not_allowlisted(self) -> None:
        # docs/specs/ is deliberately NOT allowlisted: a spec is a current document and phase 10
        # requires it to lose the name like any other.
        for path in ("token_iq/gateway/proxy/proxy_server.py", "docs/README.md", "docs/specs/a.md", "schema.prisma"):
            assert not is_allowlisted(pathlib.PurePosixPath(path)), path

    def test_allowlisted_occurrences_are_reported_but_kept_out_of_the_target(
        self, tmp_path: pathlib.Path
    ) -> None:
        _tree(tmp_path, {"a.py": "litellm", "LICENSE": "litellm litellm", "docs/plans/p.md": "litellm"})
        counted: Final = count_tree(tmp_path)
        assert counted.categories["occurrences"] == 1
        assert counted.allowlisted == 3
