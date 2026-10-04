"""
Tests for model-cost-map loading: the model-count integrity check (which must
count actual model entries, not reserved meta keys) and the extraction of the
``fallback_generalizations`` block out of the raw map.
"""

import json
import os

import pytest


from litellm.litellm_core_utils.fallback_generalizations import (
    get_fallback_generalization_rules,
    match_capability_generalizations,
    match_routing_generalization,
    set_fallback_generalizations,
)
from litellm.litellm_core_utils.get_model_cost_map import (
    FALLBACK_GENERALIZATIONS_KEY,
    GetModelCostMap,
    _count_model_entries,
    _finalize_model_cost_map,
)


def _load_root_cost_map() -> dict:
    """Superseded: there is one price file now, so this is the bundled one."""
    return GetModelCostMap.load_local_model_cost_map()


def _make_models(n: int) -> dict:
    return {
        f"model-{i}": {"litellm_provider": "openai", "mode": "chat"} for i in range(n)
    }


def test_count_model_entries_excludes_reserved_keys():
    m = _make_models(3)
    m["sample_spec"] = {"foo": "bar"}
    m[FALLBACK_GENERALIZATIONS_KEY] = {"rules": []}
    assert _count_model_entries(m) == 3


def test_validation_rejects_truly_shrunk_file_even_with_meta_keys():
    """A file with only a handful of real models must be rejected as corrupt,
    and the extra meta keys must not inflate the count past the minimum."""
    shrunk = _make_models(5)
    shrunk["sample_spec"] = {"foo": "bar"}
    shrunk[FALLBACK_GENERALIZATIONS_KEY] = {"rules": [{"name": "x"}]}

    assert (
        GetModelCostMap.validate_model_cost_map(
            fetched_map=shrunk,
            backup_model_count=2000,
            min_model_count=50,
        )
        is False
    )


def test_validation_accepts_healthy_file_with_meta_keys():
    healthy = _make_models(2000)
    healthy["sample_spec"] = {"foo": "bar"}
    healthy[FALLBACK_GENERALIZATIONS_KEY] = {"rules": []}

    assert (
        GetModelCostMap.validate_model_cost_map(
            fetched_map=healthy,
            backup_model_count=2000,
            min_model_count=50,
        )
        is True
    )


def test_validation_rejects_significant_shrink_vs_backup():
    # 600 real models vs a 2000-model backup is below the 50% shrink threshold.
    shrunk = _make_models(600)
    shrunk[FALLBACK_GENERALIZATIONS_KEY] = {"rules": []}
    assert (
        GetModelCostMap.validate_model_cost_map(
            fetched_map=shrunk,
            backup_model_count=2000,
            min_model_count=50,
            max_shrink_ratio=0.5,
        )
        is False
    )


def test_finalize_pops_key_and_installs_rules():
    previous = list(get_fallback_generalization_rules())
    try:
        raw = _make_models(2)
        raw[FALLBACK_GENERALIZATIONS_KEY] = {
            "rules": [
                {
                    "name": "rule",
                    "pattern": r"^widget-",
                    "model_info": {"litellm_provider": "openai"},
                }
            ]
        }
        finalized = _finalize_model_cost_map(raw)

        # The reserved key is removed from the returned model map ...
        assert FALLBACK_GENERALIZATIONS_KEY not in finalized
        # ... and its rules are installed into the generalizations module.
        assert match_routing_generalization("widget-9") == "openai"
    finally:
        set_fallback_generalizations(previous)


def test_finalize_with_no_block_clears_rules():
    previous = list(get_fallback_generalization_rules())
    try:
        set_fallback_generalizations(
            [{"name": "stale", "pattern": r"^x", "model_info": {"a": 1}}]
        )
        _finalize_model_cost_map(_make_models(2))
        assert match_capability_generalizations("x-1") is None
    finally:
        set_fallback_generalizations(previous)


def test_shipped_backup_carries_the_claude_routing_rules():
    """The bundled backup must ship the Claude routing rules so a fresh install
    (or an offline fallback) routes unknown Claude models without code changes.
    Bedrock-syntax ids must hit the bedrock rule before the bare-id Anthropic rule."""
    backup = GetModelCostMap.load_local_model_cost_map()
    rules = backup.get(FALLBACK_GENERALIZATIONS_KEY, {}).get("rules", [])
    names = [r.get("name") for r in rules]
    assert names.index("bedrock-claude-ids") < names.index("anthropic-claude-ids")

    previous = list(get_fallback_generalization_rules())
    try:
        set_fallback_generalizations(rules)
        assert match_routing_generalization("claude-opus-4-9") == "anthropic"
        assert match_routing_generalization("global.anthropic.claude-opus-4-9") == "bedrock"
    finally:
        set_fallback_generalizations(previous)


