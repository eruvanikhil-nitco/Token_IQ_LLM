"""Tests for scripts/rename/rename_env_names_in_deployment.py.

The failure this guards is quiet in the opposite direction from the engine's. A deployment that sets a
name nothing reads leaves the knob off while the file looks right, and no test anywhere fails. So the
pass only renames a name the engine demonstrably asks for, and the list of those is read out of the
engine rather than written down, which is the part worth testing.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_env_names_in_deployment.py"
_spec = importlib.util.spec_from_file_location("rename_env_names_in_deployment", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_env_names_in_deployment = importlib.util.module_from_spec(_spec)
sys.modules["rename_env_names_in_deployment"] = rename_env_names_in_deployment
_spec.loader.exec_module(rename_env_names_in_deployment)

KNOWN = frozenset({"TOKEN_IQ_MASTER_KEY", "TOKEN_IQ_LOG", "TOKEN_IQ_NON_ROOT"})


def moved(text: str) -> str:
    found, _count = rename_env_names_in_deployment.rewrite(text, KNOWN)
    return found


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('LITELLM_MASTER_KEY = "sk-1234"', 'TOKEN_IQ_MASTER_KEY = "sk-1234"'),
        ("      -e LITELLM_LOG=ERROR \\", "      -e TOKEN_IQ_LOG=ERROR \\"),
        ("ENV LITELLM_NON_ROOT=true", "ENV TOKEN_IQ_NON_ROOT=true"),
        ('{ name = "LITELLM_MASTER_KEY", valueFrom = x }', '{ name = "TOKEN_IQ_MASTER_KEY", valueFrom = x }'),
        ('master_key = "os.environ/LITELLM_MASTER_KEY"', 'master_key = "os.environ/TOKEN_IQ_MASTER_KEY"'),
    ],
)
def test_a_name_the_engine_asks_for_is_renamed(before: str, after: str) -> None:
    assert moved(before) == after


@pytest.mark.parametrize(
    "line",
    [
        "LITELLM_LICENSE=$LITELLM_LICENSE",
        "ARG LITELLM_BUILD_IMAGE=cgr.dev/chainguard/wolfi-base",
        'LITELLM_LOCAL_MODEL_COST_MAP: "True"',
    ],
)
def test_a_name_the_engine_does_not_ask_for_is_left_alone(line: str) -> None:
    """Three different reasons: the enterprise package reads it, Docker reads it, nothing reads it. All
    three look the same from here, and renaming any of them points a deployment at a dead variable."""
    assert moved(line) == line


def test_a_reference_moves_with_the_assignment_in_the_same_file() -> None:
    """A half-renamed file is worse than an unrenamed one: the shell expands the old name to nothing."""
    before = 'export LITELLM_MASTER_KEY=sk-1234\ncurl -H "x-key: $LITELLM_MASTER_KEY"\n'

    assert moved(before) == 'export TOKEN_IQ_MASTER_KEY=sk-1234\ncurl -H "x-key: $TOKEN_IQ_MASTER_KEY"\n'


@pytest.mark.parametrize("line", ["MY_LITELLM_LOG=1", "XLITELLM_LOG=1", "LITELLM_MASTER_KEYS=2"])
def test_a_name_that_merely_contains_one_is_not_renamed(line: str) -> None:
    assert moved(line) == line


def test_what_is_left_behind_is_reported_with_where_to_find_it() -> None:
    text = "a: 1\nLITELLM_LICENSE: x\nb: 2\n"

    left = rename_env_names_in_deployment.left_behind(text, "deploy/x.yml", KNOWN)

    assert [(item.name, item.where, item.line) for item in left] == [("LITELLM_LICENSE", "deploy/x.yml", 2)]


def test_a_name_that_was_renamed_is_not_also_reported() -> None:
    after = moved("LITELLM_MASTER_KEY: x\n")

    assert rename_env_names_in_deployment.left_behind(after, "deploy/x.yml", KNOWN) == ()


def test_the_list_of_names_comes_from_the_engine() -> None:
    """Written down here it would drift, and a drifted list is how a deployment ends up setting a name
    nothing reads. `TOKEN_IQ_MASTER_KEY` is read by `proxy_server`; the licence is read by the enterprise
    package, which is not in this repository."""
    asked = rename_env_names_in_deployment.asked_for()

    assert "TOKEN_IQ_MASTER_KEY" in asked
    assert "TOKEN_IQ_SALT_KEY" in asked
    assert "TOKEN_IQ_LICENSE" not in asked


@pytest.mark.parametrize(
    "kept",
    [
        "docs/status.md",
        "docs/decisions/0023-remove-litellm-names.md",
        "docs/plans/2026-10-04-independent-codebase.md",
    ],
)
def test_the_records_under_docs_are_out_of_scope(kept: str) -> None:
    """Decision 0023 keeps the name in the records of how this happened, and `docs/` reaches them. The
    rest of `docs/` is in scope, which is what makes these exclusions do work rather than read as
    decoration."""
    listed = {rename_env_names_in_deployment.named(path) for path in rename_env_names_in_deployment.tracked()}

    assert kept not in listed
    assert "docs/README.md" in listed, "the exclusion is too wide"


@pytest.mark.parametrize("kept", ["LICENSE", "NOTICE", "CHANGELOG.md"])
def test_the_places_that_keep_the_name_for_legal_reasons_are_never_reached(kept: str) -> None:
    """These keep it forever too, and the scope is an allow-list of paths none of them sit under, so
    nothing has to remember to exclude them."""
    listed = {rename_env_names_in_deployment.named(path) for path in rename_env_names_in_deployment.tracked()}

    assert kept not in listed
    assert not any(kept.startswith(path) for path in rename_env_names_in_deployment.SCOPE)


def test_this_pass_and_its_tests_are_out_of_scope() -> None:
    listed = {rename_env_names_in_deployment.named(path) for path in rename_env_names_in_deployment.tracked()}

    assert "scripts/rename/rename_env_names_in_deployment.py" not in listed
    assert "tests/gateway/test_rename_env_names_in_deployment.py" not in listed
    assert ".env.example" in listed, "the filter is too wide"


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "compose.yml"
    _ = source.write_text('LITELLM_MASTER_KEY: "sk-1234"\n', encoding="utf-8")

    totals, _left = rename_env_names_in_deployment.run([source], write=False, known=KNOWN)

    assert sum(totals.values()) == 1
    assert source.read_text(encoding="utf-8") == 'LITELLM_MASTER_KEY: "sk-1234"\n'


def test_applying_writes_the_file(tmp_path: Path) -> None:
    source = tmp_path / "compose.yml"
    _ = source.write_text('LITELLM_MASTER_KEY: "sk-1234"\n', encoding="utf-8")

    _totals, _left = rename_env_names_in_deployment.run([source], write=True, known=KNOWN)

    assert source.read_text(encoding="utf-8") == 'TOKEN_IQ_MASTER_KEY: "sk-1234"\n'


def test_nothing_in_the_repository_still_sets_a_renamed_name(tmp_path: Path) -> None:
    """The pass is idempotent, which is also the check that it finished: a second run moves nothing."""
    _totals, _left = rename_env_names_in_deployment.run(
        rename_env_names_in_deployment.tracked(), write=False, known=rename_env_names_in_deployment.asked_for()
    )

    assert sum(_totals.values()) == 0, f"still to rename: {dict(_totals)}"
