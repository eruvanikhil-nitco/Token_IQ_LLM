"""Which way a team's applications are allowed to reach the models.

A request is translated or not according to the address it arrives at, never according to
a team setting: the shared address repackages the body into the provider's format, and a
provider's own address passes it through unread. This setting cannot change that. It
decides only which of those addresses a team may use.

Three answers are useful, and a boolean could express only two:

`both` lets a team use either, so it can move one application at a time instead of
migrating everything on the day someone flips a switch. It is the default because it is
what a team without an opinion had before this setting existed.

`courier` closes the shared address, so every request from the team is provably one the
gateway never opened. A customer who is buying that promise wants it enforced rather than
intended.

`translator` closes the provider addresses, for a team that should only ever speak the
one common format.

Only the model-serving routes are gated. An earlier version of this refused everything
that was not a provider address, which locked a courier team's own keys out of
`/team/info`, `/key/info` and `/models`, since those are not provider addresses either.
Access to a provider address is separately granted by `allowed_passthrough_routes`; this
narrows what the team may reach, it never widens it.
"""

from __future__ import annotations

from typing import Final

from fastapi import status

from litellm.proxy._types import LiteLLMRoutes, ProxyErrorTypes, ProxyException
from token_iq.types.team_api_access import DEFAULT_API_ACCESS_MODE as DEFAULT_API_ACCESS_MODE
from token_iq.types.team_api_access import TeamApiAccessMode as TeamApiAccessMode

_COURIER_REFUSAL: Final = (
    "This team is set to courier mode, where request bodies reach the provider unread. "
    "{route} translates the body into the provider's format, so it is closed for this "
    "team. Send the provider's own request shape to its pass-through address instead, "
    "for example /anthropic/v1/messages or /openrouter/chat/completions."
)

_TRANSLATOR_REFUSAL: Final = (
    "This team is set to translating mode, where requests are written in one common "
    "format and this gateway converts them. {route} passes the body to the provider "
    "unread, so it is closed for this team. Send the common format to "
    "/v1/chat/completions instead."
)


def is_pass_through_route(route: str) -> bool:
    """Whether this address hands the body to the provider unread.

    Read off the same list the request path gates on, so the two cannot disagree.
    """
    return any(route.startswith(prefix) for prefix in LiteLLMRoutes.mapped_pass_through_routes.value)


def _serves_a_model(route: str) -> bool:
    """Whether this address is one a caller sends a model request to.

    Management, health and info addresses are not gated by this setting at all: which way
    a team writes its model requests says nothing about whether it may read its own key,
    or list the models it is allowed. `/models` and `/model/info` count as reading, which
    is why the info routes are excluded before anything else is considered.
    """
    if route in LiteLLMRoutes.info_routes.value:  # pyright: ignore[reportOperatorIssue]  # route enum values are untyped
        return False
    if is_pass_through_route(route):
        return True
    return any(
        route == known or route.startswith(f"{known}/")
        for known in LiteLLMRoutes.llm_api_routes.value  # pyright: ignore[reportAny]  # route enum values are untyped
    )


def assert_route_allowed(mode: TeamApiAccessMode, route: str) -> None:
    """Raise when this team may not use this address. Silence means allowed."""
    if mode == "both" or not _serves_a_model(route):
        return

    pass_through: Final = is_pass_through_route(route)
    if mode == "courier" and pass_through:
        return
    if mode == "translator" and not pass_through:
        return

    raise ProxyException(
        message=(_COURIER_REFUSAL if mode == "courier" else _TRANSLATOR_REFUSAL).format(route=route),
        type=ProxyErrorTypes.auth_error,
        param="route",
        code=status.HTTP_403_FORBIDDEN,
    )
