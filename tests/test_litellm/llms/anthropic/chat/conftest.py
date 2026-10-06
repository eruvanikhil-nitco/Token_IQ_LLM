"""Force ``litellm.model_cost`` to load from the PR-local JSON for these tests.

By default ``litellm.model_cost`` is fetched from the main branch on GitHub,
which lags behind PR-branch flag additions. This fixture loads the local
file so per-model flag tests pass in CI as well as locally.
See https://github.com/BerriAI/litellm/issues/27122.
"""

import pytest

from token_iq import gateway
from token_iq.gateway.core_utils.get_model_cost_map import get_model_cost_map


@pytest.fixture(autouse=True)
def _use_pr_local_model_cost_map(monkeypatch):
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setattr(
        gateway,
        "model_cost",
        get_model_cost_map(),
    )
    yield
