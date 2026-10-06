from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from token_iq.gateway.proxy._types import GatewayUserRoles, UserAPIKeyAuth
from token_iq.api.audit_logs import list_audit_logs


def _prisma_with_no_rows() -> MagicMock:
    client = MagicMock()
    client.db.litellm_auditlog.count = AsyncMock(return_value=0)
    client.db.litellm_auditlog.find_many = AsyncMock(return_value=[])
    return client


async def _list_as(role: GatewayUserRoles):
    with patch("token_iq.gateway.proxy.proxy_server.prisma_client", _prisma_with_no_rows()):
        return await list_audit_logs(
            user_api_key_dict=UserAPIKeyAuth(user_role=role),
            table_name=None,
            action=None,
            object_id=None,
            changed_by=None,
            start_date=None,
            end_date=None,
            page=1,
            size=50,
            include_noise=False,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [GatewayUserRoles.PROXY_ADMIN, GatewayUserRoles.PROXY_ADMIN_VIEW_ONLY])
async def test_admins_can_read_the_audit_trail(role):
    response = await _list_as(role)

    assert response.entries == []
    assert response.total == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [GatewayUserRoles.ORG_ADMIN, GatewayUserRoles.INTERNAL_USER, GatewayUserRoles.INTERNAL_USER_VIEW_ONLY],
)
async def test_the_installation_wide_audit_trail_is_refused_to_everyone_else(role):
    with pytest.raises(HTTPException) as refused:
        await _list_as(role)

    assert refused.value.status_code == 403
