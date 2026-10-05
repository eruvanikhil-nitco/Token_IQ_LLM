"""Tests for the credential management endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
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


def test_creating_a_credential_whose_name_is_already_taken_answers_409():
    """The dashboard's move-key action retries against this status to finish a move whose
    credential was already stored, so the duplicate has to be distinguishable from a 500."""
    from prisma.errors import UniqueViolationError

    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialAccessor.upsert_credentials"
    ) as upsert:
        repository.return_value.create = AsyncMock(
            side_effect=UniqueViolationError({}, message="Unique constraint failed")
        )

        response = _as_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "taken",
                "credential_values": {"api_key": "sk-test-not-real"},
                "credential_info": {"custom_llm_provider": "openai"},
            },
        )

    assert response.status_code == 409, response.text
    assert "taken" in response.json()["error"]["message"]
    upsert.assert_not_called()


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
    # The row is now absent entirely, not merely emptied: this list feeds the pages that attach a
    # credential to a deployment, and a billing key must never be offered there.
    assert "anthropic-billing" not in rows
    assert rows["openai-models"]["credential_values"] != {}
    assert by_name.status_code == 200, by_name.text
    assert by_name.json()["credential_values"] == {}
    assert "sk-ant-admin" not in listed.text + by_name.text


def _billing_and_model_credentials():
    return (
        CredentialItem(
            credential_name="openai-billing",
            credential_values={"api_key": "sk-admin-test-not-real"},
            credential_info={"purpose": "billing_ingestion", "provider": "openai"},
        ),
        CredentialItem(
            credential_name="openai-models",
            credential_values={"api_key": "sk-proj-test-not-real"},
            credential_info={"custom_llm_provider": "openai"},
        ),
    )


def test_the_credential_list_leaves_out_billing_credentials_altogether():
    """`/credentials` feeds the pages that attach a credential to a model deployment.

    A billing credential is an organisation admin key that reads a whole account's costs. It is
    never used to serve models, and listing it there invites someone to attach it to a deployment,
    which is the thing the purpose marker exists to prevent. The billing pages read
    `/provider/connections`, which enumerates them, so nothing needs this list to carry them.
    """
    import litellm

    billing, model_access = _billing_and_model_credentials()
    with patch.object(litellm, "credential_list", [billing, model_access]):
        listed = _as_admin_request("GET", "/credentials")

    assert listed.status_code == 200, listed.text
    names = {row["credential_name"] for row in listed.json()["credentials"]}
    assert names == {"openai-models"}, names


def test_a_billing_credential_is_still_readable_by_name():
    """Excluding them from the list must not hide them from the connect flow, which reads one
    back by name to show its state. A filter that hides them from everything is not a tidy-up."""
    import litellm

    billing, model_access = _billing_and_model_credentials()
    with patch.object(litellm, "credential_list", [billing, model_access]):
        found = _as_admin_request("GET", "/credentials/by_name/openai-billing")

    assert found.status_code == 200, found.text
    assert found.json()["credential_name"] == "openai-billing"
    assert found.json()["credential_info"]["purpose"] == "billing_ingestion"


def test_the_credential_list_still_carries_an_ordinary_credential_with_no_purpose_at_all():
    """Most stored credentials have no `purpose` key. Reading a missing key as "billing" would
    empty the list the model pages depend on."""
    import litellm

    plain = CredentialItem(
        credential_name="plain",
        credential_values={"api_key": "sk-plain-not-real"},
        credential_info={},
    )
    with patch.object(litellm, "credential_list", [plain]):
        listed = _as_admin_request("GET", "/credentials")

    assert listed.status_code == 200, listed.text
    assert [row["credential_name"] for row in listed.json()["credentials"]] == ["plain"]


TEAM_ADMIN = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-lead", user_id="lead")


def _as_team_admin_request(method: str, path: str, body: dict | None = None):
    missing = object()
    previous_override = app.dependency_overrides.get(user_api_key_auth, missing)
    app.dependency_overrides[user_api_key_auth] = lambda: TEAM_ADMIN
    try:
        return client.request(method, path, json=body, headers={"Authorization": "Bearer sk-lead"})
    finally:
        if previous_override is missing:
            app.dependency_overrides.pop(user_api_key_auth, None)
        else:
            app.dependency_overrides[user_api_key_auth] = previous_override


def test_a_team_admin_creating_a_credential_gets_their_team_recorded_on_it():
    """Condition 2 of the spec: a team admin's credential belongs to their team, so the
    list can show them only their own."""
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialAccessor.upsert_credentials"):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "team-a-openai",
                "credential_values": {"api_key": "sk-test-not-real"},
                "credential_info": {"custom_llm_provider": "openai"},
            },
        )

    assert response.status_code == 200, response.text
    written = repository.return_value.create.await_args.kwargs["data"]
    info = written["credential_info"]
    assert (json.loads(info) if isinstance(info, str) else info)["team_id"] == "team-a"


def test_a_team_admin_cannot_create_a_billing_credential():
    """A billing credential is what the installation's cost ingestion runs on, and the lookup
    that picks one ignores team_id, so a team admin's row could become the key every provider
    bill is read with. Only a proxy admin may mark one."""
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialAccessor.upsert_credentials"):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "openai-billing",
                "credential_values": {"api_key": "sk-admin-test-not-real"},
                "credential_info": {"purpose": "billing_ingestion", "provider": "openai"},
            },
        )

    assert response.status_code == 403, response.text
    assert "proxy admin" in response.json()["error"]["message"]
    repository.return_value.create.assert_not_awaited()


def test_a_team_admin_who_administers_no_team_cannot_create_a_credential():
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset()),
    ):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "nope",
                "credential_values": {"api_key": "sk-test-not-real"},
                "credential_info": {"custom_llm_provider": "openai"},
            },
        )

    assert response.status_code == 403, response.text
    repository.return_value.create.assert_not_awaited()


def test_a_team_admin_cannot_put_a_credential_in_another_team():
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        repository.return_value.create = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "POST",
            "/credentials",
            {
                "credential_name": "sneaky",
                "credential_values": {"api_key": "sk-test-not-real"},
                "credential_info": {"custom_llm_provider": "openai", "team_id": "team-b"},
            },
        )

    assert response.status_code == 403, response.text
    repository.return_value.create.assert_not_awaited()


def test_the_list_shows_a_team_admin_only_their_own_and_the_shared_credentials():
    import litellm

    mine = CredentialItem(
        credential_name="team-a-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-a"},
    )
    theirs = CredentialItem(
        credential_name="team-b-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-b"},
    )
    shared = CredentialItem(
        credential_name="shared-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch.object(
        litellm, "credential_list", [mine, theirs, shared]
    ), patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        response = _as_team_admin_request("GET", "/credentials")

    assert response.status_code == 200, response.text
    names = {row["credential_name"] for row in response.json()["credentials"]}
    assert names == {"team-a-openai", "shared-openai"}


def test_a_team_admin_cannot_read_another_team_s_credential_by_name():
    import litellm

    theirs = CredentialItem(
        credential_name="team-b-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-b"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch.object(
        litellm, "credential_list", [theirs]
    ), patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        response = _as_team_admin_request("GET", "/credentials/by_name/team-b-openai")

    assert response.status_code == 403, response.text


def test_a_team_admin_cannot_change_a_shared_credential():
    """A shared credential serves teams they do not run."""
    stored = CredentialItem(
        credential_name="shared-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.credential_endpoints.endpoints.CredentialsRepository"
    ) as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)
        repository.return_value.delete_by_name = AsyncMock(return_value=None)

        patched = _as_team_admin_request(
            "PATCH",
            "/credentials/shared-openai",
            {"credential_name": "shared-openai", "credential_values": {"api_key": "sk-test-not-real-2"}, "credential_info": {}},
        )
        deleted = _as_team_admin_request("DELETE", "/credentials/shared-openai")

    assert patched.status_code == 403, patched.text
    assert deleted.status_code == 403, deleted.text
    repository.return_value.update_by_name.assert_not_awaited()
    repository.return_value.delete_by_name.assert_not_awaited()


def test_a_team_admin_may_change_their_own_team_s_credential():
    stored = CredentialItem(
        credential_name="team-a-openai",
        credential_values={"api_key": "sk-test-not-real"},
        credential_info={"custom_llm_provider": "openai", "team_id": "team-a"},
    )
    with patch("litellm.proxy.proxy_server.prisma_client", MagicMock()), patch(
        "litellm.proxy.proxy_server.master_key", "sk-test-master"
    ), patch("litellm.proxy.credential_endpoints.endpoints.CredentialsRepository") as repository, patch(
        "litellm.proxy.credential_endpoints.endpoints.teams_user_administers",
        AsyncMock(return_value=frozenset({"team-a"})),
    ):
        repository.return_value.find_by_name = AsyncMock(return_value=stored)
        repository.return_value.update_by_name = AsyncMock(return_value=None)

        response = _as_team_admin_request(
            "PATCH",
            "/credentials/team-a-openai",
            {"credential_name": "team-a-openai", "credential_values": {"api_key": "sk-test-not-real-2"}, "credential_info": {}},
        )

    assert response.status_code == 200, response.text
    repository.return_value.update_by_name.assert_awaited_once()


def test_a_credential_with_connection_details_and_no_secret_is_accepted():
    """Condition 3 of the spec: Bedrock and Vertex on cloud permissions, and a local
    Ollama, carry a base URL or a region but no key."""
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
                "credential_name": "local-ollama",
                "credential_values": {"api_base": "http://localhost:11434"},
                "credential_info": {"custom_llm_provider": "ollama"},
            },
        )

    assert response.status_code == 200, response.text
    repository.return_value.create.assert_awaited_once()
