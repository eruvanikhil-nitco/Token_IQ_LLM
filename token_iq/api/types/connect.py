"""What the connect dialog sends and reads.

Both responses are tagged unions, for the same reason the data-quality ones are. A client that
received an external ID with no word on whether it was just generated would have to guess whether
the customer still has a CloudFormation stack to create, and a client that received a bare
`success: false` would have nothing to show the person except that something went wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, Literal, TypeAlias

from pydantic import BaseModel, Field

CREDENTIAL_NAME_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
"""What an account name may look like.

It becomes a stored credential name, appears in sync history and is echoed back in error
messages, so it is bounded and kept to characters that need no escaping anywhere it is shown.
"""


class ExternalIdRequest(BaseModel):
    vendor: str = Field(description="The connect catalogue's vendor key, for example aws")
    credential_name: str = Field(pattern=CREDENTIAL_NAME_PATTERN)


class ExternalIdMinted(BaseModel):
    kind: Literal["minted"] = "minted"
    external_id: str
    provider: str


class ExternalIdAlreadyIssued(BaseModel):
    kind: Literal["already_issued"] = "already_issued"
    external_id: str
    provider: str
    issued_at: str | None
    """When it was first handed out, so the dialog can say the role may already exist."""


ExternalIdResponse: TypeAlias = ExternalIdMinted | ExternalIdAlreadyIssued


class ConnectRequest(BaseModel):
    vendor: str = Field(description="The connect catalogue's vendor key, for example aws")
    credential_name: str = Field(pattern=CREDENTIAL_NAME_PATTERN)
    values: Mapping[str, str] = Field(
        default_factory=dict,
        description="The method's own fields. Anything outside this provider's allowlist is dropped.",
    )
    """Never an external ID. That one is resolved from what was minted for this connection, so a
    value sent here is dropped rather than honoured."""


class AccountConnected(BaseModel):
    kind: Literal["connected"] = "connected"
    provider: str
    credential_name: str
    facts_found: int
    """How many rows the test fetch brought back. Zero is still a pass: a new account with no
    spend in the window is a working connection."""


class ConnectionTestFailed(BaseModel):
    kind: Literal["test_failed"] = "test_failed"
    provider: str
    credential_name: str
    outcome: str
    """not_configured, failed, or no_connector. The probe's own vocabulary."""

    detail: str | None
    """The provider's own words where there are any, because they name the field that is wrong."""


ConnectResponse: TypeAlias = AccountConnected | ConnectionTestFailed


class RoleTemplateResponse(BaseModel):
    """The CloudFormation template the role method asks the customer to launch.

    Carried as text rather than served as a file so the dashboard's one HTTP client, which
    parses every response as JSON, can read it. The browser turns it back into a download.
    """

    filename: str
    template: str


class PrincipalKnownResponse(BaseModel):
    """The ARN to paste into the template's other parameter, as AWS reported it."""

    kind: Literal["known"] = "known"
    arn: str


class PrincipalDerivedResponse(BaseModel):
    """AWS answered with a role session, so the role behind it is the principal.

    `session_arn` is carried too, because an administrator checking this against their own
    deployment needs to see what it was worked out from. `note` says the one thing that cannot be
    worked out from here: whether the role sits under an IAM path.
    """

    kind: Literal["derived"] = "derived"
    arn: str
    session_arn: str
    note: str


class PrincipalUnknownResponse(BaseModel):
    """Nobody can say which principal this installation runs as, and why.

    Its own arm rather than an empty ARN. An empty parameter pasted into CloudFormation is a stack
    that fails to deploy, and a guessed one is a role that trusts a principal which will never
    present itself.
    """

    kind: Literal["unknown"] = "unknown"
    reason: str


BedrockPrincipalResponse: TypeAlias = PrincipalKnownResponse | PrincipalDerivedResponse | PrincipalUnknownResponse
