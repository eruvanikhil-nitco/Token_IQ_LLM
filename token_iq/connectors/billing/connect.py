"""What a new connection may carry, and what has to pass before it is stored.

Three rules, none of which needs a database, so each is tested on its own.

The field allowlist is per provider and exists because a billing credential's values are read
back by a connector. A denylist would have to anticipate every field some connector might act on
one day; an allowlist only has to name the ones that already work.

The external ID is resolved from the store, never from the request. It is the whole security
property of the role method: the customer's trust policy in their own account is written against
that exact value, so a value the caller chose is one they could reuse somewhere else.

And nothing is stored unless the live test passed. That is the blueprint's promise on the connect
dialog, and the failure it prevents is a connection that saves cleanly, shows as connected, and
then reports nothing at all.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType
from typing import Final, TypeAlias

from token_iq.gateway.types.proxy.management_endpoints.team_endpoints import BillingProbeResponse
from token_iq.types.provider_billing import BillingCredential

PROVIDERS_SIGNING_IN_WITH_A_ROLE: Final[frozenset[str]] = frozenset({"bedrock"})
"""Providers whose recommended method is a role Token IQ assumes rather than a stored secret.

Only AWS offers one today. An external ID on any other provider's credential would read as a
field that does something, and nothing in those connectors looks at it.
"""

PASSING_PROBE_OUTCOME: Final = "fetched"
"""The one outcome that counts as a working connection.

A fetch that answered with no rows still passes. A brand new account with no spend in the window
is a working connection, and requiring a figure would make a quiet account impossible to connect.
"""

BILLING_CREDENTIAL_FIELDS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "openai": frozenset({"api_key"}),
        "anthropic": frozenset({"api_key"}),
        "openrouter": frozenset({"api_key"}),
        "bedrock": frozenset(
            {
                "role_arn",
                "aws_access_key_id",
                "aws_secret_access_key",
                "aws_session_token",
                "aws_region_name",
                "service_name",
            }
        ),
        "azure": frozenset({"subscription_id", "service_name"}),
        "vertex_ai": frozenset({"billing_project_id", "billing_export_table"}),
    }
)
"""Every field each provider's billing credential may carry, and nothing else.

`external_id` is deliberately absent from bedrock's set: it is resolved by
`values_for_connection` from what was minted for this connection, so a request carrying one has
it dropped rather than honoured.
"""


@dataclasses.dataclass(frozen=True, slots=True)
class AccountStored:
    """The test passed and the credential was written."""

    provider: str
    credential_name: str
    facts_found: int


@dataclasses.dataclass(frozen=True, slots=True)
class NotStored:
    """The test did not pass, so nothing was written.

    `detail` is the provider's own words where there are any. "Could not connect" sends somebody
    back to a form with no idea which field is wrong, and AWS answers a trust policy that does not
    match with AccessDenied, which names the problem exactly.
    """

    provider: str
    credential_name: str
    outcome: str
    detail: str | None


ConnectResult: TypeAlias = AccountStored | NotStored


def permitted_values(provider: str, values: Mapping[str, str]) -> Mapping[str, str]:
    """The fields of `values` this provider's billing credential is allowed to carry.

    Blanks go too. A stored empty string makes a credential look like it carries a field it does
    not, and `read_sign_in` then names the wrong half of a key pair as the missing one.
    """
    allowed: Final = BILLING_CREDENTIAL_FIELDS.get(provider, frozenset())
    return MappingProxyType({key: value for key, value in values.items() if key in allowed and value != ""})


def values_for_connection(provider: str, requested: Mapping[str, str], external_id: str | None) -> Mapping[str, str]:
    """The values this connection is tested and stored with.

    A role sign-in gets the external ID that was minted for it. With none minted the role is left
    incomplete on purpose, so `read_sign_in` refuses it for carrying a role ARN with no external
    ID: the refusal that already exists rather than a second one invented here.
    """
    permitted: Final = permitted_values(provider, requested)
    if provider not in PROVIDERS_SIGNING_IN_WITH_A_ROLE or external_id is None:
        return permitted
    return MappingProxyType({**permitted, "external_id": external_id})


async def connect_account(
    *,
    provider: str,
    credential_name: str,
    values: Mapping[str, str],
    probe: Callable[[BillingCredential], Awaitable[BillingProbeResponse]],
    store: Callable[[BillingCredential], Awaitable[None]],
) -> ConnectResult:
    """Test the connection being offered, then store it only if the test passed.

    `probe` takes the candidate credential rather than reading a stored one. The existing probe
    endpoint looks up what is already saved, so a connect flow that reused it unchanged would
    test the previous connection and report a brand new key as working.
    """
    candidate: Final = BillingCredential(name=credential_name, values=values)
    answer: Final = await probe(candidate)

    if answer.outcome != PASSING_PROBE_OUTCOME:
        return NotStored(
            provider=provider,
            credential_name=credential_name,
            outcome=answer.outcome,
            detail=answer.detail,
        )

    await store(candidate)
    return AccountStored(provider=provider, credential_name=credential_name, facts_found=answer.facts_found)
