"""Tests for scripts/rename/scope_identifiers.py.

This decides which of 2,217 identifiers phase 6 may rename. A wrong "phase 6" renames something a
running installation reads, which is silent: the code still works and a customer's payload field, price
key or calling convention quietly changes name. A wrong "deferred" costs nothing but a later pass.

So each reason for deferring is exercised on a name that must be deferred for it, and on one that must
not be, with the two kept apart by what Python's own conventions say about them.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "scope_identifiers.py"
_spec = importlib.util.spec_from_file_location("scope_identifiers", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
scope_identifiers = importlib.util.module_from_spec(_spec)
sys.modules["scope_identifiers"] = scope_identifiers
_spec.loader.exec_module(scope_identifiers)


def write(path: Path, text: str) -> Path:
    _ = path.write_text(text, encoding="utf-8")
    return path


# --- what counts as a string a caller passes by name ---------------------------------------------


def test_a_name_passed_as_a_string_is_found(tmp_path: Path) -> None:
    """`kwargs.get("litellm_logging_obj")` is how a caller passes that argument, so the name is the
    calling convention rather than a private detail. 106 rows are like this."""
    source = write(tmp_path / "m.py", 'x = kwargs.get("litellm_logging_obj")\n')

    assert scope_identifiers.written_as_strings([source], frozenset({"litellm_logging_obj"})) == frozenset(
        {"litellm_logging_obj"}
    )


def test_a_name_only_ever_written_as_code_is_not_found(tmp_path: Path) -> None:
    source = write(tmp_path / "m.py", "obj = LiteLLMLoggingObj()\n")

    assert scope_identifiers.written_as_strings([source], frozenset({"LiteLLMLoggingObj"})) == frozenset()


def test_a_file_that_does_not_parse_is_skipped_rather_than_failing(tmp_path: Path) -> None:
    """Some committed files are deliberately invalid Python, as fixtures for other tests."""
    source = write(tmp_path / "broken.py", "def (\n")

    assert scope_identifiers.written_as_strings([source], frozenset({"litellm_x"})) == frozenset()


# --- what counts as serialised -------------------------------------------------------------------


def test_a_field_of_a_pydantic_model_is_found(tmp_path: Path) -> None:
    """It serialises, so the field name is in a response body."""
    source = write(
        tmp_path / "m.py",
        "class EmbeddingRequest(BaseModel):\n    litellm_logging_obj: object = None\n",
    )

    assert scope_identifiers.serialised_fields([source], frozenset({"litellm_logging_obj"})) == frozenset(
        {"litellm_logging_obj"}
    )


def test_a_field_of_a_typed_dict_is_found(tmp_path: Path) -> None:
    source = write(tmp_path / "m.py", "class Row(TypedDict):\n    litellm_provider: str\n")

    assert scope_identifiers.serialised_fields([source], frozenset({"litellm_provider"})) == frozenset(
        {"litellm_provider"}
    )


def test_an_attribute_of_a_plain_class_is_not_a_field(tmp_path: Path) -> None:
    """A plain class is an implementation detail. Nothing serialises it, so its attribute names are
    Python's own."""
    source = write(tmp_path / "m.py", "class Helper:\n    litellm_cache: dict = {}\n")

    assert scope_identifiers.serialised_fields([source], frozenset({"litellm_cache"})) == frozenset()


# --- what counts as a data format ----------------------------------------------------------------


def test_a_json_key_is_found(tmp_path: Path) -> None:
    """`litellm_provider` is a key in 3,559 entries of the committed price file, so renaming the Python
    name alone breaks every price lookup and renaming both is a data-format change."""
    source = write(tmp_path / "prices.json", '{"gpt-4o": {"litellm_provider": "openai"}}\n')

    assert scope_identifiers.data_keys([source], frozenset({"litellm_provider"})) == frozenset({"litellm_provider"})


def test_a_yaml_key_is_found(tmp_path: Path) -> None:
    source = write(tmp_path / "config.yaml", "jobs:\n  litellm_params_template: x\n")

    assert scope_identifiers.data_keys([source], frozenset({"litellm_params_template"})) == frozenset(
        {"litellm_params_template"}
    )


def test_a_value_rather_than_a_key_is_not_a_data_format(tmp_path: Path) -> None:
    """Only a key names a field. A value is data, and renaming the identifier does not touch it."""
    source = write(tmp_path / "config.yaml", "provider: litellm_proxy\n")

    assert scope_identifiers.data_keys([source], frozenset({"litellm_proxy"})) == frozenset()


# --- what counts as a Python name ----------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "x = LiteLLMRoutes.openai_routes\n",
        "class LiteLLMRoutes(enum.Enum): ...\n",
        "def f(LiteLLMRoutes=None): ...\n",
        "f(LiteLLMRoutes=1)\n",
        "from x import LiteLLMRoutes\n",
        "from x import y as LiteLLMRoutes\n",
    ],
)
def test_every_position_a_python_name_can_take_is_found(tmp_path: Path, source: str) -> None:
    """A row that appears in none of these belongs to the dashboard, and a pass over Python cannot
    rename it. 746 rows are that, led by a TypeScript function with 108 uses."""
    written = write(tmp_path / "m.py", source)

    assert scope_identifiers.python_names([written], frozenset({"LiteLLMRoutes"})) == frozenset({"LiteLLMRoutes"})


