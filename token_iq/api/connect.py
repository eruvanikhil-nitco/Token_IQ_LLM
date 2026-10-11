"""The two endpoints the connect dialog needs.

One mints the external ID a role sign-in rests on, once per connection and never again. The other
tests the connection being offered and stores it only if that test passed, which is the promise
the dialog makes to the person pasting a key.

The rules both apply live in `token_iq/connectors/billing/connect.py` and are tested without a
database. What is here is the wiring: translating the catalogue's vendor key to the provider whose
bill is read, resolving the external ID from the store rather than the request, and writing the
credential down the same encryption path the credential endpoint uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import TypeAdapter

from token_iq.api.provider_reconciliation import run_billing_probe
from token_iq.api.types.connect import (
    AccountConnected,
    ConnectionTestFailed,
    ConnectRequest,
    ConnectResponse,
    ExternalIdAlreadyIssued,
    ExternalIdMinted,
    ExternalIdRequest,
    ExternalIdResponse,
    RoleTemplateResponse,
)
from token_iq.connectors.billing import bedrock
from token_iq.connectors.billing.bedrock import new_external_id
from token_iq.connectors.billing.connect import (
    PROVIDERS_SIGNING_IN_WITH_A_ROLE,
    AccountStored,
    ConnectResult,
    NotStored,
    connect_account,
    values_for_connection,
)
from token_iq.connectors.billing.connector import BillingConnector, registered_connectors
from token_iq.connectors.billing.credential_purpose import (
    BILLING_PURPOSE,
    billing_credential_problem,
    billing_provider_for_vendor,
)
from token_iq.gateway.proxy._types import CommonProxyErrors, GatewayUserRoles, UserAPIKeyAuth
from token_iq.gateway.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.gateway.types.proxy.management_endpoints.team_endpoints import BillingProbeResponse
from token_iq.gateway.types.utils import CredentialItem
from token_iq.repositories.connection_external_id_repository import (
    AlreadyIssued,
    ConnectionExternalIdRepository,
    FreshlyMinted,
    IssuedExternalId,
)
from token_iq.types.provider_billing import BillingCredential

_CREDENTIAL_ROW: Final = TypeAdapter(dict[str, object])
"""One encrypted credential row on its way to the database.

The gateway's `jsonify_object` is annotated with a bare `dict`, so the row it returns is
untyped. Validating it here is what keeps an unknown value out of a database write.
"""

router: Final = APIRouter(
    tags=["provider billing"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)


def _proxy_error(status_code: int, message: str) -> HTTPException:
    """A refusal a client can read.

    A plain dict because FastAPI runs the detail through `json.dumps`, and a `MappingProxyType`
    is not serialisable: the refusal then reaches the caller as a generic 500 with the reason
    gone, which is the worst possible answer to a form field being wrong.
    """
    return HTTPException(
        status_code=status_code,
        detail={"error": message},  # mutable-ok: fixed one-key error envelope, and json.dumps needs a dict
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != GatewayUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, CommonProxyErrors.not_allowed_access.value)


def provider_or_400(vendor: str) -> str:
    """The provider whose bill this vendor's account carries.

    A vendor with none is refused rather than stored under a guessed provider. Seat and agent
    vendors are the ones that land here: their spend arrives through the tool connectors and is on
    no provider bill, so giving one of them a provider would feed tool spend into a provider
    figure, which is the one addition the counting rule forbids.
    """
    provider: Final = billing_provider_for_vendor(vendor)
    if provider is None:
        raise _proxy_error(
            status.HTTP_400_BAD_REQUEST,
            f"{vendor} has no provider bill to read. Connect it as a tool, or upload its invoices.",
        )
    return provider


def external_id_to_wire(issued: IssuedExternalId, provider: str) -> ExternalIdResponse:
    """Exhaustive over the union, so a third state is a type error here rather than an external ID
    that silently arrives looking freshly minted."""
    match issued:
        case FreshlyMinted(external_id=external_id):
            return ExternalIdMinted(external_id=external_id, provider=provider)
        case AlreadyIssued(external_id=external_id, issued_at=issued_at):
            return ExternalIdAlreadyIssued(
                external_id=external_id,
                provider=provider,
                issued_at=None if issued_at is None else issued_at.isoformat(),
            )


def connect_to_wire(result: ConnectResult) -> ConnectResponse:
    """Exhaustive for the same reason. A new outcome must not fall through as a success."""
    match result:
        case AccountStored(provider=provider, credential_name=name, facts_found=found):
            return AccountConnected(provider=provider, credential_name=name, facts_found=found)
        case NotStored(provider=provider, credential_name=name, outcome=outcome, detail=detail):
            return ConnectionTestFailed(provider=provider, credential_name=name, outcome=outcome, detail=detail)


def build_candidate_probe(
    *, provider: str, connectors: Sequence[BillingConnector]
) -> Callable[[BillingCredential], Awaitable[BillingProbeResponse]]:
    """A probe that reads the credential being offered rather than one already stored.

    `run_billing_probe` takes its credentials through an injected lookup, so the candidate is
    handed to it directly. Reusing the stored lookup here would test the previous connection and
    report a brand new key as working.
    """

    async def probe(candidate: BillingCredential) -> BillingProbeResponse:
        async def candidate_only(_: str) -> tuple[BillingCredential, ...]:
            return (candidate,)

        return await run_billing_probe(provider=provider, connectors=connectors, credentials_for=candidate_only)

    return probe


def credential_row(encrypted: CredentialItem, *, stored_by: str | None) -> Mapping[str, object]:
    """One encrypted credential as the database takes it.

    A plain dict, and that is the whole point of this function existing. Prisma serialises the
    row with `json.dumps`, which refuses a read-only view, so the first connection whose live
    test actually passed came back as a 500 with nothing stored. Separated out so the row can be
    put through the same serialiser in a test.

    `jsonify_object` is annotated with a bare `dict`, so the row is validated rather than passed
    through: without that, an untyped value would go straight into a database write.
    """
    from token_iq.gateway.proxy.utils import jsonify_object

    fields: Final = _CREDENTIAL_ROW.validate_python(jsonify_object(encrypted.model_dump()))
    return {**fields, "created_by": stored_by, "updated_by": stored_by}  # mutable-ok: prisma serialises it


def build_credential_store(
    *,
    prisma_client: object,
    provider: str,
    stored_by: str | None,
) -> Callable[[BillingCredential], Awaitable[None]]:
    """Writes the credential down the same path the credential endpoint uses.

    Encryption, the row and the in-memory upsert all come from there rather than being repeated,
    so a billing credential stored through the connect dialog is byte for byte one stored through
    the credentials API.
    """

    async def store(credential: BillingCredential) -> None:
        from token_iq.gateway.core_utils.credential_accessor import CredentialAccessor
        from token_iq.gateway.proxy.credential_endpoints.endpoints import CredentialHelperUtils
        from token_iq.gateway.repositories.credentials_repository import CredentialsRepository

        item: Final = CredentialItem(
            credential_name=credential.name,
            credential_values=dict(credential.values),  # mutable-ok: CredentialItem's field is typed `dict`
            credential_info={"purpose": BILLING_PURPOSE, "provider": provider},  # mutable-ok: as above
        )
        encrypted: Final = CredentialHelperUtils.encrypt_credential_values(item)
        await CredentialsRepository(prisma_client).create(data=credential_row(encrypted, stored_by=stored_by))
        CredentialAccessor.upsert_credentials(
            [item]  # mutable-ok: upsert_credentials' own signature takes a list; never grown here
        )

    return store


@router.post("/provider/connections/external-id", response_model=ExternalIdResponse)
async def provider_connection_external_id(
    request: ExternalIdRequest,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> ExternalIdResponse:
    """The external ID this connection presents, minting one the first time it is asked for."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    provider: Final = provider_or_400(request.vendor)
    if provider not in PROVIDERS_SIGNING_IN_WITH_A_ROLE:
        raise _proxy_error(
            status.HTTP_400_BAD_REQUEST,
            f"{provider} does not sign in with an assumed role, so it has no external ID.",
        )

    issued: Final = await ConnectionExternalIdRepository(prisma_client).issue(
        provider, request.credential_name, mint=new_external_id
    )
    return external_id_to_wire(issued, provider)


