"""
Passthrough table repositories.

Each repository centralizes access to a single Prisma table behind a ``table``
property, making the repository the one place that names the underlying table.
These are thin wrappers for tables that do not (yet) need domain-specific query
methods; richer repositories live in their own modules.
"""

from typing import TYPE_CHECKING, Any, Final, Generic

from token_iq.gateway.proxy.common_utils.config_sync_pubsub import wrap_table_actions_for_config_sync
from token_iq.gateway.repositories.prisma_protocols import RowT_co, TableActions

if TYPE_CHECKING:
    from prisma import models as prisma_models  # noqa: F401  # used by quoted base-class subscripts


class PrismaTableRepository(Generic[RowT_co]):
    """Base for repositories that expose a single Prisma table."""

    table_name: str

    def __init__(self, prisma_client: Any):
        self._prisma_client = prisma_client

    @property
    def prisma_client(self) -> Any:
        if self._prisma_client is None:
            raise RuntimeError("No database connected")
        return self._prisma_client

    @property
    def table(self) -> TableActions[RowT_co]:
        actions: Final[TableActions[RowT_co]] = getattr(self.prisma_client.db, self.table_name)
        return wrap_table_actions_for_config_sync(actions=actions, table_name=self.table_name)


class PolicyRepository(PrismaTableRepository["prisma_models.PolicyTable"]):
    table_name = "policytable"


class AgentsRepository(PrismaTableRepository["prisma_models.AgentsTable"]):
    table_name = "agentstable"


class ObjectPermissionRepository(PrismaTableRepository["prisma_models.ObjectPermissionTable"]):
    table_name = "objectpermissiontable"


class GuardrailsRepository(PrismaTableRepository["prisma_models.GuardrailsTable"]):
    table_name = "guardrailstable"


class MCPServerRepository(PrismaTableRepository["prisma_models.MCPServerTable"]):
    table_name = "mcpservertable"


class ManagedObjectRepository(PrismaTableRepository["prisma_models.ManagedObjectTable"]):
    table_name = "managedobjecttable"


class OrganizationMembershipRepository(PrismaTableRepository["prisma_models.OrganizationMembership"]):
    table_name = "organizationmembership"


class SpendLogsRepository(PrismaTableRepository["prisma_models.SpendLogs"]):
    table_name = "spendlogs"


class BudgetWindowSpendRepository(PrismaTableRepository["prisma_models.BudgetWindowSpend"]):
    table_name = "budgetwindowspend"


class ClaudeCodePluginRepository(PrismaTableRepository["prisma_models.ClaudeCodePluginTable"]):
    table_name = "claudecodeplugintable"


class TeamMembershipRepository(PrismaTableRepository["prisma_models.TeamMembership"]):
    table_name = "teammembership"


class EndUserRepository(PrismaTableRepository["prisma_models.EndUserTable"]):
    table_name = "endusertable"


class ManagedVectorStoresRepository(PrismaTableRepository["prisma_models.ManagedVectorStoresTable"]):
    table_name = "managedvectorstorestable"


class MCPUserCredentialsRepository(PrismaTableRepository["prisma_models.MCPUserCredentials"]):
    table_name = "mcpusercredentials"


class MCPServerOAuthClientRepository(PrismaTableRepository["prisma_models.MCPServerOAuthClient"]):
    table_name = "mcpserveroauthclient"


class PromptRepository(PrismaTableRepository["prisma_models.PromptTable"]):
    table_name = "prompttable"


class TagRepository(PrismaTableRepository["prisma_models.TagTable"]):
    table_name = "tagtable"


class ModelAccessGroupBudgetRepository(PrismaTableRepository["prisma_models.ModelAccessGroupBudgetTable"]):
    table_name = "modelaccessgroupbudgettable"


class InvitationLinkRepository(PrismaTableRepository["prisma_models.InvitationLink"]):
    table_name = "invitationlink"


class JWTKeyMappingRepository(PrismaTableRepository["prisma_models.JWTKeyMapping"]):
    table_name = "jwtkeymapping"


class ManagedFileRepository(PrismaTableRepository["prisma_models.ManagedFileTable"]):
    table_name = "managedfiletable"


class MemoryRepository(PrismaTableRepository["prisma_models.MemoryTable"]):
    table_name = "memorytable"


