"""Tests for scripts/rename/rename_metric_names.py.

A metric name is what a customer's dashboards and alert rules query, so this rename breaks them on purpose
and the upgrade notes have to name every one. The failure to guard against is a name the pass does not know
about: the engine emits it under the new prefix, the notes never mention it, and the customer is left with a
panel that reads zero and nothing saying why.

The second failure is quieter. Prometheus appends `_total` to a counter when it exposes it, and a word
boundary does not fall between `metric` and `_total`, so a pass matching only the bare name reports every
file done while leaving every dashboard query behind.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_metric_names.py"
_spec = importlib.util.spec_from_file_location("rename_metric_names", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_metric_names = importlib.util.module_from_spec(_spec)
sys.modules["rename_metric_names"] = rename_metric_names
_spec.loader.exec_module(rename_metric_names)

SOME = ("litellm_request_total_latency_metric", "litellm_spend_metric", "litellm_active_users")


def moved(text: str, names: tuple[str, ...] = SOME) -> str:
    found, _count = rename_metric_names.rewrite(text, names)
    return found


# --- the names themselves ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('name="litellm_spend_metric"', 'name="token_iq_spend_metric"'),
        ("self.litellm_spend_metric.labels()", "self.token_iq_spend_metric.labels()"),
        ("litellm_active_users", "token_iq_active_users"),
        ('get_labels_for_metric("litellm_spend_metric")', 'get_labels_for_metric("token_iq_spend_metric")'),
    ],
)
def test_a_metric_moves_wherever_it_is_named(before: str, after: str) -> None:
    """The metric and the attribute holding it are the same token, so they move together."""
    assert moved(before) == after


@pytest.mark.parametrize("suffix", ["_total", "_bucket", "_sum", "_count", "_created"])
def test_what_prometheus_appends_is_kept(suffix: str) -> None:
    """This is the form a dashboard queries. A word boundary does not fall between `metric` and `_total`."""
    assert moved(f"sum(rate(litellm_spend_metric{suffix}[5m]))") == f"sum(rate(token_iq_spend_metric{suffix}[5m]))"


@pytest.mark.parametrize(
    "value",
    ["litellm_params", "litellm_settings", "litellm_metadata", "litellm_provider", "litellm_teamtable"],
)
def test_something_that_is_not_a_metric_is_left_alone(value: str) -> None:
    """A config key, a metadata key and a Prisma accessor. None of them is in the set, which is what makes a
    text pass safe here, and `clashes` is what checks that before anything moves."""
    assert moved(f'x = "{value}"') == f'x = "{value}"'


def test_a_longer_name_is_not_eaten_by_a_shorter_one() -> None:
    """None of the 82 is a prefix of another today, so the alternation is ordered longest first to keep that
    from mattering if one ever is."""
    names = ("litellm_queue_size_metric", "litellm_queue_size")

    assert moved("litellm_queue_size_metric", names) == "token_iq_queue_size_metric"
    assert moved("litellm_queue_size", names) == "token_iq_queue_size"


def test_the_runtime_family_moves_as_one() -> None:
    """`prometheus_services` builds a name per service and request type, so the template is the only place
    that family can be renamed."""
    before = '    metric_name: Final = f"litellm_{service}_{type_of_request}"\n'

    assert moved(before) == '    metric_name: Final = f"token_iq_{service}_{type_of_request}"\n'


# --- the dashboards --------------------------------------------------------------------------------


def test_a_dashboard_renames_every_metric_reference() -> None:
    """In a Grafana dashboard every `litellm_…` token is a metric, including the forms Prometheus derived
    and the family built at runtime, neither of which the constructor scan can see."""
    before = '"expr": "sum(litellm_self_latency_bucket) + litellm_remaining_requests"'

    found, count = rename_metric_names.rewrite(before, SOME, grafana=True)

    assert found == '"expr": "sum(token_iq_self_latency_bucket) + token_iq_remaining_requests"'
    assert count == 2


def test_a_dashboard_is_the_only_place_an_unknown_name_moves() -> None:
    """Outside one, a name the engine does not construct is something else and stays."""
    assert moved('x = "litellm_remaining_requests"') == 'x = "litellm_remaining_requests"'


# --- where the set comes from ------------------------------------------------------------------------


def test_the_metrics_are_read_out_of_the_constructor_calls() -> None:
    """Listed here the set would drift, and a metric the code emits that the notes never mention is a
    dashboard a customer cannot fix."""
    names = rename_metric_names.every_metric()

    assert "token_iq_spend_metric" in names
    assert "token_iq_proxy_total_requests_metric" in names
    assert "litellm_params" not in names
    assert len(names) == 82


def test_no_metric_is_still_named_with_the_old_prefix() -> None:
    """The invariant the rename leaves behind, and what makes a later run a no-op rather than a disaster."""
    assert rename_metric_names.metric_names() == ()


def test_the_set_is_ordered_longest_first() -> None:
    """So a shorter name cannot eat a longer one that starts with it. Said against a synthetic pair, because
    none of the real 82 is a prefix of another."""
    assert (
        rename_metric_names.rewrite("litellm_queue_size_metric", ("litellm_queue_size_metric", "litellm_queue_size"))[0]
        == "token_iq_queue_size_metric"
    )

    names = rename_metric_names.every_metric()
    assert [len(name) for name in names] == sorted((len(name) for name in names), reverse=True)


def test_no_metric_shares_a_name_with_anything_else() -> None:
    """The precondition for renaming by text rather than by syntax tree. The pass refuses to run otherwise."""
    assert rename_metric_names.clashes() == ()


# --- scope ------------------------------------------------------------------------------------------


def test_the_records_and_the_built_dashboard_are_out_of_scope() -> None:
    listed = {rename_metric_names.named(path) for path in rename_metric_names.tracked()}

    assert "docs/status.md" not in listed
    assert "CHANGELOG.md" not in listed
    assert not any(name.startswith("token_iq/gateway/proxy/_experimental/out/") for name in listed)
    assert "token_iq/gateway/integrations/prometheus.py" in listed, "the filter is too wide"


def test_this_pass_and_its_tests_are_out_of_scope() -> None:
    listed = {rename_metric_names.named(path) for path in rename_metric_names.tracked()}

    assert "scripts/rename/rename_metric_names.py" not in listed
    assert "tests/gateway/test_rename_metric_names.py" not in listed


def test_both_dashboards_in_the_repository_are_in_scope() -> None:
    """The plan asks for the dashboards here to move with the code, because a customer copies them."""
    listed = {rename_metric_names.named(path) for path in rename_metric_names.tracked()}

    assert sum(1 for name in listed if name.endswith("grafana_dashboard.json")) == 3


def test_a_run_with_nothing_left_to_rename_changes_nothing() -> None:
    """Which is what a second run is. An alternation of nothing matches the empty string at every position,
    so without this the pass reports fifteen million mentions and rewrites every file it is given."""
    found, count = rename_metric_names.rewrite('x = "anything at all"', ())

    assert (found, count) == ('x = "anything at all"', 0)