def test_shipped_routing_rules_never_match_through_an_unrecognized_namespace():
    """Routing rules decide ``litellm_provider`` for otherwise-unknown ids, and the
    proxy's wildcard access check (``can_key_call_model`` with a ``bedrock/*`` key)
    trusts that inference: it rebuilds ``{provider}/{model}`` and matches it against
    the key's patterns. A routing pattern that matches as a substring lets
    ``bedrockz/anthropic.claude-...`` resolve to bedrock and slip through a
    ``bedrock/*`` key, so every shipped routing rule must anchor to the start of
    the name and never match an id carrying an unrecognized namespace prefix."""
    backup = GetModelCostMap.load_local_model_cost_map()
    rules = backup[FALLBACK_GENERALIZATIONS_KEY]["rules"]

    routing_rules = [r for r in rules if "litellm_provider" in r["model_info"]]
    assert routing_rules
    assert all(r["pattern"].startswith("^") for r in routing_rules)

    previous = list(get_fallback_generalization_rules())
    try:
        set_fallback_generalizations(rules)
        for bedrock_id in [
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "anthropic.claude-v2:1",
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "us-gov.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "global.anthropic.claude-fable-5-20260120-v1:0",
        ]:
            assert match_routing_generalization(bedrock_id) == "bedrock", bedrock_id
        for namespaced in [
            "bedrockz/anthropic.claude-3-5-sonnet-20240620",
            "bedrockz/us.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "bedrockz/claude-3-5-sonnet-20240620",
        ]:
            assert match_routing_generalization(namespaced) is None, namespaced
    finally:
        set_fallback_generalizations(previous)


def test_shipped_backup_marks_claude_4_6_plus_adaptive_not_4_0():
    """Adaptive thinking is data, not code. The bundled backup must carry
    supports_adaptive_thinking on genuine Claude >= 4.6 entries (every provider
    route) and on the version-gated anthropic-claude-adaptive-thinking rule for
    unmapped future Claudes, while leaving the dated Claude 4.0 names
    ("...-4-20250514") unflagged so a date can never be mistaken for a 4.6+ minor
    version. The version-neutral claude-family-baseline capability rule must not flag
    it, so an unmapped sub-4.6 name resolves but stays non-adaptive. The adaptive rule
    carries only its delta; capability unioning stacks it onto the baseline, so the
    baseline block is never duplicated across rules and no rule needs ``extends``."""
    backup = GetModelCostMap.load_local_model_cost_map()

    rules = backup[FALLBACK_GENERALIZATIONS_KEY]["rules"]
    baseline_rule = next(r for r in rules if r.get("name") == "claude-family-baseline")
    adaptive_rule = next(r for r in rules if r.get("name") == "claude-adaptive-thinking")
    assert "supports_adaptive_thinking" not in baseline_rule["model_info"]
    assert "litellm_provider" not in baseline_rule["model_info"]
    assert adaptive_rule["model_info"] == {"supports_adaptive_thinking": True}
    assert all("extends" not in r for r in rules)

    for adaptive in [
        "anthropic.claude-opus-4-8",
        "vertex_ai/claude-opus-4-6@default",
        "us.anthropic.claude-sonnet-4-6",
        "openrouter/anthropic/claude-opus-4.7",
        "azure_ai/claude-opus-4-7",
    ]:
        assert backup[adaptive]["supports_adaptive_thinking"] is True, adaptive

    for non_adaptive in [
        "claude-opus-4-20250514",
        "us.anthropic.claude-opus-4-20250514-v1:0",
        "claude-opus-4-5",
    ]:
        assert "supports_adaptive_thinking" not in backup[non_adaptive], non_adaptive


@pytest.mark.parametrize(
    "cost_map",
    [GetModelCostMap.load_local_model_cost_map()],
    ids=["bundled"],
)
def test_azure_ai_claude_1m_context_entries(cost_map: dict):
    """Microsoft Foundry serves a 1M-token context window for Opus 4.6+ and Sonnet
    4.6+, so the ``azure_ai`` entries must not advertise the 200k cap that made
    context-aware clients compact prompts early (LIT-4406). Both the root map (used
    There used to be two copies checked here so they could not drift apart. There is now
    one file, which is a better answer to the same problem."""
    for model in [
        "azure_ai/claude-opus-4-6",
        "azure_ai/claude-opus-4-7",
        "azure_ai/claude-opus-4-8",
        "azure_ai/claude-opus-5",
        "azure_ai/claude-sonnet-5",
        "azure_ai/claude-sonnet-4-6",
    ]:
        assert cost_map[model]["max_input_tokens"] == 1000000, model

    for model in [
        "azure_ai/claude-opus-4-1",
        "azure_ai/claude-opus-4-5",
        "azure_ai/claude-sonnet-4-5",
        "azure_ai/claude-haiku-4-5",
    ]:
        assert cost_map[model]["max_input_tokens"] == 200000, model