class SearchToolsRepository(PrismaTableRepository["prisma_models.SearchToolsTable"]):
    table_name = "searchtoolstable"


class ConfigOverridesRepository(PrismaTableRepository["prisma_models.ConfigOverrides"]):
    table_name = "configoverrides"


class MCPToolsetRepository(PrismaTableRepository["prisma_models.MCPToolsetTable"]):
    table_name = "mcptoolsettable"


class ToolRepository(PrismaTableRepository["prisma_models.ToolTable"]):
    table_name = "tooltable"


class DeletedVerificationTokenRepository(PrismaTableRepository["prisma_models.DeletedVerificationToken"]):
    table_name = "deletedverificationtoken"


class WorkflowRunRepository(PrismaTableRepository["prisma_models.WorkflowRun"]):
    table_name = "workflowrun"


class ModelTableRepository(PrismaTableRepository["prisma_models.ModelTable"]):
    table_name = "modeltable"


class AccessGroupRepository(PrismaTableRepository["prisma_models.AccessGroupTable"]):
    table_name = "accessgrouptable"


class SSOConfigRepository(PrismaTableRepository["prisma_models.SSOConfig"]):
    table_name = "ssoconfig"


class UISettingsRepository(PrismaTableRepository["prisma_models.UISettings"]):
    table_name = "uisettings"


class DailyGuardrailMetricsRepository(PrismaTableRepository["prisma_models.DailyGuardrailMetrics"]):
    table_name = "dailyguardrailmetrics"


class DailyGuardrailUsageUnitsRepository(PrismaTableRepository["prisma_models.DailyGuardrailUsageUnits"]):
    table_name = "dailyguardrailusageunits"


class PolicyAttachmentRepository(PrismaTableRepository["prisma_models.PolicyAttachmentTable"]):
    table_name = "policyattachmenttable"


class DeletedTeamRepository(PrismaTableRepository["prisma_models.DeletedTeamTable"]):
    table_name = "deletedteamtable"


class SkillsRepository(PrismaTableRepository["prisma_models.SkillsTable"]):
    table_name = "skillstable"


class CacheConfigRepository(PrismaTableRepository["prisma_models.CacheConfig"]):
    table_name = "cacheconfig"


class ManagedVectorStoreIndexRepository(PrismaTableRepository["prisma_models.ManagedVectorStoreIndexTable"]):
    table_name = "managedvectorstoreindextable"


class WorkflowMessageRepository(PrismaTableRepository["prisma_models.WorkflowMessage"]):
    table_name = "workflowmessage"


class DailyTagSpendRepository(PrismaTableRepository["prisma_models.DailyTagSpend"]):
    table_name = "dailytagspend"


class SpendLogToolIndexRepository(PrismaTableRepository["prisma_models.SpendLogToolIndex"]):
    table_name = "spendlogtoolindex"


class DailyToolSpendRepository(PrismaTableRepository["prisma_models.DailyToolSpend"]):
    table_name = "dailytoolspend"


class SpendLogGuardrailIndexRepository(PrismaTableRepository["prisma_models.SpendLogGuardrailIndex"]):
    table_name = "spendlogguardrailindex"


class UserNotificationsRepository(PrismaTableRepository["prisma_models.UserNotifications"]):
    table_name = "usernotifications"


class HealthCheckRepository(PrismaTableRepository["prisma_models.HealthCheckTable"]):
    table_name = "healthchecktable"


class DeprecatedVerificationTokenRepository(PrismaTableRepository["prisma_models.DeprecatedVerificationToken"]):
    table_name = "deprecatedverificationtoken"


class WorkflowEventRepository(PrismaTableRepository["prisma_models.WorkflowEvent"]):
    table_name = "workflowevent"


class DailyPolicyMetricsRepository(PrismaTableRepository["prisma_models.DailyPolicyMetrics"]):
    table_name = "dailypolicymetrics"


class AdaptiveRouterStateRepository(PrismaTableRepository["prisma_models.AdaptiveRouterState"]):
    table_name = "adaptiverouterstate"


class AuditLogRepository(PrismaTableRepository["prisma_models.AuditLog"]):
    table_name = "auditlog"


class AdaptiveRouterSessionRepository(PrismaTableRepository["prisma_models.AdaptiveRouterSession"]):
    table_name = "adaptiveroutersession"
