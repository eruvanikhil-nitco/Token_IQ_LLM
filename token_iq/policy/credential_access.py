"""Who may read, create and change a stored credential.

A credential's owning team is recorded in `credential_info`, which the table already
carries as free-form JSON and which travels unchanged into the in-memory credential list
the router reads. A credential with no team belongs to the whole installation: a team
admin may use it, but may not edit or delete it, because it serves teams they do not run.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from pydantic import ValidationError

from token_iq.gateway._logging import verbose_proxy_logger
from token_iq.gateway.proxy._types import LiteLLM_TeamTable, GatewayUserRoles, UserAPIKeyAuth
from token_iq.gateway.proxy.management_endpoints.common_utils import _is_user_team_admin

CREDENTIAL_TEAM_KEY: Final = "team_id"


def credential_team(credential_info: Mapping[str, object] | None) -> str | None:
    """The team that owns this credential, or None when the installation does."""
    if credential_info is None:
        return None
    team: Final = credential_info.get(CREDENTIAL_TEAM_KEY)
    return team if isinstance(team, str) and team else None


def _validated_team_row(row: Any) -> LiteLLM_TeamTable | None:  # any-ok: PrismaClient row is untyped
    """A team row as a validated model, or None when the row itself is malformed."""
    dumped: Final = row.model_dump()
    try:
        return LiteLLM_TeamTable.model_validate(dumped)
    except ValidationError:
        verbose_proxy_logger.debug("Skipping malformed team row (team_id=%s)", dumped.get("team_id"))
        return None


async def teams_user_administers(
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: Any,  # any-ok: PrismaClient is an untyped runtime wrapper
) -> frozenset[str]:
    """Every team this caller is an admin of. Empty for a proxy admin, who needs no list."""
    if user_api_key_dict.user_role == GatewayUserRoles.PROXY_ADMIN:
        return frozenset()
    rows: Final = await prisma_client.db.litellm_teamtable.find_many()
    valid_teams: Final = (team for team in (_validated_team_row(row) for row in rows) if team is not None)
    return frozenset(
        team.team_id
        for team in valid_teams
        if _is_user_team_admin(user_api_key_dict=user_api_key_dict, team_obj=team)
    )


def may_read_credential(
    credential_info: Mapping[str, object] | None,
    *,
    is_admin: bool,
    administered_teams: frozenset[str],
) -> bool:
    """Whether this caller may see the credential at all."""
    if is_admin:
        return True
    if not administered_teams:
        return False
    owner: Final = credential_team(credential_info)
    return owner is None or owner in administered_teams


def may_change_credential(
    credential_info: Mapping[str, object] | None,
    *,
    is_admin: bool,
    administered_teams: frozenset[str],
) -> bool:
    """Whether this caller may edit or delete the credential."""
    if is_admin:
        return True
    owner: Final = credential_team(credential_info)
    return owner is not None and owner in administered_teams
