"""Translating a team's permitted models into the names a courier request uses.

A team's `models` list holds this gateway's deployment names, for example
`openrouter/openai/gpt-4o-mini`. A courier request names the provider's own model,
`openai/gpt-4o-mini`, because the body is the provider's own and never mentions our
deployment.

So a permission written for translating mode stops matching the moment a team is switched
to courier, and every call is refused as `team_model_access_denied` naming a model the
admin can see plainly granted. It reads as a broken permission system rather than a naming
mismatch, and it is not something an operator can be expected to work out.

This maps one to the other by looking up what each permitted deployment actually points at,
so the permission an admin wrote keeps meaning what they meant in both modes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final


def _provider_model_of(litellm_params: Mapping[str, object]) -> str | None:
    """The provider's own name for what a deployment points at.

    `openrouter/openai/gpt-4o-mini` is addressed on the courier route as
    `openai/gpt-4o-mini`: the provider prefix is how we reach the provider, not part of
    what the provider calls the model.
    """
    model: Final = litellm_params.get("model")
    if not isinstance(model, str) or "/" not in model:
        return None
    return model.split("/", 1)[1]


def permitted_provider_models(
    permitted_deployments: Sequence[str],
    deployments: Sequence[Mapping[str, object]],
) -> frozenset[str]:
    """Provider-side model names a caller granted these deployments may address.

    A wildcard grant passes through untouched: it already means everything, in either
    naming scheme.
    """
    if not permitted_deployments:
        return frozenset()
    if "*" in permitted_deployments:
        return frozenset({"*"})

    granted: Final = frozenset(permitted_deployments)
    return frozenset(
        provider_model
        for deployment in deployments
        if isinstance(name := deployment.get("model_name"), str)
        and name in granted
        and isinstance(params := deployment.get("litellm_params"), Mapping)
        and (provider_model := _provider_model_of(params)) is not None
    )
