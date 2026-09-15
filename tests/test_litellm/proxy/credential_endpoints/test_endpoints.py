"""Tests for the credential management endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.proxy_server import app
from litellm.types.utils import CredentialItem

client = TestClient(app)


def _as_admin():
    return UserAPIKeyAuth(api_key="test-key", user_role="proxy_admin")


def _patch_credential(name: str, body: dict):
    missing = object()
    previous_override = app.dependency_overrides.get(user_api_key_auth, missing)
    app.dependency_overrides[user_api_key_auth] = _as_admin
    try:
        return client.patch(
            f"/credentials/{name}",
            json=body,
            headers={"Authorization": "Bearer test-key"},
        )
    finally:
        if previous_override is missing:
            app.dependency_overrides.pop(user_api_key_auth, None)
        else:
            app.dependency_overrides[user_api_key_auth] = previous_override


def test_update_credential_answers_404_when_the_credential_does_not_exist():
    """Regression: the handler used to ``return handle_exception_on_proxy(e)``, which makes
    the exception the response body and lets FastAPI answer 200, so a write the handler
    rejected read as a success to every caller that checks the status. The dashboard's API
    client branches on the status, so it reported a failed edit as applied."""
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository:
        repository.return_value.find_by_name = AsyncMock(return_value=None)

        response = _patch_credential(
            "definitely-not-there",
            {"credential_name": "definitely-not-there", "credential_values": {"api_key": "sk-x"}, "credential_info": {}},
        )

    assert response.status_code == 404, f"rejected write answered {response.status_code}: {response.text}"
    assert "error" in response.json()


def test_update_credential_answers_500_when_the_database_is_not_connected():
    """The other rejection this handler raises must carry its own status too."""
    with patch("litellm.proxy.proxy_server.prisma_client", None):
        response = _patch_credential(
            "any-name",
            {"credential_name": "any-name", "credential_values": {"api_key": "sk-x"}, "credential_info": {}},
        )

    assert response.status_code == 500, f"rejected write answered {response.status_code}: {response.text}"


def test_update_credential_still_answers_200_on_a_successful_write():
    """The fix must not turn a legitimate update into an error; the dashboard and the
    Playwright credentials spec both assert the success path."""
    stored = CredentialItem(
        credential_name="existing",
        credential_values={"api_key": "sk-old"},
        credential_info={"custom_llm_provider": "openai"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository:
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)

        response = _patch_credential(
            "existing",
            {"credential_name": "existing", "credential_values": {"api_key": "sk-new"}, "credential_info": {}},
        )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def _as_admin_request(method: str, path: str, body: dict | None = None):
    missing = object()
    previous_override = app.dependency_overrides.get(user_api_key_auth, missing)
    app.dependency_overrides[user_api_key_auth] = _as_admin
    try:
        return client.request(method, path, json=body, headers={"Authorization": "Bearer test-key"})
    finally:
        if previous_override is missing:
            app.dependency_overrides.pop(user_api_key_auth, None)
        else:
            app.dependency_overrides[user_api_key_auth] = previous_override


def test_creating_a_billing_credential_with_an_ordinary_key_is_refused_before_anything_is_stored():
    """An ordinary OpenAI key saves fine and then fails every cost sync with a 401."""
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository:
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "openai-billing",
                "credential_values": {"api_key": "sk-proj-test-not-real"},
                "credential_info": {"purpose": "billing_ingestion", "provider": "openai"},
            },
        )

    assert response.status_code == 400, response.text
    message = response.json()["error"]["message"]
    assert "sk-admin-" in message
    assert "{'error'" not in message
    repository.return_value.create.assert_not_awaited()


def test_creating_a_billing_credential_with_an_admin_key_is_stored():
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialAccessor.upsert_credentials"
    ):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "openai-billing",
                "credential_values": {"api_key": "sk-admin-test-not-real"},
                "credential_info": {"purpose": "billing_ingestion", "provider": "openai"},
            },
        )

    assert response.status_code == 200, response.text
    repository.return_value.create.assert_awaited_once()


def test_updating_a_billing_credential_with_an_ordinary_key_is_refused():
    stored = CredentialItem(
        credential_name="openai-billing",
        credential_values={"api_key": "encrypted-stored-value"},
        credential_info={"purpose": "billing_ingestion", "provider": "openai"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository:
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)

        response = _patch_credential(
            "openai-billing",
            {
                "credential_name": "openai-billing",
                "credential_values": {"api_key": "sk-proj-test-not-real"},
                "credential_info": {},
            },
        )

    assert response.status_code == 400, response.text
    repository.return_value.update_by_name.assert_not_awaited()


def _patch_stored_credential(stored: CredentialItem, body: dict):
    import litellm

    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch.object(
        litellm, "credential_list", []
    ):
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)
        response = _patch_credential(stored.credential_name, body)
    return response, repository.return_value.update_by_name


def _written_credential_info(update_by_name: AsyncMock) -> dict:
    import json

    written = update_by_name.await_args.kwargs["data"]["credential_info"]
    return json.loads(written) if isinstance(written, str) else written


@pytest.mark.parametrize(
    "stored_info",
    [
        {"purpose": "billing_ingestion", "provider": "openai"},
        {"custom_llm_provider": "openai"},
    ],
    ids=["billing", "model_access"],
)
def test_patching_credential_info_keeps_the_stored_info_in_the_database(stored_info):
    """Regression: the database copy was replaced by the patch's info, so a billing
    credential lost its marker on the next reload and was served as a model key."""
    stored = CredentialItem(
        credential_name="stored-credential",
        credential_values={"api_key": "encrypted-stored-value"},
        credential_info=dict(stored_info),
    )

    response, update_by_name = _patch_stored_credential(
        stored,
        {"credential_name": "stored-credential", "credential_values": {}, "credential_info": {"description": "costs"}},
    )

    assert response.status_code == 200, response.text
    assert _written_credential_info(update_by_name) == {**stored_info, "description": "costs"}
    assert stored.credential_info == stored_info


_BILLING_OPENAI = {"purpose": "billing_ingestion", "provider": "openai"}
_PURPOSE_CHANGE_REFUSED = "The purpose and provider of a credential cannot be changed. Delete it and create a new one."


@pytest.mark.parametrize(
    "stored_info,patched_info",
    [
        ({"custom_llm_provider": "openai"}, _BILLING_OPENAI),
        (_BILLING_OPENAI, {"purpose": "model_access"}),
        (_BILLING_OPENAI, {"provider": "anthropic"}),
    ],
    ids=["model_access_to_billing", "billing_to_other_purpose", "billing_openai_to_anthropic"],
)
def test_changing_the_purpose_or_provider_of_a_billing_credential_is_refused(stored_info, patched_info):
    """A key checked for one purpose and provider must not skip that check by being relabelled."""
    stored = CredentialItem(
        credential_name="stored-credential",
        credential_values={"api_key": "encrypted-stored-value"},
        credential_info=dict(stored_info),
    )

    response, update_by_name = _patch_stored_credential(
        stored,
        {"credential_name": "stored-credential", "credential_values": {}, "credential_info": patched_info},
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == _PURPOSE_CHANGE_REFUSED
    update_by_name.assert_not_awaited()


def test_resending_the_same_purpose_and_provider_with_a_new_admin_key_is_accepted():
    """The dashboard sends the stored purpose and provider back on every edit."""
    stored = CredentialItem(
        credential_name="openai-billing",
        credential_values={"api_key": "encrypted-stored-value"},
        credential_info=dict(_BILLING_OPENAI),
    )

    response, update_by_name = _patch_stored_credential(
        stored,
        {
            "credential_name": "openai-billing",
            "credential_values": {"api_key": "sk-admin-new-test-not-real"},
            "credential_info": dict(_BILLING_OPENAI),
        },
    )

    assert response.status_code == 200, response.text
    assert _written_credential_info(update_by_name) == _BILLING_OPENAI


def test_listing_credentials_never_returns_any_part_of_a_billing_key():
    """Billing keys read a whole organisation's costs. Even a masked prefix narrows a
    leaked key down, so the list returns nothing for them."""
    import litellm

    billing = CredentialItem(
        credential_name="anthropic-billing",
        credential_values={"api_key": "sk-ant-admin01-test-not-real"},
        credential_info={"purpose": "billing_ingestion", "provider": "anthropic"},
    )
    model_access = CredentialItem(
        credential_name="openai-models",
        credential_values={"api_key": "sk-proj-test-not-real"},
        credential_info={"custom_llm_provider": "openai"},
    )
    with patch.object(litellm, "credential_list", [billing, model_access]):
        listed = _as_admin_request("GET", "/credentials")
        by_name = _as_admin_request("GET", "/credentials/by_name/anthropic-billing")

    assert listed.status_code == 200, listed.text
    rows = {row["credential_name"]: row for row in listed.json()["credentials"]}
    assert rows["anthropic-billing"]["credential_values"] == {}
    assert rows["openai-models"]["credential_values"] != {}
    assert by_name.status_code == 200, by_name.text
    assert by_name.json()["credential_values"] == {}
    assert "sk-ant-admin" not in listed.text + by_name.text
