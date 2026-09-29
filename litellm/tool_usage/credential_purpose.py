"""Which stored credentials read a user tool's usage, and whether one is fit to.

Mirrors `litellm/provider_billing/credential_purpose.py`. A tool credential reads what people
did inside a tool and is never used to serve models, so one marker on `credential_info`
identifies it for the ingestion job, the credential endpoints and the dashboard alike.

Each tool needs something different beyond a key, and checking it here rather than at fetch
time is the difference between an admin being told now and a sync failing silently every hour.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

TOOL_PURPOSE: Final = "tool_usage_ingestion"

TOOL_NAMES: Final[frozenset[str]] = frozenset({"claude_code", "cursor", "copilot"})

_ADMIN_KEY_PREFIXES: Final = MappingProxyType({"claude_code": "sk-ant-admin"})
"""The Claude Code usage report answers only to an organisation admin key. An ordinary key
saves fine and then fails every sync with a 401."""

_REQUIRED_FIELDS: Final = MappingProxyType({"copilot": ("organization",)})
"""Copilot seats are per organisation, so a credential without one can never be used."""


def is_tool_credential(credential_info: Mapping[str, object] | None) -> bool:
    """Whether this credential is marked for reading a user tool's usage."""
    return credential_info is not None and credential_info.get("purpose") == TOOL_PURPOSE


def _present(value: object) -> bool:
    return isinstance(value, str) and value != ""


def tool_credential_problem(
    credential_info: Mapping[str, object],
    credential_values: Mapping[str, object],
    *,
    require_keys: bool,
) -> str | None:
    """Why this tool credential cannot read its tool's usage, or None when it can."""
    tool: Final = credential_info.get("tool")
    if not isinstance(tool, str) or tool not in TOOL_NAMES:
        return f"A user tool credential needs a tool, one of: {', '.join(sorted(TOOL_NAMES))}."

    api_key: Final = credential_values.get("api_key")
    if not _present(api_key):
        if require_keys:
            return f"A {tool} credential needs an api_key."
        return None

    missing: Final = tuple(name for name in _REQUIRED_FIELDS.get(tool, ()) if not _present(credential_values.get(name)))
    if require_keys and missing:
        return f"A {tool} credential needs {' and '.join(missing)}."

    prefix: Final = _ADMIN_KEY_PREFIXES.get(tool)
    if prefix is not None and isinstance(api_key, str) and not api_key.startswith(prefix):
        return f"This is not an organisation admin key. The {tool} usage report needs one, and it starts with {prefix}."
    return None
