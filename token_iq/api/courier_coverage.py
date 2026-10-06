"""What a provider actually does in courier mode, derived rather than declared.

An admin switching a team to courier needs to know which of that team's providers will
carry traffic correctly and which will carry it while recording no cost. A hand-written
table answering that drifts from the code and then lies, and a coverage report that lies
is worse than none, because it is believed.

So both halves are read from the same places the request path reads them.

Whether a courier route exists comes from ``LiteLLMRoutes.mapped_pass_through_routes``,
the list the request path itself gates on, so the two cannot disagree.

Whether usage is read back has two mechanisms today and a provider is covered by either.
Some providers carry a ``BasePassthroughConfig`` that overrides
``logging_non_streaming_response``; the rest are priced by a branch in the success
handler's dispatch. The dispatch branches are recovered from its own source, so adding a
provider there without teaching this module about it fails
``test_every_pricing_branch_in_the_dispatch_is_accounted_for`` instead of silently
reporting that provider as free.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from token_iq.gateway.proxy._types import LiteLLMRoutes

# Dispatch predicates whose derived name is not the route prefix. Everything else
# reduces mechanically: `is_anthropic_route` -> `anthropic`.
_PREDICATE_ALIASES: Final[dict[str, str]] = {
    "vertex": "vertex_ai",
    "vertex_ai_live": "vertex_ai",
    "comprehend_medical": "comprehendmedical",
}

# Azure OpenAI deployments are recognised by the OpenAI branch, which matches their
# hostnames rather than carrying a branch of their own.
_PRICED_BY_ANOTHERS_BRANCH: Final[dict[str, str]] = {
    "azure": "openai",
    "azure_ai": "openai",
}


@dataclass(frozen=True, slots=True)
class ProviderCourierCoverage:
    provider: str
    has_route: bool
    reads_usage: bool

    @property
    def is_covered(self) -> bool:
        return self.has_route and self.reads_usage

    @property
    def summary(self) -> str:
        """Deliberately says what the code supports, not that anyone has seen it work.

        This is read from the request path, so it is accurate about which code paths
        exist. It cannot tell whether a provider has ever carried a real request and had
        its spend reconciled, and a provider can be fully wired and still be wrong: the
        OpenRouter reader looked complete and recorded zero cost until real traffic went
        through it. The wording keeps that distinction visible rather than implying a
        guarantee this module cannot make.
        """
        if self.is_covered:
            return "Supported: the courier route exists and usage is read back for billing."
        if not self.has_route:
            return "No courier route. This provider cannot be used in courier mode."
        return "Carries traffic but records no cost. Spend for this provider would be missing."


def pricing_branch_providers() -> tuple[str, ...]:
    """Providers priced by a branch in the success handler's dispatch, read from its source."""
    from token_iq.gateway.proxy.pass_through_endpoints.success_handler import PassThroughEndpointLogging

    source: Final = inspect.getsource(PassThroughEndpointLogging.normalize_llm_passthrough_logging_payload)
    derived: Final = {
        _PREDICATE_ALIASES.get(stem, stem)
        for stem in (
            match.removeprefix("is_").removesuffix("_route") for match in re.findall(r"self\.(is_\w+)\(", source)
        )
    }
    return tuple(sorted(derived))


def _has_config_usage_reader(provider: str) -> bool:
    from token_iq.gateway.llms.base_llm.passthrough.transformation import BasePassthroughConfig
    from token_iq.gateway.types.utils import LlmProviders
    from token_iq.gateway.utils import ProviderConfigManager

    try:
        config: Final = ProviderConfigManager.get_provider_passthrough_config(
            provider=LlmProviders(provider),
            model="",
        )
    except ValueError:
        return False
    if config is None:
        return False
    return type(config).logging_non_streaming_response is not BasePassthroughConfig.logging_non_streaming_response


def provider_courier_coverage(provider: str) -> ProviderCourierCoverage:
    priced_under: Final = _PRICED_BY_ANOTHERS_BRANCH.get(provider, provider)
    return ProviderCourierCoverage(
        provider=provider,
        has_route=f"/{provider}" in LiteLLMRoutes.mapped_pass_through_routes.value,
        reads_usage=priced_under in pricing_branch_providers() or _has_config_usage_reader(provider),
    )


def providers_of(deployments: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    """The providers these deployments actually reach.

    A deployment's model is written `provider/their-model-name`, and the prefix is how we
    reach the provider rather than part of what the provider calls the model.
    """
    return tuple(
        sorted(
            {
                model.split("/", 1)[0]
                for deployment in deployments
                if isinstance(params := deployment.get("litellm_params"), Mapping)
                and isinstance(model := params.get("model"), str)
                and "/" in model
            }
        )
    )
