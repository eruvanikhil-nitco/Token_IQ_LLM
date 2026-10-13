"""A caller's scope comes from their identity, and a parameter that disagrees is refused.

The failure these guard is silent in the worst way: a scope read from a query parameter answers a
request for another team's spend with that team's spend, and every screen keeps working. The second
failure is quieter still, a parameter that is narrowed instead of refused, because then the caller
learns to trust a filter that decides nothing.
"""

from __future__ import annotations

from typing import Final

import pytest

from token_iq.access.scope import (
    NoAccess,
    OneTeam,
    OnlySelf,
    ScopeRefused,
    WholeOrganisation,
    readable_scope,
    scope_for_team,
    scope_of,
)
from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth


def _identity(
    role: GatewayUserRoles | None,
    *,
    user_id: str | None = "u-1",
    team_id: str | None = "t-1",
) -> UserAPIKeyAuth:
    return UserAPIKeyAuth(user_role=role, user_id=user_id, team_id=team_id, token="hashed")


@pytest.mark.parametrize(
    "role",
    (GatewayUserRoles.PROXY_ADMIN, GatewayUserRoles.PROXY_ADMIN_VIEW_ONLY, GatewayUserRoles.ORG_ADMIN),
)
def test_an_administrator_reads_the_whole_organisation(role: GatewayUserRoles) -> None:
    assert scope_of(_identity(role)) == WholeOrganisation()


@pytest.mark.parametrize("role", (GatewayUserRoles.INTERNAL_USER, GatewayUserRoles.INTERNAL_USER_VIEW_ONLY))
def test_an_internal_user_reads_only_their_own_usage(role: GatewayUserRoles) -> None:
    assert scope_of(_identity(role)) == OnlySelf("u-1")


def test_a_team_key_reads_one_team() -> None:
    assert scope_of(_identity(GatewayUserRoles.TEAM)) == OneTeam("t-1")


def test_a_role_nobody_mapped_reads_nothing() -> None:
    """The fail-closed direction. An unknown role must not fall through to the widest scope, which
    is how a scope decision grants by accident."""
    scope: Final = scope_of(_identity(GatewayUserRoles.CUSTOMER))

    assert isinstance(scope, NoAccess)
    assert scope.reason


def test_no_role_at_all_reads_nothing() -> None:
    assert isinstance(scope_of(_identity(None)), NoAccess)


def test_a_team_key_with_no_team_reads_nothing_rather_than_everything() -> None:
    scope: Final = scope_of(_identity(GatewayUserRoles.TEAM, team_id=None))

    assert isinstance(scope, NoAccess)
    assert "team" in scope.reason


def test_an_internal_user_with_no_user_id_reads_nothing() -> None:
    assert isinstance(scope_of(_identity(GatewayUserRoles.INTERNAL_USER, user_id=None)), NoAccess)


def test_an_organisation_wide_endpoint_admits_the_proxy_admin() -> None:
    assert readable_scope(_identity(GatewayUserRoles.PROXY_ADMIN), subject="the ledger") == WholeOrganisation()


@pytest.mark.parametrize("role", (GatewayUserRoles.PROXY_ADMIN_VIEW_ONLY, GatewayUserRoles.ORG_ADMIN))
def test_the_other_two_organisation_wide_roles_are_still_refused(role: GatewayUserRoles) -> None:
    """Today's rule, kept exactly. Both of these read the whole organisation and the sidebar already
    offers them these pages, so they see an entry and then an error, which is a defect. Fixing it
    means admitting a role that is refused today, and admitting a role is a grant."""
    assert isinstance(readable_scope(_identity(role), subject="the ledger"), ScopeRefused)


@pytest.mark.parametrize(
    "role",
    (
        GatewayUserRoles.INTERNAL_USER,
        GatewayUserRoles.INTERNAL_USER_VIEW_ONLY,
        GatewayUserRoles.TEAM,
        GatewayUserRoles.CUSTOMER,
        None,
    ),
)
def test_an_organisation_wide_endpoint_refuses_everyone_else(role: GatewayUserRoles | None) -> None:
    refused: Final = readable_scope(_identity(role), subject="the ledger")

    assert isinstance(refused, ScopeRefused)
    assert "the ledger" in refused.message


def test_the_refusal_names_the_endpoint_it_came_from() -> None:
    """Twelve copies of this rule worded it twelve ways. One function with a subject keeps what the
    caller needs to know and leaves one place to change."""
    ledger: Final = readable_scope(_identity(GatewayUserRoles.TEAM), subject="the ledger")
    rates: Final = readable_scope(_identity(GatewayUserRoles.TEAM), subject="the rates")

    assert isinstance(ledger, ScopeRefused)
    assert isinstance(rates, ScopeRefused)
    assert ledger.message != rates.message


def test_an_administrator_may_ask_for_any_team() -> None:
    assert scope_for_team(_identity(GatewayUserRoles.PROXY_ADMIN), "t-9") == OneTeam("t-9")


def test_a_team_key_may_ask_for_its_own_team() -> None:
    assert scope_for_team(_identity(GatewayUserRoles.TEAM), "t-1") == OneTeam("t-1")


def test_a_team_key_asking_for_another_team_is_refused_rather_than_narrowed() -> None:
    """The one that matters. Narrowing would answer the request with this team's figures, which
    looks like a working filter and is how a caller comes to trust a parameter that decides
    nothing."""
    answer: Final = scope_for_team(_identity(GatewayUserRoles.TEAM), "t-2")

    assert isinstance(answer, ScopeRefused)
    assert answer != OneTeam("t-1")


def test_a_person_who_reads_their_own_usage_cannot_ask_for_a_team() -> None:
    assert isinstance(scope_for_team(_identity(GatewayUserRoles.INTERNAL_USER), "t-1"), ScopeRefused)


def test_asking_for_no_team_leaves_the_identity_scope_as_it_is() -> None:
    assert scope_for_team(_identity(GatewayUserRoles.TEAM), None) == OneTeam("t-1")
    assert scope_for_team(_identity(GatewayUserRoles.PROXY_ADMIN), None) == WholeOrganisation()


def test_a_caller_with_no_access_is_refused_with_their_own_reason() -> None:
    answer: Final = scope_for_team(_identity(GatewayUserRoles.CUSTOMER), "t-1")

    assert isinstance(answer, ScopeRefused)
    assert answer.message == "This caller is not a Token IQ reader."
