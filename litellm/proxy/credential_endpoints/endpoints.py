"""
CRUD endpoints for storing reusable credentials.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import (
    Final,
    cast,  # noqa: TID251  # jsonify_object in proxy/utils.py is annotated with a bare dict
)

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.litellm_core_utils.credential_accessor import CredentialAccessor
from litellm.litellm_core_utils.litellm_logging import _get_masked_values
from litellm.provider_billing.credential_purpose import billing_credential_problem, is_billing_credential
from litellm.proxy._types import CommonProxyErrors, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.common_utils.encrypt_decrypt_utils import encrypt_value_helper
from litellm.proxy.utils import handle_exception_on_proxy, jsonify_object
from litellm.repositories.credentials_repository import CredentialsRepository
from litellm.types.utils import CreateCredentialItem, CredentialItem

router: Final = APIRouter()


class CredentialHelperUtils:
    @staticmethod
    def encrypt_credential_values(credential: CredentialItem, new_encryption_key: str | None = None) -> CredentialItem:
        """Encrypt values in credential.credential_values and add to DB"""
        encrypted_credential_values: Final = {}
        for key, value in (credential.credential_values or {}).items():
            encrypted_credential_values[key] = encrypt_value_helper(value, new_encryption_key)

        # Return a new object to avoid mutating the caller's credential, which
        # is kept in memory and should remain unencrypted.
        return CredentialItem(
            credential_name=credential.credential_name,
            credential_values=encrypted_credential_values,
            credential_info=credential.credential_info or {},
        )


_NO_CREDENTIAL_VALUES: Final = MappingProxyType({})


def _refuse_unfit_billing_credential(
    credential_info: Mapping[str, object], credential_values: Mapping[str, object], *, require_keys: bool
) -> None:
    """A billing credential that cannot read its provider's bill is refused before it is stored."""
    if not is_billing_credential(credential_info):
        return
    problem: Final = billing_credential_problem(credential_info, credential_values, require_keys=require_keys)
    if problem is not None:
        raise HTTPException(status_code=400, detail=problem)


