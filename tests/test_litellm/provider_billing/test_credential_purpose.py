from __future__ import annotations

import pytest

from litellm.provider_billing.credential_purpose import (
    BILLING_PROVIDERS,
    billing_credential_problem,
    is_billing_credential,
)


def test_a_credential_is_for_billing_only_when_it_says_so():
    assert is_billing_credential({"purpose": "billing_ingestion", "provider": "openai"}) is True
    assert is_billing_credential({"custom_llm_provider": "openai"}) is False
    assert is_billing_credential(None) is False


def test_the_billing_providers_are_the_ones_this_build_has_connectors_for():
    assert BILLING_PROVIDERS == frozenset({"openai", "anthropic", "openrouter", "bedrock"})


@pytest.mark.parametrize(
    ("provider", "values"),
    [
        ("openai", {"api_key": "sk-admin-test-not-real"}),
        ("anthropic", {"api_key": "sk-ant-admin01-test-not-real"}),
        ("openrouter", {"api_key": "sk-or-v1-test-not-real"}),
        ("bedrock", {"aws_access_key_id": "AKIATESTNOTREAL", "aws_secret_access_key": "test-not-real"}),
    ],
)
def test_a_complete_billing_credential_has_no_problem(provider, values):
    info = {"purpose": "billing_ingestion", "provider": provider}

    assert billing_credential_problem(info, values, require_keys=True) is None


def test_an_ordinary_openai_key_is_refused_because_cost_reports_need_an_admin_key():
    """Saving a model key as a billing credential would fail on every sync with a 401,
    long after the admin who pasted it has moved on."""
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "openai"},
        {"api_key": "sk-proj-test-not-real"},
        require_keys=True,
    )

    assert problem is not None
    assert "sk-admin-" in problem


def test_an_ordinary_anthropic_key_is_refused():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "anthropic"},
        {"api_key": "sk-ant-api03-test-not-real"},
        require_keys=True,
    )

    assert problem is not None
    assert "sk-ant-admin" in problem


def test_an_unknown_provider_is_refused_and_the_message_lists_the_supported_ones():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "cohere"}, {"api_key": "x"}, require_keys=True
    )

    assert problem is not None
    assert "anthropic, bedrock, openai, openrouter" in problem


def test_a_missing_key_is_refused_on_create():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "openrouter"}, {}, require_keys=True
    )

    assert problem is not None
    assert "api_key" in problem


def test_a_bedrock_credential_without_both_aws_keys_is_refused_on_create():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "bedrock"},
        {"aws_access_key_id": "AKIATESTNOTREAL"},
        require_keys=True,
    )

    assert problem is not None
    assert "aws_secret_access_key" in problem


def test_an_update_that_sends_no_key_keeps_the_stored_one_and_is_accepted():
    """The stored key was checked when it was saved and is never sent back to the form,
    so an edit that renames nothing and sends no key must not be refused."""
    assert (
        billing_credential_problem({"purpose": "billing_ingestion", "provider": "openai"}, {}, require_keys=False)
        is None
    )


def test_an_update_that_sends_a_wrong_kind_of_key_is_refused():
    problem = billing_credential_problem(
        {"purpose": "billing_ingestion", "provider": "openai"},
        {"api_key": "sk-proj-test-not-real"},
        require_keys=False,
    )

    assert problem is not None