def test_get_model_cost_map_stamps_loaded_at(monkeypatch):
    """The load time feeds each pod's reload-due decision; a load that does not stamp it
    would make manual reload requests race the proxy's startup"""
    from datetime import datetime, timezone

    from litellm.litellm_core_utils import get_model_cost_map as module

    monkeypatch.setattr(module._cost_map_source_info, "loaded_at", None)

    before = datetime.now(timezone.utc)
    module.get_model_cost_map()
    loaded_at = module.get_model_cost_map_loaded_at()

    assert loaded_at is not None
    assert before <= loaded_at <= datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# refetch_model_cost_map: retry/backoff behavior for runtime reloads
# ---------------------------------------------------------------------------

import functools
import random

import httpx

from litellm.litellm_core_utils.get_model_cost_map import (
    ModelCostMapReloaded,
    ModelCostMapReloadUnavailable,
    refetch_model_cost_map,
)

_URL = "https://example.invalid/model_prices.json"


@functools.lru_cache(maxsize=1)
def _real_map_bytes() -> bytes:
    return json.dumps(_load_root_cost_map()).encode()


class _SleepRecorder:
    """Injected in place of asyncio.sleep so tests assert waits without real delay."""

    def __init__(self):
        self.waits = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.fixture(autouse=True)
def _unset_local_cost_map_env(monkeypatch):
    """CI exports LITELLM_LOCAL_MODEL_COST_MAP=True; clear it so fetch behavior is deterministic."""
    monkeypatch.delenv("LITELLM_LOCAL_MODEL_COST_MAP", raising=False)


def _mock_client(outcomes, client_cls=httpx.AsyncClient):
    """httpx client over a MockTransport serving one outcome per request; an exception instance is raised."""
    calls = {"count": 0}

    def handler(request):
        idx = min(calls["count"], len(outcomes) - 1)
        calls["count"] += 1
        outcome = outcomes[idx]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return client_cls(transport=httpx.MockTransport(handler)), calls


class _SyncSleepRecorder:
    """Injected in place of time.sleep so the boot path's waits are asserted without delay."""

    def __init__(self):
        self.waits = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


class TestPricesAreLocalOnly:
    """Phase 2: the runtime reads the bundled price file and never reaches the network.

    This is the rule the whole price pipeline exists to protect. A stale price does not
    fail: nothing crashes, no test goes red, the ledger keeps reconciling, and every figure
    the product reports is quietly wrong for any model whose price moved. A fetch that
    survives anywhere means an installation behind a firewall silently serves whatever the
    last successful download left behind.
    """

    def test_loading_prices_opens_no_socket(self, monkeypatch):
        """The load-bearing test. If any fetch path survives, this fails."""
        import socket

        def refuse(*args, **kwargs):
            raise AssertionError("the price loader opened a socket; it must read the bundled file")

        monkeypatch.setattr(socket.socket, "connect", refuse)
        monkeypatch.setattr(socket.socket, "connect_ex", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)

        from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map

        loaded = get_model_cost_map()
        assert len(loaded) > 1000, "the bundled file should hold the full price list"

    def test_the_bundled_file_is_the_only_copy(self):
        """Two copies of 2.1MB kept in sync by convention diverge, and then which one a
        given code path reads becomes a coin toss nobody knows they are flipping."""
        import pathlib

        repo = pathlib.Path(__file__).resolve().parents[3]
        duplicates = [
            repo / "model_prices_and_context_window.json",
            repo / "litellm" / "model_prices_and_context_window_backup.json",
        ]
        present = [p for p in duplicates if p.exists()]
        assert not present, f"superseded price copies still on disk: {[p.name for p in present]}"
        assert (repo / "data" / "pricing" / "model_prices.json").is_file()

    def test_a_model_with_no_price_is_absent_rather_than_free(self):
        """A missing model must not read as zero. Zero turns real spend into free usage and
        nothing downstream can tell the difference."""
        from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map

        loaded = get_model_cost_map()
        assert "a-model-that-does-not-exist-anywhere" not in loaded

    def test_the_local_cost_map_switch_is_gone(self):
        """LITELLM_LOCAL_MODEL_COST_MAP chose between local and remote. Local is now the
        only mode, so a switch that appears to offer a choice is a lie."""
        import pathlib

        source = pathlib.Path(
            "litellm/litellm_core_utils/get_model_cost_map.py"
        ).read_text(encoding="utf-8")
        assert "LITELLM_LOCAL_MODEL_COST_MAP" not in source

    def test_no_upstream_url_remains_in_the_loader(self):
        import pathlib

        source = pathlib.Path(
            "litellm/litellm_core_utils/get_model_cost_map.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("raw.githubusercontent.com", "BerriAI"):
            assert forbidden not in source, f"{forbidden} still referenced by the price loader"
