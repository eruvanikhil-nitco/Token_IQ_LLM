from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from litellm.provider_billing.connection_state import ConnectionState
from litellm.proxy._types import (
    KeyManagementRoutes,
    LiteLLM_DeletedTeamTable,
    LiteLLM_TeamMembership,
    LiteLLM_TeamTable,
    Member,
)
from litellm.types.proxy.provider_billing import SyncOutcome
from litellm.types.proxy.team_api_access import TeamApiAccessMode

TeamIdSearchMatch = Literal["exact", "prefix"]


class GetTeamMemberPermissionsRequest(BaseModel):
    """Request to get the team member permissions for a team"""

    team_id: str


class GetTeamMemberPermissionsResponse(BaseModel):
    """Response to get the team member permissions for a team"""

    team_id: str
    """
    The team id that the permissions are for
    """

    team_member_permissions: list[str] | None = []
    """
    The team member permissions currently set for the team
    """

    all_available_permissions: list[str]
    """
    All available team member permissions
    """


class UpdateTeamMemberPermissionsRequest(BaseModel):
    """Request to update the team member permissions for a team"""

    team_id: str
    team_member_permissions: list[str]


class BulkUpdateTeamMemberPermissionsRequest(BaseModel):
    """Request to bulk-update team member permissions across teams."""

    permissions: list[KeyManagementRoutes]
    """Permissions to append to the target teams (duplicates are skipped)."""

    team_ids: list[str] | None = None
    """Specific team IDs to update. Required unless apply_to_all_teams is True."""

    apply_to_all_teams: bool = False
    """When True, update all teams. Mutually exclusive with team_ids."""


class BulkUpdateTeamMemberPermissionsResponse(BaseModel):
    """Response for bulk team member permissions update."""

    message: str
    teams_updated: int
    permissions_appended: list[str] | None = None


class TeamListItem(LiteLLM_TeamTable):
    """A team item in the paginated list response, enriched with computed fields."""

    members_count: int = 0
    keys_count: int = 0
    # Resources inherited from access groups (separate from direct assignments)
    access_group_models: list[str] | None = None
    access_group_mcp_server_ids: list[str] | None = None
    access_group_agent_ids: list[str] | None = None


class TeamListResponse(BaseModel):
    """Response to get the list of teams"""

    teams: list[TeamListItem | LiteLLM_TeamTable | LiteLLM_DeletedTeamTable]
    total: int
    page: int
    page_size: int
    total_pages: int


class BulkTeamMemberAddRequest(BaseModel):
    """Request for bulk team member addition"""

    team_id: str
    members: list[Member] | None = None  # List of members to add
    all_users: bool | None = False  # Flag to add all users on Proxy to the team
    max_budget_in_team: float | None = None


class TeamMemberAddResult(BaseModel):
    """Result of a single team member add operation"""

    user_id: str | None = None
    user_email: str | None = None
    success: bool
    error: str | None = None
    updated_user: dict[str, Any] | None = None
    updated_team_membership: dict[str, Any] | None = None


class BulkTeamMemberAddResponse(BaseModel):
    """Response for bulk team member add operations"""

    team_id: str
    results: list[TeamMemberAddResult]
    total_requested: int
    successful_additions: int
    failed_additions: int
    updated_team: dict[str, Any] | None = None


class TeamMemberInfoResponse(LiteLLM_TeamMembership):
    """Response for GET /team/{team_id}/members/me — caller's own membership row."""

    role: str | None = None
    user_email: str | None = None
    team_alias: str | None = None


class TeamMetadataFieldSchema(BaseModel):
    """One declared team metadata field from ``general_settings.team_metadata_schema``.

    Advisory only: the UI uses it to prepopulate the team metadata form.
    Enforcement stays with ``custom_team_metadata_validate``.
    """

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    label: str | None = None


class TeamMetadataSchemaResponse(BaseModel):
    """Response for GET /team/metadata_schema; ``fields`` is empty when no schema is configured."""

    fields: tuple[TeamMetadataFieldSchema, ...]


class ProviderCourierCoverageResponse(BaseModel):
    """What one provider will do for a team running in courier mode"""

    provider: str
    has_route: bool
    """Whether a courier route exists for this provider at all"""

    reads_usage: bool
    """Whether the provider's reply is read for token usage, which is what makes the request billable"""

    is_covered: bool
    summary: str


class TeamCourierCoverageResponse(BaseModel):
    """Everything the courier mode panel needs to tell an admin what switching would do"""

    team_id: str
    api_access_mode: TeamApiAccessMode
    unbound_key_count: int
    """Keys on this team that do not name the provider account they spend against"""

    providers: list[ProviderCourierCoverageResponse]


class ReconciliationRow(BaseModel):
    """One request, priced twice"""

    request_id: str
    model: str | None
    credential_name: str
    our_cost: str
    their_cost: str | None
    delta: str | None
    evidence: str
    """reconciled, priced, or allocated — how much of this row the provider actually asserted"""


class ReconciliationResponse(BaseModel):
    """What we recorded against what the provider charged, over a window"""

    provider: str
    rows: list[ReconciliationRow]
    our_total: str
    their_total: str
    delta: str
    unmatched_our_rows: int
    """Requests we recorded that the provider has not priced. Either a polling backlog, or
    spend the provider never billed us for."""


class BillingProbeResponse(BaseModel):
    """One on-demand fetch from a provider's billing API, reported without storing anything"""

    provider: str
    credential_name: str | None
    """Which stored credential was tried, when one was found"""

    outcome: str
    """fetched, not_configured, failed, or no_connector"""

    facts_found: int
    sample_cost: str | None
    detail: str | None


class ProviderFetchDetail(BaseModel):
    """What this build reads from one provider"""

    endpoint: str
    endpoint_url: str
    grain: str
    """request or day"""

    refresh_seconds: int
    window_hours: int
    delay_note: str
    history_note: str


class ProviderConnectionAccount(BaseModel):
    """One stored billing credential's standing against its provider"""

    credential_name: str
    state: ConnectionState
    detail: str | None
    last_sync_at: str | None
    last_outcome: str | None
    facts_stored: int


class ProviderConnection(BaseModel):
    provider: str
    display_name: str
    state: ConnectionState
    accounts: tuple[ProviderConnectionAccount, ...]
    fetches: ProviderFetchDetail


class ProviderConnectionsResponse(BaseModel):
    providers: tuple[ProviderConnection, ...]


class ProviderSyncHistoryRow(BaseModel):
    provider: str
    credential_name: str
    started_at: str
    finished_at: str
    outcome: SyncOutcome
    facts_written: int
    window_start: str
    window_end: str
    detail: str | None


class ProviderSyncHistoryResponse(BaseModel):
    rows: tuple[ProviderSyncHistoryRow, ...]


class DailyReconciliationRow(BaseModel):
    """One day, charged twice"""

    day: str
    our_cost: str
    their_cost: str | None
    delta: str | None
    escaped_spend: bool
    """True when the provider charged more than this gateway recorded, meaning traffic
    reached the provider without passing through here."""


class DailyReconciliationResponse(BaseModel):
    """Daily totals from a provider that reports aggregates rather than single requests"""

    provider: str
    rows: list[DailyReconciliationRow]
    our_total: str
    their_total: str
    delta: str
    days_provider_charged_more: int
