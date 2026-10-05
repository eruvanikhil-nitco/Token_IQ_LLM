"""Ask a provider what models its credentials can reach, and say which of those we can price.

The Add Model form's dropdown is built from `model_prices_and_context_window.json`, which
ships with the package. That file is a pricing catalogue, not an availability list, so it
lags: OpenRouter serves far more models than the file names, and names a few the provider
has since retired.

This module adds the second source. `get_valid_models(check_provider_endpoint=True, ...)`
already queries the provider with the operator's own credentials; nothing here re-implements
that. What is new is the merge: every discovered model is returned alongside whether the
local catalogue can price it.

Two states, not three, and the distinction matters. At discovery time we know only whether a
local pricing row exists. Whether the *provider* will report a cost is unknowable until a
request is actually made, so a model with no local row is reported as exactly that rather
than as "free". Recording what actually happened belongs on the spend log, not here.

See docs/decisions/0015-provider-model-discovery.md
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, Field

import litellm

# The catalogue keys these off the same names it prices by, so a row that carries neither
# is present for its metadata (context window, capabilities) rather than for billing.
_COST_FIELDS: Final = ("input_cost_per_token", "output_cost_per_token")


class DiscoveredModel(BaseModel):
    """One model the provider says these credentials can reach."""

    model_name: str = Field(description="The name to put in litellm_params.model, provider prefix included")
    has_local_pricing: bool = Field(description="Whether model_prices_and_context_window.json can price this model")
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None


class ModelDiscoveryResponse(BaseModel):
    """What a provider offers, and how much of it this build can price."""

    custom_llm_provider: str
    models: list[DiscoveredModel]  # writable-ok: FastAPI serialises the response model directly
    total: int = Field(description="Models the provider reported")
    priced: int = Field(description="Of those, how many the local catalogue can price")
    unpriced: int = Field(
        description=(
            "Of those, how many have no local price. Their cost will come from the provider's "
            "own usage reporting if it sends one, and will otherwise record as zero."
        )
    )


def _local_pricing(model_name: str) -> tuple[float | None, float | None]:
    """Input and output per-token cost from the shipped catalogue, or (None, None)."""
    entry: Final = litellm.model_cost.get(model_name)
    if not isinstance(entry, dict):
        return None, None
    costs: Final = tuple(entry.get(field) for field in _COST_FIELDS)
    return (
        costs[0] if isinstance(costs[0], (int, float)) else None,
        costs[1] if isinstance(costs[1], (int, float)) else None,
    )


def merge_with_local_pricing(
    *,
    custom_llm_provider: str,
    discovered_models: Sequence[str],
) -> ModelDiscoveryResponse:
    """Pair each discovered model with what the local catalogue knows about its price.

    Pure: takes the provider's answer rather than fetching it, so the merge is testable
    without a network call and the endpoint stays a thin wrapper.
    """
    priced_pairs: Final = tuple((name, _local_pricing(name)) for name in sorted(set(discovered_models)))
    merged: Final = tuple(
        DiscoveredModel(
            model_name=name,
            has_local_pricing=input_cost is not None or output_cost is not None,
            input_cost_per_token=input_cost,
            output_cost_per_token=output_cost,
        )
        for name, (input_cost, output_cost) in priced_pairs
    )
    priced: Final = sum(1 for model in merged if model.has_local_pricing)
    return ModelDiscoveryResponse(
        custom_llm_provider=custom_llm_provider,
        models=list(merged),
        total=len(merged),
        priced=priced,
        unpriced=len(merged) - priced,
    )
