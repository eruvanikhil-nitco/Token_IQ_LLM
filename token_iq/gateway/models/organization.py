"""
Organization table model.

Canonical definition for ``litellm_organizationtable``. Re-exported from
``litellm.proxy._types`` for backwards compatibility.
"""

from token_iq.gateway.models.budget import LiteLLM_BudgetTable
from token_iq.gateway.models.object_permission import LiteLLM_ObjectPermissionTable
from token_iq.gateway.models.user import LiteLLM_UserTable
from token_iq.gateway.types.llms.base import LiteLLMPydanticObjectBase


class LiteLLM_OrganizationTable(LiteLLMPydanticObjectBase):
    """Represents user-controllable params for a LiteLLM_OrganizationTable record"""

    organization_id: str | None = None
    organization_alias: str | None = None
    budget_id: str
    spend: float = 0.0
    metadata: dict | None = None
    models: list[str] = []
    model_spend: dict | None = {}
    created_by: str
    updated_by: str
    users: list[LiteLLM_UserTable] | None = None
    litellm_budget_table: LiteLLM_BudgetTable | None = None
    object_permission: LiteLLM_ObjectPermissionTable | None = None
    object_permission_id: str | None = None