def test_a_name_only_in_a_string_is_not_a_python_name(tmp_path: Path) -> None:
    source = write(tmp_path / "m.py", 'label = "getGlobalLitellmHeaderName"\n')

    assert scope_identifiers.python_names([source], frozenset({"getGlobalLitellmHeaderName"})) == frozenset()


# --- the verdict ---------------------------------------------------------------------------------


def test_capwords_is_exempt_from_the_string_test_and_only_that_one() -> None:
    """A class written as a string is a forward reference, not a key: `"LiteLLMLoggingObj"` appears 172
    times that way and every one is an annotation. Python's conventions are the only thing that can tell
    those apart, which is why the exemption is by case and nothing else."""
    assert scope_identifiers.capwords("LiteLLMLoggingObj") is True
    assert scope_identifiers.capwords("_LiteLLMLoggingObj") is True
    assert scope_identifiers.capwords("litellm_logging_obj") is False
    assert scope_identifiers.capwords("_litellm_judged") is False


def test_the_scope_artifact_decides_every_row_and_says_why() -> None:
    """Read from the committed file rather than recomputed: it is what the rename pass reads, so a row
    with no verdict there is a row that pass would skip without saying so."""
    import csv

    with (_REPO_ROOT / "docs" / "plans" / "phase-6-identifier-scope.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows, "the scope artifact is empty"
    assert all(row["verdict"] in {"phase 6", "deferred"} for row in rows)
    assert all(row["because"] for row in rows), "a row was decided without saying why"
    assert any(row["verdict"] == "phase 6" for row in rows)
    assert any(row["verdict"] == "deferred" for row in rows)


def test_the_names_this_phase_must_not_touch_are_deferred() -> None:
    """The four that would each have been a silent change, named so a later edit to the rules has to
    keep them out: a payload field, a price-file key, a calling convention and a module."""
    import csv

    with (_REPO_ROOT / "docs" / "plans" / "phase-6-identifier-scope.csv").open(encoding="utf-8") as handle:
        verdicts = {row["old"]: row["verdict"] for row in csv.DictReader(handle)}

    for name in ("litellm_provider", "litellm_logging_obj", "litellm_credential_name", "litellm_proxy_extras"):
        assert verdicts.get(name) == "deferred", f"{name} would be renamed, and something outside reads it"


# --- the verdict, with the scans injected --------------------------------------------------------


EMPTY = frozenset()


def verdict_for(name: str, **found: frozenset[str]) -> tuple[str, str]:
    """One row's verdict, with every scan answered here rather than looked up in this checkout."""
    scans = {"strings": EMPTY, "fields": EMPTY, "keys": EMPTY, "modules": EMPTY, "in_python": frozenset({name})}
    scans.update(found)
    decided = scope_identifiers.decide([{"old": name, "new": "x", "files": "1"}], **scans)
    return decided[0].verdict, decided[0].because


def test_a_name_nothing_outside_reads_is_this_phases() -> None:
    assert verdict_for("LiteLLMRoutes")[0] == "phase 6"


@pytest.mark.parametrize(
    ("name", "scan", "expected_reason"),
    [
        ("litellm_logging_obj", "strings", "passes it by name"),
        ("litellm_provider", "fields", "in a payload"),
        ("litellm_params_template", "keys", "a data format"),
        ("litellm_pre_call_utils", "modules", "moves a file"),
    ],
)
def test_each_reason_defers_the_row_on_its_own(name: str, scan: str, expected_reason: str) -> None:
    """One clause at a time, with the other four answering no. Dropping any of them has to fail here."""
    call, because = verdict_for(name, **{scan: frozenset({name})})

    assert call == "deferred"
    assert expected_reason in because


def test_a_name_that_is_not_a_python_name_is_deferred() -> None:
    call, because = verdict_for("getGlobalLitellmHeaderName", in_python=EMPTY)

    assert call == "deferred"
    assert "the UI work renames it" in because


def test_a_class_written_as_a_string_is_still_this_phases() -> None:
    """The one exemption, and it is to the string test alone: a class written as a string is a forward
    reference. 172 of them are, and every one is an annotation."""
    assert verdict_for("LiteLLMLoggingObj", strings=frozenset({"LiteLLMLoggingObj"}))[0] == "phase 6"


def test_a_class_that_is_a_payload_field_is_still_deferred() -> None:
    """The exemption does not extend to the other tests. A CapWords name used as a field would still be
    in a response body."""
    assert verdict_for("LiteLLMBatch", fields=frozenset({"LiteLLMBatch"}))[0] == "deferred"
