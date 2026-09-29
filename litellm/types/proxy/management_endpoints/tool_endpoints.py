"""Request and response shapes for the User Tools screens.

`what_it_cannot_give` travels to the browser beside everything else on purpose. Two of the
three tools cannot report what a reader would assume, and a screen that showed only the
figures would leave a customer working out why the numbers look wrong on their own.
"""

from __future__ import annotations

from pydantic import BaseModel

from litellm.provider_billing.connection_state import ConnectionState


class ToolFetchDetail(BaseModel):
    endpoint: str
    endpoint_url: str
    what_it_gives: str
    what_it_cannot_give: str
    backfill_note: str
    verification_note: str


class ToolConnectionAccount(BaseModel):
    credential_name: str
    state: ConnectionState
    detail: str | None
    last_sync_at: str | None
    last_outcome: str | None
    rows_stored: int


class ToolConnection(BaseModel):
    tool: str
    display_name: str
    state: ConnectionState
    accounts: tuple[ToolConnectionAccount, ...]
    fetches: ToolFetchDetail
    verified_against_real_account: bool


class ToolConnectionsResponse(BaseModel):
    tools: tuple[ToolConnection, ...]
