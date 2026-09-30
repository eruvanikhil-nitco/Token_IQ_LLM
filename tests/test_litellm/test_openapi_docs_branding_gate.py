"""The branding gate must catch real prose and ignore identifiers.

A gate whose exclusions are slightly too broad passes on an empty set and looks like success.
That failure has happened on this branch before, so the exclusions get their own tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
if str(REPO / "tests" / "code_coverage_tests") not in sys.path:
    sys.path.insert(0, str(REPO / "tests" / "code_coverage_tests"))

from check_openapi_docs_do_not_name_litellm import offenders  # noqa: E402  # path set above


def test_a_description_naming_litellm_is_caught() -> None:
    schema: Final = {"paths": {"/x": {"get": {"description": "Proxied by LiteLLM."}}}}

    assert len(offenders(schema)) == 1


def test_a_link_to_another_products_documentation_is_caught() -> None:
    schema: Final = {"paths": {"/x": {"get": {"description": "See https://docs.litellm.ai/docs/x"}}}}

    assert len(offenders(schema)) == 1


def test_a_strangers_address_in_an_example_is_caught() -> None:
    """Ten real addresses belonging to people at another company were being shown to our
    customers as example values."""
    schema: Final = {"components": {"schemas": {"U": {"properties": {"e": {"example": "someone@berri.ai"}}}}}}

    assert len(offenders(schema)) == 1


def test_a_title_pydantic_generated_from_a_field_name_is_ignored() -> None:
    """Rewriting this means renaming the request field, which changes what a client sends."""
    schema: Final = {
        "components": {"schemas": {"R": {"properties": {"litellm_call_id": {"title": "Litellm Call Id"}}}}}
    }

    assert offenders(schema) == ()


def test_a_schema_title_that_is_just_the_class_name_is_ignored() -> None:
    schema: Final = {"components": {"schemas": {"LiteLLMKeyType": {"title": "LiteLLMKeyType"}}}}

    assert offenders(schema) == ()


def test_a_parameter_title_generated_from_its_name_is_ignored() -> None:
    """The name lives in a sibling field rather than in the path, which the walker has to
    carry down or this reads as prose and can never be fixed without renaming the parameter."""
    schema: Final = {
        "paths": {
            "/x": {"get": {"parameters": [{"name": "litellm_model_id", "schema": {"title": "Litellm Model Id"}}]}}
        }
    }

    assert offenders(schema) == ()


def test_a_hand_written_title_naming_litellm_is_still_caught() -> None:
    """The exclusion is for titles that echo an identifier, not for every title. A title that
    says something a human wrote must not slip through with them."""
    schema: Final = {
        "components": {"schemas": {"KeyType": {"properties": {"kind": {"title": "The LiteLLM key kind"}}}}}
    }

    assert len(offenders(schema)) == 1


def test_clean_documentation_produces_no_offenders() -> None:
    schema: Final = {"paths": {"/x": {"get": {"description": "Creates a key.", "summary": "Create key"}}}}

    assert offenders(schema) == ()


def test_a_database_table_name_inside_prose_is_ignored() -> None:
    """`LiteLLM_SpendLogs` is the table's actual name. Renaming it is a migration, not a
    rewrite of a sentence, so the gate must not demand one."""
    schema: Final = {"paths": {"/x": {"get": {"description": "Resets LiteLLM_SpendLogs."}}}}

    assert offenders(schema) == ()


def test_a_request_field_name_inside_prose_is_ignored() -> None:
    schema: Final = {"paths": {"/x": {"get": {"description": "Pass litellm_call_id to trace it."}}}}

    assert offenders(schema) == ()


def test_the_product_name_in_lower_case_is_still_caught() -> None:
    """Several descriptions say "surfaced by litellm" in lower case, which reads to a customer
    exactly like the capitalised form."""
    schema: Final = {"paths": {"/x": {"get": {"description": "Errors surfaced by litellm."}}}}

    assert len(offenders(schema)) == 1


def test_a_header_name_a_client_must_send_is_ignored() -> None:
    """`x-litellm-model` is a header a client sends. Renaming it breaks those clients."""
    schema: Final = {"paths": {"/x": {"post": {"description": "Pass model via `x-litellm-model`."}}}}

    assert offenders(schema) == ()


def test_a_quoted_default_value_is_ignored() -> None:
    """The default really is the string 'litellm'. Rewriting the sentence without changing the
    value would make the documentation lie, and changing the value changes what a third party
    receives."""
    schema: Final = {
        "components": {"schemas": {"C": {"properties": {"app": {"description": "Defaults to 'litellm'"}}}}}
    }

    assert offenders(schema) == ()


def test_a_dotted_setting_name_is_ignored() -> None:
    """`litellm.skip_system_message_in_guardrail` is a setting a customer writes in their
    config. Renaming it changes what their config file has to say."""
    schema: Final = {"paths": {"/x": {"get": {"description": "Uses litellm.skip_tool_message_in_guardrail."}}}}

    assert offenders(schema) == ()


def test_a_sentence_that_merely_ends_in_the_product_name_is_still_caught() -> None:
    """The exclusion is for an attribute path, not for a full stop."""
    schema: Final = {"paths": {"/x": {"get": {"description": "This request was priced by litellm."}}}}

    assert len(offenders(schema)) == 1


def test_a_url_encoded_address_is_caught() -> None:
    """A curl example wrote the address as krrish7%40berri.ai, which a plain @ search misses
    and which a customer's browser still renders as a real person's address."""
    schema: Final = {"paths": {"/x": {"get": {"description": "curl '.../user/info?user_id=a%40berri.ai'"}}}}

    assert len(offenders(schema)) == 1