@router.post(
    "/credentials",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def create_credential(
    request: Request,
    fastapi_response: Response,
    credential: CreateCredentialItem,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    [BETA] endpoint. This might change unexpectedly.
    Stores credential in DB.
    Reloads credentials in memory.
    """
    from litellm.proxy.proxy_server import llm_router, prisma_client

    try:
        if prisma_client is None:
            raise HTTPException(
                status_code=500,
                detail={"error": CommonProxyErrors.db_not_connected_error.value},
            )
        if credential.model_id:
            if llm_router is None:
                raise HTTPException(
                    status_code=500,
                    detail="LLM router not found. Please ensure you have a valid router instance.",
                )
            # get model from router
            model: Final = llm_router.get_deployment(credential.model_id)
            if model is None:
                raise HTTPException(status_code=404, detail="Model not found")
            credential_values: Final = llm_router.get_deployment_credentials(credential.model_id)
            if credential_values is None:
                raise HTTPException(status_code=404, detail="Model not found")
            credential.credential_values = credential_values

        if credential.credential_values is None:
            raise HTTPException(
                status_code=400,
                detail="Credential values are required. Unable to infer credential values from model ID.",
            )
        _refuse_unfit_billing_credential(credential.credential_info, credential.credential_values, require_keys=True)
        processed_credential: Final = CredentialItem(
            credential_name=credential.credential_name,
            credential_values=credential.credential_values,
            credential_info=credential.credential_info,
        )
        encrypted_credential: Final = CredentialHelperUtils.encrypt_credential_values(processed_credential)
        credentials_dict: Final = encrypted_credential.model_dump()
        credentials_dict_jsonified: Final = cast(  # cast-ok: deep-copies a model_dump, so keys are str
            "dict[str, object]", jsonify_object(credentials_dict)
        )
        await CredentialsRepository(prisma_client).create(
            data={
                **credentials_dict_jsonified,
                "created_by": user_api_key_dict.user_id,
                "updated_by": user_api_key_dict.user_id,
            }
        )

        ## ADD TO LITELLM ##
        CredentialAccessor.upsert_credentials([processed_credential])

        return {"success": True, "message": "Credential created successfully"}
    except Exception as e:
        verbose_proxy_logger.exception(e)
        raise handle_exception_on_proxy(e)


@router.get(
    "/credentials",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def get_credentials(
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    [BETA] endpoint. This might change unexpectedly.
    """
    try:
        masked_credentials: Final = [
            {
                "credential_name": credential.credential_name,
                "credential_values": _NO_CREDENTIAL_VALUES
                if is_billing_credential(credential.credential_info)
                else _get_masked_values(credential.credential_values),
                "credential_info": credential.credential_info,
            }
            for credential in litellm.credential_list
        ]
        return {"success": True, "credentials": masked_credentials}
    except Exception as e:
        return handle_exception_on_proxy(e)


@router.get(
    "/credentials/by_name/{credential_name:path}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
    response_model=CredentialItem,
)
async def get_credential_by_name(
    request: Request,
    fastapi_response: Response,
    credential_name: str = Path(..., description="The credential name, percent-decoded; may contain slashes"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    [BETA] endpoint. This might change unexpectedly.
    """
    try:
        for credential in litellm.credential_list:
            if credential.credential_name == credential_name:
                masked_credential = CredentialItem(
                    credential_name=credential.credential_name,
                    credential_values=_NO_CREDENTIAL_VALUES
                    if is_billing_credential(credential.credential_info)
                    else _get_masked_values(
                        credential.credential_values,
                        unmasked_length=4,
                        number_of_asterisks=4,
                    ),
                    credential_info=credential.credential_info,
                )
                return masked_credential
        raise HTTPException(
            status_code=404,
            detail="Credential not found. Got credential name: " + credential_name,
        )
    except Exception as e:
        verbose_proxy_logger.exception(e)
        raise handle_exception_on_proxy(e)


@router.get(
    "/credentials/by_model/{model_id}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
    response_model=CredentialItem,
)
async def get_credential_by_model(
    request: Request,
    fastapi_response: Response,
    model_id: str = Path(..., description="The model ID to look up credentials for"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    [BETA] endpoint. This might change unexpectedly.
    """
    from litellm.proxy.proxy_server import llm_router

    try:
        if llm_router is None:
            raise HTTPException(status_code=500, detail="LLM router not found")
        model: Final = llm_router.get_deployment(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        credential_values: Final = llm_router.get_deployment_credentials(model_id)
        if credential_values is None:
            raise HTTPException(status_code=404, detail="Model not found")
        masked_credential_values: Final = _get_masked_values(
            credential_values,
            unmasked_length=4,
            number_of_asterisks=4,
        )
        credential: Final = CredentialItem(
            credential_name=f"{model.model_name}-credential-{model_id}",
            credential_values=masked_credential_values,
            credential_info={},
        )
        return credential
    except Exception as e:
        verbose_proxy_logger.exception(e)
        raise handle_exception_on_proxy(e)


@router.delete(
    "/credentials/{credential_name:path}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def delete_credential(
    request: Request,
    fastapi_response: Response,
    credential_name: str = Path(..., description="The credential name, percent-decoded; may contain slashes"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    [BETA] endpoint. This might change unexpectedly.
    """
    from litellm.proxy.proxy_server import prisma_client

    try:
        if prisma_client is None:
            raise HTTPException(
                status_code=500,
                detail={"error": CommonProxyErrors.db_not_connected_error.value},
            )
        await CredentialsRepository(prisma_client).delete_by_name(credential_name)

        ## DELETE FROM LITELLM ##
        litellm.credential_list = [cred for cred in litellm.credential_list if cred.credential_name != credential_name]
        return {"success": True, "message": "Credential deleted successfully"}
    except Exception as e:
        return handle_exception_on_proxy(e)


def update_db_credential(
    db_credential: CredentialItem,
    updated_patch: CredentialItem,
    new_encryption_key: str | None = None,
) -> CredentialItem:
    """The stored credential with the patch's name, encrypted values and info laid over it, key by key."""
    encrypted_patch: Final = CredentialHelperUtils.encrypt_credential_values(updated_patch, new_encryption_key)
    return CredentialItem.model_validate(
        MappingProxyType(
            {
                "credential_name": encrypted_patch.credential_name or db_credential.credential_name,
                "credential_values": MappingProxyType(
                    {**db_credential.credential_values, **encrypted_patch.credential_values}
                ),
                "credential_info": MappingProxyType(
                    {**db_credential.credential_info, **encrypted_patch.credential_info}
                ),
            }
        )
    )


_PURPOSE_KEYS: Final = ("purpose", "provider")


def _refuse_purpose_or_provider_change(stored_info: Mapping[str, object], patched_info: Mapping[str, object]) -> None:
    """A billing key is checked for its purpose and provider when stored, so relabelling it would skip that check."""
    if not (is_billing_credential(stored_info) or is_billing_credential(patched_info)):
        return
    if any(key in patched_info and patched_info[key] != stored_info.get(key) for key in _PURPOSE_KEYS):
        raise HTTPException(
            status_code=400,
            detail="The purpose and provider of a credential cannot be changed. Delete it and create a new one.",
        )


@router.patch(
    "/credentials/{credential_name:path}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["credential management"],
)
async def update_credential(
    request: Request,
    fastapi_response: Response,
    credential: CredentialItem,
    credential_name: str = Path(..., description="The credential name, percent-decoded; may contain slashes"),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    [BETA] endpoint. This might change unexpectedly.
    """
    from litellm.proxy.proxy_server import prisma_client

    try:
        if prisma_client is None:
            raise HTTPException(
                status_code=500,
                detail={"error": CommonProxyErrors.db_not_connected_error.value},
            )
        credentials_repository: Final = CredentialsRepository(prisma_client)
        db_credential: Final = await credentials_repository.find_by_name(credential_name)
        if db_credential is None:
            raise HTTPException(status_code=404, detail="Credential not found in DB.")
        merged_info: Final = MappingProxyType({**db_credential.credential_info, **credential.credential_info})
        _refuse_purpose_or_provider_change(db_credential.credential_info, merged_info)
        _refuse_unfit_billing_credential(merged_info, credential.credential_values, require_keys=False)
        merged_credential: Final = update_db_credential(db_credential, credential)
        credential_object_jsonified: Final = cast(  # cast-ok: deep-copies a model_dump, so keys are str
            "dict[str, object]", jsonify_object(merged_credential.model_dump())
        )
        await credentials_repository.update_by_name(
            credential_name,
            data={
                **credential_object_jsonified,
                "updated_by": user_api_key_dict.user_id,
            },
        )

        # Sync in-memory credential_list (skip if not in memory - e.g., proxy restarted)
        new_name: Final = merged_credential.credential_name
        existing_in_memory: CredentialItem | None = None
        for cred in litellm.credential_list:
            if cred.credential_name == credential_name:
                existing_in_memory = cred
                break

        if existing_in_memory is not None:
            in_memory_values: Final = dict(existing_in_memory.credential_values or {})
            if credential.credential_values:
                in_memory_values.update(credential.credential_values)
            in_memory_info: Final = dict(existing_in_memory.credential_info or {})
            if credential.credential_info:
                in_memory_info.update(credential.credential_info)
            updated_in_memory: Final = CredentialItem(
                credential_name=new_name,
                credential_values=in_memory_values,
                credential_info=in_memory_info,
            )
            # Remove old entry if renamed, then use upsert_credentials to handle duplicates
            if new_name != credential_name:
                litellm.credential_list = [c for c in litellm.credential_list if c.credential_name != credential_name]
            CredentialAccessor.upsert_credentials([updated_in_memory])

        return {"success": True, "message": "Credential updated successfully"}
    except Exception as e:
        raise handle_exception_on_proxy(e)