@router.post("/provider/connections", response_model=ConnectResponse)
async def connect_provider_account(
    request: ConnectRequest,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> ConnectResponse:
    """Test the connection being offered, and store it only if the test passed."""
    from token_iq.gateway.proxy.proxy_server import prisma_client
    from token_iq.gateway.repositories.credentials_repository import CredentialsRepository

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    provider: Final = provider_or_400(request.vendor)

    if await CredentialsRepository(prisma_client).find_by_name(request.credential_name) is not None:
        raise _proxy_error(
            status.HTTP_409_CONFLICT,
            f"An account named {request.credential_name} already exists. Pick another name.",
        )

    external_id: Final = (
        await ConnectionExternalIdRepository(prisma_client).find(provider, request.credential_name)
        if provider in PROVIDERS_SIGNING_IN_WITH_A_ROLE
        else None
    )
    values: Final[Mapping[str, str]] = values_for_connection(provider, request.values, external_id)

    problem: Final = billing_credential_problem(
        MappingProxyType({"purpose": BILLING_PURPOSE, "provider": provider}), values, require_keys=True
    )
    if problem is not None:
        raise _proxy_error(status.HTTP_400_BAD_REQUEST, problem)

    result: Final = await connect_account(
        provider=provider,
        credential_name=request.credential_name,
        values=values,
        probe=build_candidate_probe(provider=provider, connectors=registered_connectors()),
        store=build_credential_store(
            prisma_client=prisma_client, provider=provider, stored_by=user_api_key_dict.user_id
        ),
    )
    return connect_to_wire(result)


ROLE_TEMPLATE_PATH: Final = Path(bedrock.__file__).with_name("bedrock_read_only_role.yaml")
"""The CloudFormation template the role method's first step asks the customer to launch.

Served rather than linked. The template is what creates the role, so a dialog that names it and
gives no way to get it is a dead end, and a template a customer retyped is one whose trust policy
nobody has checked. `tests/token_iq/connectors/billing/test_bedrock_role_template.py` guards the
file this serves.
"""


@router.get("/provider/connections/bedrock-role-template", response_model=RoleTemplateResponse)
async def bedrock_role_template(
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> RoleTemplateResponse:
    """The CloudFormation template that creates the read-only role, exactly as it ships."""
    _admin_or_403(user_api_key_dict)
    return RoleTemplateResponse(
        filename="token-iq-bedrock-role.yaml",
        template=ROLE_TEMPLATE_PATH.read_text(encoding="utf-8"),
    )
