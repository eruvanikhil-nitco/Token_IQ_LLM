from __future__ import annotations

from typing import Final

from litellm.tool_usage.credential_purpose import (
    TOOL_PURPOSE,
    is_tool_credential,
    tool_credential_problem,
)


def _problem(info: dict[str, object], values: dict[str, object], *, require_keys: bool = True) -> str | None:
    return tool_credential_problem(info, values, require_keys=require_keys)


def test_a_credential_with_no_marker_is_not_a_tool_credential() -> None:
    """The marker is what keeps a key that reads people's activity out of the pool that serves
    traffic. A credential without it must never be picked up by the tool ingestion job."""
    assert is_tool_credential(None) is False
    assert is_tool_credential({}) is False
    assert is_tool_credential({"purpose": "billing_ingestion"}) is False
    assert is_tool_credential({"purpose": TOOL_PURPOSE}) is True


def test_a_credential_naming_no_tool_is_refused_with_the_list_of_tools() -> None:
    problem: Final = _problem({"purpose": TOOL_PURPOSE}, {"api_key": "sk-ant-admin01-x"})

    assert problem is not None
    assert "claude_code" in problem and "cursor" in problem and "copilot" in problem


def test_a_credential_naming_a_tool_we_do_not_have_is_refused() -> None:
    assert _problem({"purpose": TOOL_PURPOSE, "tool": "codex"}, {"api_key": "x"}) is not None


def test_an_ordinary_anthropic_key_is_refused_before_it_fails_every_sync() -> None:
    """The usage report answers only to an organisation admin key. An ordinary key saves
    cleanly and then returns 401 every hour, which nobody connects back to this screen."""
    problem: Final = _problem({"purpose": TOOL_PURPOSE, "tool": "claude_code"}, {"api_key": "sk-ant-api03-x"})

    assert problem is not None
    assert "admin" in problem.lower()


def test_an_admin_key_for_claude_code_is_accepted() -> None:
    assert _problem({"purpose": TOOL_PURPOSE, "tool": "claude_code"}, {"api_key": "sk-ant-admin01-x"}) is None


def test_copilot_without_an_organisation_is_refused_because_seats_are_per_organisation() -> None:
    problem: Final = _problem({"purpose": TOOL_PURPOSE, "tool": "copilot"}, {"api_key": "ghp_x"})

    assert problem is not None
    assert "organization" in problem


def test_copilot_with_an_organisation_is_accepted() -> None:
    assert _problem({"purpose": TOOL_PURPOSE, "tool": "copilot"}, {"api_key": "ghp_x", "organization": "acme"}) is None


def test_cursor_needs_only_a_key_because_its_key_is_scoped_to_one_team() -> None:
    assert _problem({"purpose": TOOL_PURPOSE, "tool": "cursor"}, {"api_key": "key_x"}) is None


def test_a_missing_key_is_reported_when_keys_are_required() -> None:
    problem: Final = _problem({"purpose": TOOL_PURPOSE, "tool": "cursor"}, {})

    assert problem is not None
    assert "api_key" in problem


def test_an_update_that_does_not_resend_the_key_is_allowed() -> None:
    """Editing a credential must not force an admin to paste the secret again just to change
    something beside it."""
    assert _problem({"purpose": TOOL_PURPOSE, "tool": "cursor"}, {}, require_keys=False) is None
