"""Which data a caller may read, decided from their own identity rather than from a parameter.

A role decides which pages and actions a person has; a scope decides which data they see. They are
not the same thing, and the blueprint is explicit about where a scope applies: every page, tab,
export, scheduled report, assistant answer, API call and MCP query.

**Measured on 13 Oct 2026, before writing any of this:** every Token IQ endpoint that returns money
is proxy-admin-only, through twelve copies of the same three-line check with twelve different
refusal messages. So there is no scope leak today, because there is no scoped caller: the only
identity these endpoints admit already sees everything. The risk is the other direction, and it
arrives the moment a non-admin role is admitted to any of them. A filter applied in the browser over
an endpoint that returns everything is not a scope, and the way to tell the difference is to call
the endpoint directly with another team's id.

So this module answers the scope question once, as a value, and every endpoint says which scopes it
accepts. The scope is read from the caller's identity. A request that names a team is checked
against that identity and refused when it disagrees, rather than quietly narrowed, because a silent
narrowing teaches a caller that the parameter works.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, TypeAlias, assert_never

from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth

__all__: Final = (
    "NoAccess",
    "OneTeam",
    "OnlySelf",
    "Scope",
    "ScopeRefused",
    "WholeOrganisation",
    "readable_scope",
    "refusal_message",
    "scope_for_team",
    "scope_of",
)


@dataclass(frozen=True, slots=True)
class WholeOrganisation:
    """Every team, every project, every person. What an owner, an admin and an org admin have."""

    kind: Literal["organisation"] = "organisation"


@dataclass(frozen=True, slots=True)
class OneTeam:
    """One team's data and no other team's. What both Team Lead roles will have."""

    team_id: str
    kind: Literal["team"] = "team"


@dataclass(frozen=True, slots=True)
class OnlySelf:
    """This person's own usage. What a Team Member has, and what an internal user has today."""

    user_id: str
    kind: Literal["self"] = "self"


@dataclass(frozen=True, slots=True)
class NoAccess:
    """Not a person who reads Token IQ at all, with the reason said out loud."""

    reason: str
    kind: Literal["none"] = "none"


Scope: TypeAlias = WholeOrganisation | OneTeam | OnlySelf | NoAccess


def scope_of(identity: UserAPIKeyAuth) -> Scope:
    """The widest data this caller may read, from their identity alone.

    Never from a query parameter. A caller who could widen their own scope by asking has no scope,
    and that mistake does not throw: it answers with somebody else's spend.
    """
    role: Final = identity.user_role
    if role in (
        GatewayUserRoles.PROXY_ADMIN,
        GatewayUserRoles.PROXY_ADMIN_VIEW_ONLY,
        GatewayUserRoles.ORG_ADMIN,
    ):
        return WholeOrganisation()
    if role in (GatewayUserRoles.INTERNAL_USER, GatewayUserRoles.INTERNAL_USER_VIEW_ONLY):
        user_id: Final = identity.user_id
        if user_id is None:
            return NoAccess("This key names no user, so there is no own usage to show.")
        return OnlySelf(user_id)
    if role == GatewayUserRoles.TEAM:
        team_id: Final = identity.team_id
        if team_id is None:
            return NoAccess("This key names no team, so there is no team's data to show.")
        return OneTeam(team_id)
    return NoAccess("This caller is not a Token IQ reader.")


@dataclass(frozen=True, slots=True)
class ScopeRefused:
    """A caller asked for data their identity does not cover, and the answer is no."""

    message: str


ADMITTED_TODAY: Final[frozenset[GatewayUserRoles]] = frozenset({GatewayUserRoles.PROXY_ADMIN})
"""The roles every money endpoint admits, which is one.

Not the same question as `scope_of`. An admin viewer and an org admin do read the whole
organisation, and the sidebar already offers them these pages, but every endpoint behind them
refuses anything that is not the proxy admin, so those two roles see an entry and then an error.
That is a real defect and it is recorded in `docs/status.md` rather than fixed here: widening an
endpoint is a grant, and a grant is the owner's decision. Changing this one set is how it is made,
once, instead of in twelve places.
"""


def readable_scope(identity: UserAPIKeyAuth, *, subject: str) -> WholeOrganisation | ScopeRefused:
    """The scope for an endpoint that only answers organisation-wide questions.

    Every money endpoint is one of these today, and each one carried its own copy of the rule. The
    copies are the problem this replaces: twelve places to widen, and widening one of them by
    accident is a grant nobody sees. An endpoint that later answers a team's question asks for the
    scope itself and filters where it reads, rather than this.
    """
    if identity.user_role not in ADMITTED_TODAY:
        return ScopeRefused(f"Only a proxy admin may read or change {subject}, which covers every team.")
    return WholeOrganisation()


def scope_for_team(identity: UserAPIKeyAuth, asked: str | None) -> Scope | ScopeRefused:
    """The scope for a request that names a team, which must agree with the caller's identity.

    A parameter that disagrees is refused rather than narrowed. Narrowing silently would answer a
    request for another team's spend with this team's, which reads as a working filter and is how a
    caller learns to trust a parameter that decides nothing.
    """
    scope: Final = scope_of(identity)
    if asked is None:
        return scope
    match scope:
        case WholeOrganisation():
            return OneTeam(asked)
        case OneTeam(team_id=team_id):
            if team_id == asked:
                return scope
            return ScopeRefused("This key reads one team's data, and that is not the team it was asked for.")
        case OnlySelf():
            return ScopeRefused("This key reads its own usage, so it cannot be asked for a team's.")
        case NoAccess(reason=reason):
            return ScopeRefused(reason)
        case _:  # pyright: ignore[reportUnnecessaryComparison]  # the union is closed; this is the assert_never arm
            assert_never(scope)


def refusal_message(refused: ScopeRefused) -> str:
    """The one place a refusal becomes text, so twelve endpoints cannot word it twelve ways."""
    return refused.message
