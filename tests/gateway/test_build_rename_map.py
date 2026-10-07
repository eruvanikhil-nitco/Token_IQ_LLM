"""Tests for scripts/rename/build_rename_map.py.

The map decides, for every spelling of the old name in the repository, what it becomes and which
phase owns it. Both decisions are easy to get wrong in a way no later check would catch: a name
classified as an identifier when it is really an environment variable gets renamed in phase 6 and
breaks a customer's running configuration, and a name folded onto the wrong new spelling gets
renamed to something that already means something else.

So each rule is exercised on a name it must claim and on one it must not.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "build_rename_map.py"
_spec = importlib.util.spec_from_file_location("build_rename_map", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
build_rename_map = importlib.util.module_from_spec(_spec)
sys.modules["build_rename_map"] = build_rename_map
_spec.loader.exec_module(build_rename_map)

renamed_identifier = build_rename_map.renamed_identifier
classify = build_rename_map.classify
excluded = build_rename_map.excluded


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("LiteLLMRoutes", "GatewayRoutes"),
        ("litellm_logging", "gateway_logging"),
        ("LITELLM_MODE", "GATEWAY_MODE"),
        ("LitellmUserRoles", "GatewayUserRoles"),
        # Spellings nobody intended. They are still the name, so they are still renamed.
        ("liteLLM", "gateway"),
        ("LiTeLlM", "Gateway"),
    ],
)
def test_each_spelling_of_the_name_gets_one_new_name(identifier: str, expected: str) -> None:
    assert renamed_identifier(identifier) == expected


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        # Neither reads correctly as gateway_params: one is a model's own parameters and the other
        # is the gateway's settings, and the plan names both by hand for that reason.
        ("litellm_params", "model_params"),
        ("litellm_settings", "gateway_settings"),
    ],
)
def test_the_two_names_the_plan_decides_by_hand_are_not_renamed_mechanically(identifier: str, expected: str) -> None:
    assert renamed_identifier(identifier) == expected


def test_a_name_without_the_old_name_in_it_is_left_alone() -> None:
    assert renamed_identifier("GatewayRoutes") == ""


@pytest.mark.parametrize(
    ("identifier", "where", "expected"),
    [
        # Phase 6 renames code. Everything a running installation reads by name waits for its own
        # phase, because renaming it in phase 6 breaks that installation on upgrade.
        ("LITELLM_MASTER_KEY", ("token_iq/gateway/proxy/proxy_server.py",), "env var"),
        ("litellm_settings", ("token_iq/gateway/proxy/proxy_server.py",), "config key"),
        ("x-token-iq-model-id", ("token_iq/gateway/proxy/common_utils/http_parsing_utils.py",), "request header"),
        ("LiteLLM_TeamTable", ("schema.prisma",), "database model"),
        ("token_iq_requests_metric", ("token_iq/gateway/integrations/prometheus.py",), "metric name"),
        ("LiteLLMRoutes", ("token_iq/gateway/proxy/_types.py",), "identifier"),
    ],
)
def test_the_phase_that_owns_a_name_is_read_from_where_it_is_written(
    identifier: str, where: tuple[str, ...], expected: str
) -> None:
    assert classify(identifier, where) == expected


def test_a_table_named_in_python_still_belongs_to_the_database_phase() -> None:
    """Most table names also appear in a .prisma file, so the schema rule would claim them anyway.
    A raw SQL string or a Prisma accessor inside Python is the case only the name itself decides,
    and getting it wrong renames a table reference in phase 6 while the table keeps its old name."""
    assert classify("LiteLLM_SpendLogs", ("token_iq/repositories/gap_repository.py",)) == "database model"


def test_an_env_var_is_not_mistaken_for_a_class_that_merely_shouts() -> None:
    """A screaming identifier that is not an environment variable still belongs to phase 6."""
    assert classify("LITELLM_MASTER_KEY", ("token_iq/gateway/proxy/proxy_server.py",)) == "env var"
    assert classify("LiteLLM", ("token_iq/gateway/__init__.py",)) == "identifier"


def test_the_census_fixture_is_not_renamed_because_it_is_what_a_gate_greps_for() -> None:
    """tests/code_coverage_tests/test_inventory_census.py holds the spellings on purpose. Renaming
    them would leave the gate passing against names that no longer exist."""
    where = ("tests/code_coverage_tests/test_inventory_census.py",)
    assert classify("LiTeLlM", where) == "census fixture"


def test_a_name_in_two_places_is_not_claimed_by_the_census_fixture() -> None:
    where = ("tests/code_coverage_tests/test_inventory_census.py", "token_iq/gateway/__init__.py")
    assert classify("LiteLLM", where) == "identifier"


@pytest.mark.parametrize("path", ["LICENSE", "NOTICE", "CHANGELOG.md"])
def test_the_three_files_the_licence_requires_are_never_counted(path: str) -> None:
    """Deleting the name from these is a licence violation rather than a completed rename. See
    docs/decisions/0023-remove-litellm-names.md."""
    assert excluded(path) is True


@pytest.mark.parametrize(
    "path", ["docs/decisions/0001-observer-only.md", "docs/plans/2026-10-04-independent-codebase.md"]
)
def test_the_historical_record_is_never_counted(path: str) -> None:
    assert excluded(path) is True


@pytest.mark.parametrize("path", ["token_iq/gateway/__init__.py", "schema.prisma", "docs/status.md"])
def test_everything_else_is_counted(path: str) -> None:
    assert excluded(path) is False
